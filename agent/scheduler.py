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

    Day 4 更新：
    1. 支持空问题检查
    2. 支持 RetrievalAgent 超时后的兜底处理
    3. 支持 QAAgent 调用失败时返回错误信息
    4. 支持 SummaryAgent 异常处理
    5. 保留完整调度步骤，方便联调和测试
    """

    def __init__(self, base_url: str = "http://172.20.10.2:8000", top_k: int = 3):
        self.base_url = base_url.rstrip("/")
        self.top_k = top_k

        self.retrieval_agent = RetrievalAgent(
            base_url=self.base_url,
            timeout=120
        )
        self.qa_agent = QAAgent(
            base_url=self.base_url,
            top_k=self.top_k
        )
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

        # 1. RetrievalAgent：先检索相关法条
        steps.append("调用 RetrievalAgent，通过 /search 检索相关法条")
        retrieval_result = self.retrieval_agent.retrieve(question)

        retrieval_success = retrieval_result.get("status") == "success"

        if retrieval_success:
            steps.append("RetrievalAgent 返回检索结果")
        else:
            steps.append("RetrievalAgent 调用失败或无结果，记录错误信息")
            steps.append("继续调用 QAAgent 作为兜底流程")

        # 2. QAAgent：生成最终回答
        steps.append("调用 QAAgent，通过 /rag 生成最终回答")
        qa_result = self.qa_agent.answer(question)

        if not qa_result.get("success"):
            steps.append("QAAgent 调用失败，调度终止")

            return {
                "success": False,
                "question": question,
                "final_answer": "",
                "references": [],
                "retrieval_result": retrieval_result,
                "summary_result": {},
                "steps": steps,
                "error": qa_result.get("error", "QAAgent 调用失败。")
            }

        steps.append("QAAgent 返回最终回答和引用法条")

        # 3. SummaryAgent：对 RetrievalAgent 的结果做总结
        steps.append("调用 SummaryAgent，对检索结果做结构化总结")
        try:
            summary_result = self.summary_agent.summarize(retrieval_result)
            steps.append("SummaryAgent 返回总结结果")
        except Exception as exc:
            summary_result = {
                "agent": "SummaryAgent",
                "status": "error",
                "question": question,
                "summary": "",
                "references": [],
                "message": f"SummaryAgent 调用失败：{exc}"
            }
            steps.append("SummaryAgent 调用失败，但不影响 QAAgent 最终回答")

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

    test_questions = [
        "用人单位拖欠工资，劳动者可以解除劳动合同吗？",
        "试用期最长可以约定多久？",
        "公司不签劳动合同怎么办？"
    ]

    for question in test_questions:
        print("\n" + "=" * 60)
        print("测试问题：", question)

        result = scheduler.run(question)

        print("\n调用是否成功：", result["success"])

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