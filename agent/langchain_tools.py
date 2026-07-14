from __future__ import annotations

import json

from langchain_core.tools import tool

from .retrieval_agent import RetrievalAgent
from .summary_agent import SummaryAgent


_retrieval_agent = RetrievalAgent()
_summary_agent = SummaryAgent()


@tool
def legal_search(question: str) -> str:
    """检索与用户法律问题相关的法律条文。"""
    result = _retrieval_agent.retrieve(question)
    return json.dumps(result, ensure_ascii=False)


@tool
def summarize_legal_results(retrieval_result_json: str) -> str:
    """对 legal_search 返回的 JSON 检索结果进行结构化总结。"""
    retrieval_result = json.loads(retrieval_result_json)
    result = _summary_agent.summarize(retrieval_result)
    return json.dumps(result, ensure_ascii=False)
