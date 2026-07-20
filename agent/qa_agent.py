# -*- coding: utf-8 -*-

import requests
from typing import Callable, Any


class QAAgent:
    """
    问答 Agent。

    已有能力：
    1. answer(question)：调用 /rag 接口，处理单轮问答

    新增能力：
    2. chat(messages)：调用 /chat 接口，处理多轮对话
    """

    def __init__(
        self, base_url: str, top_k: int = 3, timeout: int = 120,
        rag_handler: Callable[[str, int], dict[str, Any]] | None = None,
        chat_handler: Callable[[list[dict], int, str | None, dict | None], dict[str, Any]] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.top_k = top_k
        self.timeout = timeout
        self.rag_handler = rag_handler
        self.chat_handler = chat_handler

    def answer(self, question: str) -> dict:
        """
        单轮问答：调用 /rag。
        """
        question = (question or "").strip()

        if not question:
            return {
                "success": False,
                "question": question,
                "answer": "",
                "references": [],
                "error": "问题不能为空。"
            }

        if self.rag_handler is not None:
            try:
                data = self.rag_handler(question, self.top_k)
                return self._success_result(question, data)
            except Exception as exc:
                return {"success": False, "question": question, "answer": "", "references": [], "error": str(exc)}

        url = f"{self.base_url}/rag"

        payload = {
            "prompt": question,
            "top_k": self.top_k
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            return self._success_result(question, data)

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "question": question,
                "answer": "",
                "references": [],
                "error": str(e)
            }

    def chat(
        self, messages: list[dict], search_query: str | None = None,
        retrieval_result: dict | None = None,
    ) -> dict:
        """
        多轮问答：调用 /chat。

        messages 示例：
        [
            {"role": "user", "content": "劳动合同必须签书面的吗？"},
            {"role": "assistant", "content": "一般情况下应订立书面劳动合同。"},
            {"role": "user", "content": "那如果公司一直没签怎么办？"}
        ]
        """
        messages = self._normalize_messages(messages)

        if not messages:
            return {
                "success": False,
                "question": "",
                "messages": [],
                "answer": "",
                "references": [],
                "error": "messages 不能为空。"
            }

        current_question = self._get_last_user_message(messages)

        if not current_question:
            return {
                "success": False,
                "question": "",
                "messages": messages,
                "answer": "",
                "references": [],
                "error": "messages 中必须至少包含一条 user 消息。"
            }

        if self.chat_handler is not None:
            try:
                data = self.chat_handler(messages, self.top_k, search_query, retrieval_result)
                result = self._success_result(current_question, data)
                result["messages"] = data.get("messages", messages)
                return result
            except Exception as exc:
                return {"success": False, "question": current_question, "messages": messages, "answer": "", "references": [], "error": str(exc)}

        url = f"{self.base_url}/chat"

        payload = {
            "messages": messages,
            "top_k": self.top_k
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            result = self._success_result(current_question, data)
            result["messages"] = data.get("messages", messages)
            return result

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "question": current_question,
                "messages": messages,
                "answer": "",
                "references": [],
                "error": str(e)
            }

    @staticmethod
    def _success_result(question: str, data: dict) -> dict:
        return {
            "success": True,
            "question": question,
            "answer": data.get("answer", ""),
            "references": data.get("references", []),
            "model": data.get("model", ""),
            "elapsed_seconds": data.get("elapsed_seconds"),
            "low_confidence": data.get("low_confidence"),
            "raw": data,
        }

    @staticmethod
    def _normalize_messages(messages: list[dict]) -> list[dict]:
        """
        清洗 messages，避免格式不规范导致 /chat 接口报错。
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
        获取最后一条用户问题，用于记录当前轮问题。
        """
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content", "").strip():
                return msg["content"].strip()
        return ""


if __name__ == "__main__":
    agent = QAAgent("http://172.20.10.2:8000")

    messages = []

    print("QAAgent 多轮对话测试，输入 q 退出。")

    while True:
        question = input("\n请输入法律问题：").strip()

        if question.lower() == "q":
            print("已退出 QAAgent 测试。")
            break

        if not question:
            print("问题不能为空，请重新输入。")
            continue

        messages.append({
            "role": "user",
            "content": question
        })

        result = agent.chat(messages)

        print("\n调用是否成功：", result["success"])
        print("当前问题：", result.get("question", ""))
        print("回答：", result.get("answer", ""))
        print("引用法条：", result.get("references", []))

        if result["success"]:
            messages.append({
                "role": "assistant",
                "content": result.get("answer", "")
            })
        else:
            print("错误信息：", result.get("error", "未知错误"))