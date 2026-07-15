try:
    from agent.qa_agent import QAAgent
    from agent.retrieval_agent import RetrievalAgent
    from agent.summary_agent import SummaryAgent
except ImportError:
    from qa_agent import QAAgent
    from retrieval_agent import RetrievalAgent
    from summary_agent import SummaryAgent


class AgentScheduler:
    """
    C 负责的 Agent 调度器。

    当前完整流程：
    1. 用户输入法律问题
    2. RetrievalAgent 调用 /search 检索相关法条
    3. QAAgent 调用 /rag 生成最终回答
    4. SummaryAgent 对检索到的法条做结构化总结
    5. 返回最终回答、引用法条、检索结果、总结结果和调度步骤
    """

    def __init__(self, base_url: str = "http://172.20.10.2:8000", top_k: int = 3):
        self.base_url = base_url.rstrip("/")
        self.top_k = top_k

        self.retrieval_agent = RetrievalAgent(base_url=self.base_url)
        self.qa_agent = QAAgent(base_url=self.base_url, top_k=self.top_k)
        self.summary_agent = SummaryAgent()

    def run(self, question: str) -> dict:
        question = (question or "").strip()
        steps = []

        if not question:
            return {
                "success": False,
                "question": question,
                "final_answer": "",
                "references": [],
                "retrieval_result": {},
                "summary_result": {},
                "steps": ["问题为空，调度终止"],
                "error": "问题不能为空。"
            }

        steps.append("接收用户问题")

        # 1. 检索 Agent
        steps.append("调用 RetrievalAgent，通过 /search 检索相关法条")
        retrieval_result = self.retrieval_agent.retrieve(question)

        if retrieval_result.get("status") == "error":
            steps.append("RetrievalAgent 调用失败")

            return {
                "success": False,
                "question": question,
                "final_answer": "",
                "references": [],
                "retrieval_result": retrieval_result,
                "summary_result": {},
                "steps": steps,
                "error": retrieval_result.get("message", "检索失败。")
            }

        steps.append("RetrievalAgent 返回检索结果")

        # 2. 问答 Agent
        steps.append("调用 QAAgent，通过 /rag 生成最终回答")
        qa_result = self.qa_agent.answer(question)

        if not qa_result.get("success"):
            steps.append("QAAgent 调用失败")

            return {
                "success": False,
                "question": question,
                "final_answer": "",
                "references": retrieval_result.get("trusted_results", []),
                "retrieval_result": retrieval_result,
                "summary_result": {},
                "steps": steps,
                "error": qa_result.get("error", "问答生成失败。")
            }

        steps.append("QAAgent 返回最终回答和引用法条")

        # 3. 总结 Agent
        steps.append("调用 SummaryAgent，对检索结果做结构化总结")
        summary_result = self.summary_agent.summarize(retrieval_result)
        steps.append("SummaryAgent 返回总结结果")

        steps.append("完成完整 Agent 调度流程")

        return {
            "success": True,
            "question": question,
            "final_answer": qa_result.get("answer", ""),
            "references": qa_result.get("references", []),
            "retrieval_result": retrieval_result,
            "summary_result": summary_result,
            "steps": steps,
            "raw": qa_result.get("raw", {})
        }


if __name__ == "__main__":
    scheduler = AgentScheduler("http://172.20.10.2:8000")

    question = "用人单位拖欠工资，劳动者可以解除劳动合同吗？"
    result = scheduler.run(question)

    print("调用是否成功：", result["success"])
    print("问题：", result["question"])

    print("\n调度步骤：")
    for step in result["steps"]:
        print("-", step)

    print("\n最终回答：")
    print(result["final_answer"])

    print("\nQAAgent 引用法条：")
    for index, ref in enumerate(result.get("references", []), start=1):
        print(f"\n[{index}] {ref.get('law_name', '未知法规')} {ref.get('article_no', '')}")
        print("内容：", ref.get("content", ""))
        print("相关度：", ref.get("score", ""))

    print("\nSummaryAgent 总结：")
    summary_result = result.get("summary_result", {})
    print(summary_result.get("summary", ""))

    if not result["success"]:
        print("\n错误信息：", result.get("error"))