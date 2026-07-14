from qa_agent import QAAgent


class AgentScheduler:
    """
    C 负责的 Agent 调度逻辑。

    当前基础流程：
    用户问题 -> QAAgent -> /rag -> 最终回答

    后续可以扩展为：
    用户问题 -> RetrievalAgent -> QAAgent -> SummaryAgent -> 最终输出
    """

    def __init__(self, base_url: str):
        self.qa_agent = QAAgent(base_url)

    def run(self, question: str) -> dict:
        steps = []

        steps.append("接收用户问题")
        steps.append("调用 QAAgent")
        qa_result = self.qa_agent.answer(question)

        if not qa_result["success"]:
            steps.append("QAAgent 调用失败")

            return {
                "success": False,
                "question": question,
                "final_answer": "QAAgent 调用失败，请检查 /rag 接口或网络连接。",
                "references": [],
                "steps": steps,
                "error": qa_result.get("error")
            }

        steps.append("QAAgent 成功调用 /rag 接口")
        steps.append("返回最终回答和引用法条")

        return {
            "success": True,
            "question": question,
            "final_answer": qa_result["answer"],
            "references": qa_result["references"],
            "steps": steps,
            "raw": qa_result["raw"]
        }


if __name__ == "__main__":
    scheduler = AgentScheduler("http://172.20.10.2:8000")

    question = "用人单位拖欠工资，劳动者可以解除劳动合同吗？"
    result = scheduler.run(question)

    print("调用是否成功：", result["success"])
    print("问题：", result["question"])
    print("最终回答：", result["final_answer"])
    print("引用法条：", result["references"])
    print("调度步骤：")

    for step in result["steps"]:
        print("-", step)

    if not result["success"]:
        print("错误信息：", result["error"])