"""针对 /chat 统一 Agent 链路的轻量回归测试。

输入 JSON 的每一项至少包含 question、expected_answer、note；可选 messages 和 use_rag。
逐项调用 POST /chat，并写出可直接提交/人工复核的 JSON 结果。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 /chat 回归测试并生成 JSON 结果")
    parser.add_argument("--input", default="data/test/chat_regression_cases.json")
    parser.add_argument("--output", default="data/test/chat_regression_results.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    cases = load_cases(Path(args.input))
    output_path = Path(args.output)
    results: list[dict] = []

    for index, case in enumerate(cases, start=1):
        messages = case.get("messages") or [{"role": "user", "content": case["question"]}]
        use_rag = bool(case.get("use_rag", True))
        print(f"[{index}/{len(cases)}] {case['question']}")
        started = time.time()
        try:
            response = requests.post(
                f"{args.base_url.rstrip('/')}/chat",
                json={"messages": messages, "top_k": args.top_k, "use_rag": use_rag},
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()
            references = data.get("references", [])
            steps = data.get("steps", [])
            note = (
                f"接口成功；用时={data.get('elapsed_seconds', time.time() - started):.2f}s；"
                f"引用数={len(references)}；low_confidence={data.get('low_confidence')}；"
                f"处理步骤={' | '.join(steps)}。原测试说明：{case.get('note', '')}"
            )
            result = {
                "id": case.get("id", str(index)),
                "question": case["question"],
                "expected_answer": case["expected_answer"],
                "model_output": data.get("answer", ""),
                "retrieved_text": "\n\n".join(
                    f"[{i}] {item.get('law_name', '')} {item.get('article_no', '')}\n{item.get('content', '')}"
                    for i, item in enumerate(references, start=1)
                ),
                "evaluation_note": note,
                "rewritten_question": data.get("rewritten_question"),
                "steps": steps,
                "references": references,
            }
        except requests.RequestException as exc:
            result = {
                "id": case.get("id", str(index)),
                "question": case["question"],
                "expected_answer": case["expected_answer"],
                "model_output": f"[调用失败] {exc}",
                "retrieved_text": "",
                "evaluation_note": f"/chat 回归测试失败：{exc}。原测试说明：{case.get('note', '')}",
            }
        results.append(result)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"完成：{len(results)} 条，结果已写入 {output_path}")


if __name__ == "__main__":
    main()
