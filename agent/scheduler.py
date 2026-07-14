import requests
from qa_agent import QAAgent


class AgentScheduler:
    """
    C 负责的 Agent 调度器。

    当前实现的基础流程：
    1. 接收用户法律问题
    2. 先调用 /search 检索相关法条
    3. 再调用 QAAgent，使用 /rag 生成最终回答
    4. 整理最终答案、引用法条和调度步骤

    后续等 B 的 RetrievalAgent 和 SummaryAgent 完成后，
    可以把 /search 和 summary 部分替换成 B 的 Agent。
    """

    def __init__(self, base_url: str, top_k: int = 3):
        self.base_url = base_url.rstrip("/")
        self.top_k = top_k
        self.qa_agent = QAAgent(base_url, top_k=top_k)

    def search_articles(self, question: str) -> dict:
        """
        调用组长提供的 /search 接口，获取相关法条。
        这一步相当于调度流程里的“先检索”。
        """
        url = f"{self.base_url}/search"

        payload = {
            "query": question,
            "top_k": self.top_k
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "articles": data.get("results", data.get("articles", data.get("references", []))),
                "raw": data
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "articles": [],
                "error": str(e)
            }

    def summarize_result(self, question: str, answer: str, references: list) -> str:
        """
        当前基础版 Summary 逻辑：
        不单独调用大模型，只对结果做简单整理。
        后续可以替换成 B 的 SummaryAgent。
        """
        if not references:
            return f"问题：{question}\n\n回答：{answer}\n\n未返回引用法条。"

        ref_text_list = []

        for index, ref in enumerate(references, start=1):
            law_name = ref.get("law_name", "未知法律")
            article_no = ref.get("article_no", "未知条文")
            content = ref.get("content", "")
            score = ref.get("score", "")

            ref_text_list.append(
                f"[{index}] {law_name} {article_no}\n"
                f"相关度：{score}\n"
                f"内容：{content}"
            )

        references_text = "\n\n".join(ref_text_list)

        return (
            f"问题：{question}\n\n"
            f"最终回答：\n{answer}\n\n"
            f"引用法条：\n{references_text}"
        )

    def run(self, question: str) -> dict:
        steps = []

        steps.append("接收用户问题")

        steps.append("调用 /search 接口，先检索相关法条")
        search_result = self.search_articles(question)

        if search_result["success"]:
            steps.append("检索成功，获得相关法条")
        else:
            steps.append("检索失败，继续调用 /rag 尝试生成回答")

        steps.append("调用 QAAgent")
        qa_result = self.qa_agent.answer(question)

        if not qa_result["success"]:
            steps.append("QAAgent 调用失败")

            return {
                "success": False,
                "question": question,
                "final_answer": "QAAgent 调用失败，请检查 /rag 接口或网络连接。",
                "references": [],
                "search_result": search_result,
                "summary": "",
                "steps": steps,
                "error": qa_result.get("error")
            }

        steps.append("QAAgent 成功调用 /rag 接口")
        steps.append("获得最终回答和引用法条")

        references = qa_result.get("references", [])
        summary = self.summarize_result(question, qa_result["answer"], references)

        steps.append("整理最终输出结果")

        return {
            "success": True,
            "question": question,
            "final_answer": qa_result["answer"],
            "references": references,
            "search_result": search_result,
            "summary": summary,
            "steps": steps,
            "raw": qa_result["raw"]
        }


if __name__ == "__main__":
    scheduler = AgentScheduler("http://172.20.10.2:8000")

    while True:
        question = input("\n请输入法律问题，输入 q 退出：").strip()

        if question.lower() == "q":
            print("已退出 AgentScheduler。")
            break

        if not question:
            print("问题不能为空，请重新输入。")
            continue

        result = scheduler.run(question)

        print("\n调用是否成功：", result["success"])
        print("\n调度步骤：")
        for step in result["steps"]:
            print("-", step)

        print("\n最终回答：")
        print(result["final_answer"])

        print("\n引用法条：")
        for index, ref in enumerate(result["references"], start=1):
            print(f"\n[{index}] {ref.get('law_name', '未知法律')} {ref.get('article_no', '未知条文')}")
            print("内容：", ref.get("content", ""))
            print("相关度：", ref.get("score", ""))

        if not result["success"]:
            print("\n错误信息：", result.get("error"))