#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 3 批量接口测试脚本。

功能：
1. 调用 GET /health 检查服务；
2. 对指定数量的样本调用 POST /search 和 POST /rag；
3. 将检索法条写入 retrieved_text；
4. 将系统回答写入 model_output；
5. 可选择交互式人工评价 evaluation_note；
6. 每处理一条立即保存，避免中途退出丢失结果。

示例：
python data/test/day3_run_tests.py ^
  --base-url http://127.0.0.1:8000 ^
  --input data/test/test_samples_part2.json ^
  --count 20 ^
  --review
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    req = Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接接口：{exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("接口返回的不是合法 JSON") from exc


def format_articles(results: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, item in enumerate(results, start=1):
        law_name = str(item.get("law_name", "")).strip()
        article_no = str(item.get("article_no", "")).strip()
        content = str(item.get("content", "")).strip()
        score = item.get("score")
        score_text = f"；相关度={score:.4f}" if isinstance(score, (int, float)) else ""
        title = " ".join(x for x in (law_name, article_no) if x)
        blocks.append(f"[{index}] {title}{score_text}\n{content}".strip())
    return "\n\n".join(blocks)


def save_samples(path: Path, samples: list[dict[str, Any]]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def review_sample(sample: dict[str, Any], api_note: str) -> None:
    print("\n" + "=" * 88)
    print("【问题】")
    print(sample["question"])
    print("\n【标准答案】")
    print(sample["expected_answer"])
    print("\n【系统回答】")
    print(sample["model_output"])
    print("\n【检索结果】")
    print(sample["retrieved_text"][:3000] or "无")
    print("\n请选择评价：")
    print("1 = 准确；2 = 基本准确；3 = 部分正确；4 = 错误；5 = 暂不评价")

    mapping = {
        "1": "准确",
        "2": "基本准确",
        "3": "部分正确",
        "4": "错误",
        "5": "待人工复核",
    }
    while True:
        choice = input("评价编号：").strip()
        if choice in mapping:
            break
        print("请输入 1、2、3、4 或 5。")

    detail = input("补充说明（可直接回车）：").strip()
    old_note = str(sample.get("evaluation_note", "")).strip()
    parts = [
        f"接口测试完成。{api_note}",
        f"回答评价：{mapping[choice]}。",
    ]
    if detail:
        parts.append(f"人工说明：{detail}")
    if old_note:
        parts.append(f"原评价要点：{old_note}")
    sample["evaluation_note"] = " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="批量调用 /search 和 /rag 完成 Day 3 测试")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--input", default="data/test/test_samples_part2.json")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--start", type=int, default=0, help="从第几条开始，0 表示第一条")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--review", action="store_true", help="每条接口返回后进行人工评价")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="重新测试已有 model_output 的样本；默认跳过已有结果",
    )
    args = parser.parse_args()

    if args.count < 1 or args.start < 0 or not 1 <= args.top_k <= 20:
        parser.error("count 必须大于0，start不能为负数，top-k应为1至20")

    path = Path(args.input)
    if not path.exists():
        print(f"找不到输入文件：{path}", file=sys.stderr)
        return 2

    try:
        samples = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取 JSON 失败：{exc}", file=sys.stderr)
        return 2

    if not isinstance(samples, list):
        print("输入 JSON 的最外层必须是数组。", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    try:
        health = request_json("GET", f"{base_url}/health", timeout=20)
    except RuntimeError as exc:
        print(f"健康检查失败：{exc}", file=sys.stderr)
        print("请确认服务已启动、IP和端口正确，并能在浏览器打开 /docs。", file=sys.stderr)
        return 3

    if health.get("status") != "ok":
        print(f"健康检查返回异常：{health}", file=sys.stderr)
        return 3

    print(f"服务正常：{base_url}")
    print(f"准备测试：从第 {args.start + 1} 条起，最多处理 {args.count} 条")

    processed = 0
    failures = 0
    for index in range(args.start, len(samples)):
        if processed >= args.count:
            break

        sample = samples[index]
        question = str(sample.get("question", "")).strip()
        if not question:
            print(f"[{index + 1}] 跳过：question 为空")
            continue
        if sample.get("model_output") and not args.overwrite:
            print(f"[{index + 1}] 跳过：已有 model_output")
            continue

        print(f"\n[{index + 1}/{len(samples)}] {question}")
        try:
            search_data = request_json(
                "POST",
                f"{base_url}/search",
                {"query": question, "top_k": args.top_k},
                timeout=args.timeout,
            )
            search_results = search_data.get("results", [])
            if not isinstance(search_results, list):
                raise RuntimeError("/search 返回的 results 不是数组")

            rag_data = request_json(
                "POST",
                f"{base_url}/rag",
                {"prompt": question, "top_k": args.top_k},
                timeout=args.timeout,
            )
            answer = str(rag_data.get("answer", "")).strip()
            references = rag_data.get("references", [])
            if not answer:
                raise RuntimeError("/rag 返回的 answer 为空")

            sample["retrieved_text"] = format_articles(search_results)
            sample["model_output"] = answer

            low_confidence = bool(rag_data.get("low_confidence", False))
            top1 = search_results[0] if search_results else {}
            top1_title = " ".join(
                str(top1.get(key, "")).strip()
                for key in ("law_name", "article_no")
                if str(top1.get(key, "")).strip()
            )
            api_note = (
                f"检索返回{len(search_results)}条；"
                f"top1={top1_title or '无'}；"
                f"low_confidence={low_confidence}。"
            )

            if args.review:
                review_sample(sample, api_note)
            else:
                old_note = str(sample.get("evaluation_note", "")).strip()
                sample["evaluation_note"] = (
                    f"接口测试完成。{api_note} 回答评价：待人工复核。"
                    + (f" 原评价要点：{old_note}" if old_note else "")
                )

            processed += 1
            save_samples(path, samples)
            print("已保存。")
            time.sleep(0.2)

        except RuntimeError as exc:
            failures += 1
            old_note = str(sample.get("evaluation_note", "")).strip()
            sample["evaluation_note"] = (
                f"接口测试失败：{exc}。"
                + (f" 原评价要点：{old_note}" if old_note else "")
            )
            save_samples(path, samples)
            print(f"失败：{exc}", file=sys.stderr)

    print("\n" + "=" * 60)
    print(f"成功处理：{processed} 条")
    print(f"失败：{failures} 条")
    print(f"结果文件：{path}")
    tested = sum(1 for item in samples if str(item.get("model_output", "")).strip())
    print(f"当前已有 model_output：{tested}/{len(samples)} 条")

    return 0 if processed > 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
