from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

import requests


@dataclass
class LawResult:
    law_name: str
    article_no: str
    content: str
    chapter: str
    source_url: str
    score: float
    trusted: bool


class RetrievalAgent:
    """调用组长提供的 POST /search 接口并标准化返回结果。"""

    def __init__(
        self,
        base_url: str = "http://192.20.10.2:8000",
        score_threshold: float = 0.6,
        timeout: int = 30,
        search_handler: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.search_url = f"{base_url.rstrip('/')}/search"
        self.score_threshold = score_threshold
        self.timeout = timeout
        self.search_handler = search_handler

    def retrieve(self, question: str) -> dict[str, Any]:
        question = (question or "").strip()
        if not question:
            return self._error_result("", "问题不能为空。")

        if self.search_handler is not None:
            try:
                data = self.search_handler(question)
            except Exception as exc:
                return self._error_result(question, f"本地检索调用失败：{exc}")
            return self._normalize_response(question, data)

        try:
            response = requests.post(
                self.search_url,
                json={"query": question},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout:
            return self._error_result(question, "调用 /search 接口超时。")
        except requests.ConnectionError:
            return self._error_result(
                question,
                "无法连接 API 服务，请确认服务已启动、地址正确且设备处于同一局域网。",
            )
        except requests.HTTPError:
            return self._error_result(
                question,
                f"/search 返回 HTTP {response.status_code}：{response.text}",
            )
        except requests.RequestException as exc:
            return self._error_result(question, f"请求接口失败：{exc}")

        try:
            data = response.json()
        except ValueError:
            return self._error_result(question, "接口返回内容不是合法 JSON。")

        return self._normalize_response(question, data)

    def _normalize_response(self, question: str, data: dict[str, Any]) -> dict[str, Any]:
        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            return self._error_result(question, "接口字段 results 不是列表。")

        results: list[dict[str, Any]] = []
        trusted_results: list[dict[str, Any]] = []
        reference_results: list[dict[str, Any]] = []

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            try:
                score = float(item.get("score", 0))
            except (TypeError, ValueError):
                score = 0.0

            result = LawResult(
                law_name=str(item.get("law_name", "未知法规")),
                article_no=str(item.get("article_no", "")),
                content=str(item.get("content", "")),
                chapter=str(item.get("chapter", "")),
                source_url=str(item.get("source_url", "")),
                score=score,
                trusted=score >= self.score_threshold,
            )
            normalized = asdict(result)
            results.append(normalized)

            if result.trusted:
                trusted_results.append(normalized)
            else:
                reference_results.append(normalized)

        if not results:
            return {
                "agent": "RetrievalAgent",
                "status": "empty",
                "question": data.get("query", question),
                "score_threshold": self.score_threshold,
                "results": [],
                "trusted_results": [],
                "reference_results": [],
                "message": "未检索到相关法律条文。",
            }

        return {
            "agent": "RetrievalAgent",
            "status": "success",
            "question": data.get("query", question),
            "score_threshold": self.score_threshold,
            "results": results,
            "trusted_results": trusted_results,
            "reference_results": reference_results,
            "message": (
                f"共检索到 {len(results)} 条法条，其中 "
                f"{len(trusted_results)} 条 score 不低于 {self.score_threshold}。"
            ),
        }

    def format_references(self, retrieval_result: dict[str, Any]) -> str:
        """把结果格式化为可直接传给其他 Agent 或打印查看的文本。"""
        selected = retrieval_result.get("trusted_results") or retrieval_result.get(
            "reference_results", []
        )
        if not selected:
            return "未检索到相关法律条文。"

        blocks = []
        for index, item in enumerate(selected, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"【法条{index}】",
                        f"法规名称：{item.get('law_name', '')}",
                        f"条文编号：{item.get('article_no', '')}",
                        f"所属章节：{item.get('chapter', '')}",
                        f"法条内容：{item.get('content', '')}",
                        f"相关度：{float(item.get('score', 0)):.4f}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _error_result(question: str, message: str) -> dict[str, Any]:
        return {
            "agent": "RetrievalAgent",
            "status": "error",
            "question": question,
            "results": [],
            "trusted_results": [],
            "reference_results": [],
            "message": message,
        }
