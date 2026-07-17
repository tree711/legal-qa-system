from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from agent import RetrievalAgent, SummaryAgent


TEST_CASES = [
    ("劳动法", "劳动合同试用期最长可以约定多久？"),
    # ("劳动法", "劳动合同期限不满三个月，可以约定试用期吗？"),
    # ("劳动法", "用人单位违法延长试用期需要承担什么责任？"),
    # ("民法", "借款合同一定要采用书面形式吗？"),
    # ("民法", "未成年人签订的合同是否有效？"),
    # ("刑法", "盗窃他人财物可能承担什么法律责任？"),
    # ("公司法", "股东是否有权查阅公司会计账簿？"),
    # ("消费者权益法", "商家规定商品一经售出概不退换是否合法？"),
    # ("模糊问题", "公司这样做合法吗？"),
    # ("非法律问题", "今天天气怎么样？"),
]


def main() -> None:
    retrieval_agent = RetrievalAgent()
    summary_agent = SummaryAgent()
    records = []

    for index, (category, question) in enumerate(TEST_CASES, start=1):
        print("=" * 70)
        print(f"[{index}/10] {category}：{question}")

        retrieval_result = retrieval_agent.retrieve(question)
        summary_result = summary_agent.summarize(retrieval_result)

        print("Retrieval 状态：", retrieval_result.get("status"))
        print("说明：", retrieval_result.get("message"))
        print("可信结果数：", len(retrieval_result.get("trusted_results", [])))
        print("参考结果数：", len(retrieval_result.get("reference_results", [])))
        print("Summary 状态：", summary_result.get("status"))
        print("摘要：")
        print(summary_result.get("summary", ""))

        records.append(
            {
                "index": index,
                "category": category,
                "question": question,
                "retrieval_result": retrieval_result,
                "summary_result": summary_result,
            }
        )

    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"agent_manual_test_{timestamp}.json"
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 70)
    print(f"测试完成，原始结果已保存到：{output_path}")


if __name__ == "__main__":
    main()
