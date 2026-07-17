# -*- coding: utf-8 -*-

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

    支持两种调度流程：
    1. run(question)：单轮问答流程
       RetrievalAgent -> QAAgent.answer(/rag) -> SummaryAgent

    2. chat(messages)：多轮对话流程
       RetrievalAgent -> QAAgent.chat(/chat) -> SummaryAgent
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
            top_k=self.top_k,
            timeout=120
        )

        self.summary_agent = SummaryAgent()

    def run(self, question: str) -> dict:
        """
        单轮 Agent 调度流程。
        保持原来的格式不变。
        """
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

        try:
            retrieval_result = self.retrieval_agent.retrieve(question)
        except Exception as exc:
            retrieval_result = {
                "agent": "RetrievalAgent",
                "status": "error",
                "question": question,
                "results": [],
                "message": f"RetrievalAgent 调用失败：{exc}"
            }

        retrieval_success = retrieval_result.get("status") == "success"

        if retrieval_success:
            steps.append("RetrievalAgent 返回检索结果")
        else:
            steps.append("RetrievalAgent 调用失败或无结果，记录错误信息")
            steps.append("继续调用 QAAgent 作为兜底流程")

        # 2. QAAgent：生成最终回答
        steps.append("调用 QAAgent，通过 /rag 生成最终回答")

        try:
            qa_result = self.qa_agent.answer(question)
        except Exception as exc:
            qa_result = {
                "success": False,
                "question": question,
                "answer": "",
                "references": [],
                "error": f"QAAgent 调用异常：{exc}"
            }

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

    def chat(self, messages: list[dict]) -> dict:
        """
        多轮 Agent 调度流程。

        在原有三 Agent 串联基础上新增多轮对话支持：
        1. 接收 messages 历史
        2. 从 messages 中提取最近用户问题，用于 RetrievalAgent 检索
        3. RetrievalAgent 调用 /search
        4. QAAgent.chat 调用 /chat
        5. SummaryAgent 对检索结果做结构化总结
        6. 调度器汇总返回

        返回格式尽量与 run(question) 保持一致。
        """
        steps = []
        messages = self._normalize_messages(messages)

        if not messages:
            return {
                "success": False,
                "question": "",
                "messages": [],
                "final_answer": "",
                "references": [],
                "retrieval_result": {},
                "summary_result": {},
                "steps": ["messages 为空，调度终止"],
                "error": "messages 不能为空。"
            }

        current_question = self._get_last_user_message(messages)

        if not current_question:
            return {
                "success": False,
                "question": "",
                "messages": messages,
                "final_answer": "",
                "references": [],
                "retrieval_result": {},
                "summary_result": {},
                "steps": ["messages 中没有 user 消息，调度终止"],
                "error": "messages 中必须至少包含一条 user 消息。"
            }

        search_query = self._build_search_query_from_messages(messages)

        steps.append("接收用户多轮对话历史")
        steps.append("提取当前问题及最近上下文")

        # 1. RetrievalAgent：多轮场景下仍然先检索
        steps.append("调用 RetrievalAgent，通过 /search 检索相关法条")

        try:
            retrieval_result = self.retrieval_agent.retrieve(search_query)
        except Exception as exc:
            retrieval_result = {
                "agent": "RetrievalAgent",
                "status": "error",
                "question": search_query,
                "results": [],
                "message": f"RetrievalAgent 调用失败：{exc}"
            }

        retrieval_success = retrieval_result.get("status") == "success"

        if retrieval_success:
            steps.append("RetrievalAgent 返回检索结果")
        else:
            steps.append("RetrievalAgent 调用失败或无结果，记录错误信息")
            steps.append("继续调用 QAAgent.chat 作为兜底流程")

        # 2. QAAgent：调用 /chat 生成多轮回答
        steps.append("调用 QAAgent，通过 /chat 生成最终回答")

        try:
            qa_result = self.qa_agent.chat(messages)
        except Exception as exc:
            qa_result = {
                "success": False,
                "question": current_question,
                "messages": messages,
                "answer": "",
                "references": [],
                "error": f"QAAgent.chat 调用异常：{exc}"
            }

        if not qa_result.get("success"):
            steps.append("QAAgent 调用失败，调度终止")

            return {
                "success": False,
                "question": current_question,
                "messages": messages,
                "final_answer": "",
                "references": [],
                "retrieval_result": retrieval_result,
                "summary_result": {},
                "steps": steps,
                "error": qa_result.get("error", "QAAgent.chat 调用失败。")
            }

        steps.append("QAAgent 返回最终回答和引用法条")

        # 3. SummaryAgent：多轮场景下仍然总结检索结果
        steps.append("调用 SummaryAgent，对检索结果做结构化总结")

        try:
            summary_result = self.summary_agent.summarize(retrieval_result)
            steps.append("SummaryAgent 返回总结结果")
        except Exception as exc:
            summary_result = {
                "agent": "SummaryAgent",
                "status": "error",
                "question": current_question,
                "summary": "",
                "references": [],
                "message": f"SummaryAgent 调用失败：{exc}"
            }
            steps.append("SummaryAgent 调用失败，但不影响 QAAgent 最终回答")

        steps.append("完成完整 Agent 调度流程")

        return {
            "success": True,
            "question": current_question,
            "messages": messages,
            "final_answer": qa_result.get("answer", ""),
            "references": qa_result.get("references", []),
            "retrieval_result": retrieval_result,
            "summary_result": summary_result,
            "steps": steps,
            "raw": qa_result.get("raw", {})
        }

    @staticmethod
    def _normalize_messages(messages: list[dict]) -> list[dict]:
        """
        清洗多轮 messages。
        """
        allowed_roles = {"system", "user", "assistant"}
        normalized = []

        for msg in messages or []:
            role = str(msg.get("role", "")).strip()
            content = str(msg.get("content", "")).strip()

            if not content:
                continue

            if role not in allowed_roles:
                role = "user"

            normalized.append({
                "role": role,
                "content": content
            })

        return normalized

    @staticmethod
    def _get_last_user_message(messages: list[dict]) -> str:
        """
        获取最后一条 user 消息，作为当前轮问题。
        """
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                return msg["content"].strip()
        return ""

    @staticmethod
    def _build_search_query_from_messages(
        messages: list[dict],
        max_user_turns: int = 3
    ) -> str:
        """
        用最近几轮用户问题拼接成检索 query。

        这样可以解决多轮追问缺上下文的问题。
        例如：
        第一轮：劳动合同必须签书面的吗？
        第二轮：那如果公司一直没签怎么办？

        如果只检索第二句，检索效果可能不好；
        拼接最近几轮 user 消息后，RetrievalAgent 更容易找到相关法条。
        """
        user_messages = []

        for msg in messages:
            if msg.get("role") == "user" and msg.get("content", "").strip():
                user_messages.append(msg["content"].strip())

        recent_user_messages = user_messages[-max_user_turns:]

        return "\n".join(recent_user_messages)


