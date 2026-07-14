import requests


class QAAgent:
    """
    C 负责的问答 Agent。

    功能：
    1. 接收用户法律问题
    2. 调用组长提供的 POST /rag 接口
    3. 返回最终回答和引用法条
    """

    def __init__(self, base_url: str, top_k: int = 3):
        self.base_url = base_url.rstrip("/")
        self.top_k = top_k

    def answer(self, question: str) -> dict:
        url = f"{self.base_url}/rag"

        payload = {
            "prompt": question,
            "top_k": self.top_k
        }

        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "question": question,
                "answer": data.get("answer", ""),
                "references": data.get("references", []),
                "model": data.get("model", ""),
                "elapsed_seconds": data.get("elapsed_seconds", None),
                "raw": data
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "question": question,
                "answer": "",
                "references": [],
                "error": str(e)
            }


if __name__ == "__main__":
    agent = QAAgent("http://172.20.10.2:8000")

    while True:
        question = input("\n请输入法律问题，输入 q 退出：").strip()

        if question.lower() == "q":
            print("已退出 QAAgent 测试。")
            break

        if not question:
            print("问题不能为空，请重新输入。")
            continue

        result = agent.answer(question)

        print("\n调用是否成功：", result["success"])
        print("问题：", result["question"])
        print("回答：", result["answer"])
        print("引用法条：", result["references"])

        if not result["success"]:
            print("错误信息：", result["error"])