import json

from agent import RetrievalAgent, SummaryAgent


def main() -> None:
    question = "消费者购买商品后享有哪些权利？"

    retrieval_agent = RetrievalAgent()
    summary_agent = SummaryAgent()

    retrieval_result = retrieval_agent.retrieve(question)

    print("=== RetrievalAgent 原始结果 ===")
    print(json.dumps(retrieval_result, ensure_ascii=False, indent=2))

    print("\n=== 格式化法条 ===")
    print(retrieval_agent.format_references(retrieval_result))

    summary_result = summary_agent.summarize(retrieval_result)

    print("\n=== SummaryAgent 结果 ===")
    print(json.dumps(summary_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