if __name__ == "__main__":
    scheduler = AgentScheduler("http://172.20.10.2:8000")

    print("\n========== 单轮调度测试 ==========")

    test_questions = [
    "劳动合同试用期最长可以约定多久？",
    "劳动合同期限不满三个月，可以约定试用期吗？",
    "用人单位违法延长试用期需要承担什么责任？",
    "借款合同一定要采用书面形式吗？",
    "未成年人签订的合同是否有效？",
    "盗窃他人财物可能承担什么法律责任？",
    "股东是否有权查阅公司会计账簿？",
    "商家规定商品一经售出概不退换是否合法？",
    "公司这样做合法吗？",
    "今天天气怎么样？",
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

    print("\n========== 多轮调度测试 ==========")

    messages = [
        {
            "role": "user",
            "content": "劳动合同必须签书面的吗？"
        },
        {
            "role": "assistant",
            "content": "一般情况下，用人单位与劳动者建立劳动关系，应当订立书面劳动合同。"
        },
        {
            "role": "user",
            "content": "那如果公司一直没签怎么办？"
        }
    ]

    result = scheduler.chat(messages)

    print("\n调用是否成功：", result["success"])

    print("\n调度步骤：")
    for step in result["steps"]:
        print("-", step)

    print("\n当前问题：")
    print(result["question"])

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