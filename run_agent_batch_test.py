# -*- coding: utf-8 -*-
"""
run_agent_batch_test.py
======================================================
作用：读入 D 构造的测试问题集（至少包含 question / expected_answer 字段），
      依次调用 C 写好的 AgentScheduler（检索 Agent → 问答 Agent → 总结 Agent 的完整链路），
      把结果整理成和现有测试集一致的字段格式，写回 JSON 文件。

不修改 agent/ 下的任何代码，只是调用现成的 AgentScheduler。

【重要】这个脚本要放在项目根目录下运行（跟 agent/ 文件夹平级），
        因为要 `from agent.scheduler import AgentScheduler`。

运行方式：
    # 完整跑一遍（默认输入 data/test_samples_full.json，输出到同名 _agent_result.json）
    python run_agent_batch_test.py

    # 指定输入输出文件
    python run_agent_batch_test.py --input data/test_samples_full.json --output data/test_samples_agent_result.json

    # 先用少量题目跑通流程再跑全部（比如先测3条）
    python run_agent_batch_test.py --limit 3

    # 服务地址变了（换了网络/热点），用这个覆盖 AgentScheduler 默认的地址
    python run_agent_batch_test.py --base-url http://192.168.1.5:8000

【断点续测】
    脚本每测完一条就立刻把当前进度写回输出文件。如果中途被打断（网络断了、
    电脑重启等），直接重新运行同一条命令即可——脚本会跳过输出文件里已经
    有 model_output 内容的题目，只测还没测过的，不会重复消耗时间。
    如果想强制全部重测，加 --force 参数。
======================================================
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 保证能从项目根目录导入 agent 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from agent.scheduler import AgentScheduler
except ImportError as e:
    print(f"[错误] 无法导入 AgentScheduler，请确认本脚本放在项目根目录下运行。原始错误：{e}")
    sys.exit(1)


DEFAULT_BASE_URL = "http://172.20.10.2:8000"


def format_retrieved_text(references: list) -> str:
    """
    把 /rag 返回的 references 列表格式化成和现有测试集一致的 retrieved_text 字符串：
    "[1] 法规名 条文号；相关度=0.xxxx\n条文内容\n\n[2] ..."
    """
    if not references:
        return ""

    blocks = []
    for i, ref in enumerate(references, start=1):
        title = " ".join(
            p for p in (ref.get("law_name", ""), ref.get("article_no", "")) if p
        )
        try:
            score = float(ref.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        blocks.append(f"[{i}] {title}；相关度={score:.4f}\n{ref.get('content', '')}")

    return "\n\n".join(blocks)


def build_evaluation_note(result: dict, previous_note: str) -> str:
    """
    自动生成一段接口层面的诊断信息，拼在最前面；
    D 之前写好的评分要点（如果有）保留在后面的"原评价要点"里，不丢失；
    "回答评价"这一项留空，等人工填写。
    """
    if not result.get("success"):
        diag = f"Agent 调度测试失败。错误信息：{result.get('error', '未知错误')}。"
    else:
        raw = result.get("raw", {}) or {}
        references = result.get("references", []) or []
        low_confidence = raw.get("low_confidence")

        retrieval_result = result.get("retrieval_result", {}) or {}
        retrieval_status = retrieval_result.get("status", "未知")

        summary_result = result.get("summary_result", {}) or {}
        summary_status = summary_result.get("status", "未知")

        if references:
            top1 = references[0]
            top1_desc = (
                f"{top1.get('law_name', '')} {top1.get('article_no', '')}"
                f"（相关度={float(top1.get('score', 0)):.4f}）"
            )
        else:
            top1_desc = "无"

        diag = (
            f"Agent 调度测试完成。RetrievalAgent 状态={retrieval_status}；"
            f"SummaryAgent 状态={summary_status}；"
            f"QAAgent 检索到 {len(references)} 条法条；top1={top1_desc}；"
            f"low_confidence={low_confidence}。"
            f" 回答评价：[请人工填写：准确/部分正确/错误]。"
        )

    previous_note = (previous_note or "").strip()
    if previous_note:
        # 避免重复累加：如果之前已经跑过一次自动诊断，只保留最早的"原评价要点"部分
        if "原评价要点：" in previous_note:
            previous_note = previous_note.split("原评价要点：", 1)[1]
            previous_note = "原评价要点：" + previous_note
        else:
            previous_note = f"原评价要点：{previous_note}"
        return f"{diag} {previous_note}"

    return diag


def load_items(input_path: Path) -> list:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print("[错误] 输入文件最外层必须是一个 JSON 数组")
        sys.exit(1)
    return data


def save_items(output_path: Path, items: list) -> None:
    # 先写临时文件再替换，避免写到一半程序崩溃导致文件损坏
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    tmp_path.replace(output_path)


def main():
    parser = argparse.ArgumentParser(description="批量跑 AgentScheduler 完整链路测试")
    parser.add_argument("--input", default="data/test_samples_full.json", help="输入的测试问题集路径")
    parser.add_argument("--output", default=None, help="输出文件路径，默认在输入文件名后加 _agent_result")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="组长服务的地址")
    parser.add_argument("--top-k", type=int, default=5, help="传给 AgentScheduler 的 top_k")
    parser.add_argument("--limit", type=int, default=None, help="只测前 N 条，用于先小范围验证脚本本身没问题")
    parser.add_argument("--force", action="store_true", help="强制重测所有题目，忽略已有结果")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[错误] 找不到输入文件：{input_path}")
        sys.exit(1)

    output_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_agent_result" + input_path.suffix
    )

    # 如果输出文件已经存在（比如上次跑到一半），从这里继续，而不是从输入文件重新开始
    if output_path.exists() and not args.force:
        items = load_items(output_path)
        print(f"[续测] 发现已有输出文件 {output_path}，将在此基础上继续。")
    else:
        items = load_items(input_path)

    if args.limit:
        items = items[: args.limit]

    print(f"[初始化] 服务地址：{args.base_url}，共 {len(items)} 条问题")
    scheduler = AgentScheduler(base_url=args.base_url, top_k=args.top_k)

    total = len(items)
    todo_count = sum(1 for it in items if args.force or not (it.get("model_output") or "").strip())
    print(f"[计划] 共 {total} 条，其中待测 {todo_count} 条（已测过的会跳过，除非加 --force）")

    done = 0
    start_time = time.time()

    for idx, item in enumerate(items):
        question = item.get("question", "")
        if not question:
            continue

        already_done = (item.get("model_output") or "").strip()
        if already_done and not args.force:
            continue

        done += 1
        print(f"\n[{idx + 1}/{total}] 测试问题：{question}")

        t0 = time.time()
        try:
            result = scheduler.run(question)
        except Exception as exc:
            # 调度器本身理论上不会抛异常（内部已经做了兜底），
            # 这里再兜一层，防止个别题目的意外报错中断整批测试
            print(f"    [异常] 调度器抛出未捕获的异常：{exc}")
            result = {
                "success": False,
                "final_answer": "",
                "references": [],
                "retrieval_result": {},
                "summary_result": {},
                "error": f"调度器抛出未捕获异常：{exc}",
            }

        elapsed = time.time() - t0
        print(f"    完成，用时 {elapsed:.1f}s，成功={result.get('success')}")

        item["retrieved_text"] = format_retrieved_text(result.get("references", []))
        item["model_output"] = result.get("final_answer", "") or f"[调度失败] {result.get('error', '')}"
        item["evaluation_note"] = build_evaluation_note(result, item.get("evaluation_note", ""))

        # 每测完一条就立刻存盘，避免中途中断丢失已测结果
        save_items(output_path, items)

    total_elapsed = time.time() - start_time
    print(f"\n✅ 本次共测试 {done} 条，用时 {total_elapsed / 60:.1f} 分钟")
    print(f"结果已保存到：{output_path}")


if __name__ == "__main__":
    main()