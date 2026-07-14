from __future__ import annotations

from typing import Any


class SummaryAgent:
    """对 RetrievalAgent 的法条结果做结构化摘要。"""

    def summarize(self, retrieval_result: dict[str, Any]) -> dict[str, Any]:
        question = retrieval_result.get("question", "")
        status = retrieval_result.get("status")

        if status == "error":
            return {
                "agent": "SummaryAgent",
                "status": "error",
                "question": question,
                "summary": "",
                "references": [],
                "message": retrieval_result.get("message", "检索失败。"),
            }

        selected = retrieval_result.get("trusted_results") or retrieval_result.get(
            "reference_results", []
        )

        if not selected:
            return {
                "agent": "SummaryAgent",
                "status": "empty",
                "question": question,
                "summary": "未找到可以用于总结的相关法律条文。",
                "references": [],
                "message": "没有检索结果。",
            }

        summary_lines = []
        references = []

        for index, item in enumerate(selected, start=1):
            law_name = item.get("law_name", "未知法规")
            article_no = item.get("article_no", "")
            content = item.get("content", "")
            score = float(item.get("score", 0))

            summary_lines.append(
                f"{index}. 《{law_name}》{article_no}：{content}"
            )
            references.append(
                {
                    "law_name": law_name,
                    "article_no": article_no,
                    "chapter": item.get("chapter", ""),
                    "source_url": item.get("source_url", ""),
                    "score": score,
                }
            )

        return {
            "agent": "SummaryAgent",
            "status": "success",
            "question": question,
            "summary": "\n".join(summary_lines),
            "references": references,
            "message": f"已根据 {len(selected)} 条法条完成结构化总结。",
        }
