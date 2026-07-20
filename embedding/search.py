# -*- coding: utf-8 -*-
"""
search.py
======================================================
作用：输入一个法律问题，从已构建好的 FAISS 索引中检索最相关的法律条文。

前置条件：
    必须先运行 build_index.py 成功生成索引文件
    （config.py 中 FAISS_INDEX_PATH / METADATA_PATH 指向的文件要存在）

运行方式：
    1. 交互模式（推荐，可以连续输入多个问题测试效果）：
       python embedding/search.py

    2. 命令行单次查询模式：
       python embedding/search.py "试用期最长可以约定多久？"

    3. 作为模块被后续 RAG 脚本调用：
       from search import search
       results = search("试用期最长可以约定多久？", top_k=5)
======================================================
"""

import sys
import json
import os

import numpy as np

try:
    import ollama
except ImportError:
    print("[错误] 没有安装 ollama 库，请先运行：pip install ollama")
    sys.exit(1)

try:
    import faiss
except ImportError:
    print("[错误] 没有安装 faiss-cpu 库，请先运行：pip install faiss-cpu")
    sys.exit(1)

try:
    # 被 api/main.py 以 `from embedding.search import ...` 方式导入时走这里
    from embedding.config import (
        EMBED_MODEL,
        FAISS_INDEX_PATH,
        METADATA_PATH,
        DEFAULT_TOP_K,
        QUERY_PREFIX,
    )
except ImportError:
    # 直接运行 `python embedding/search.py` 时走这里
    from config import (
        EMBED_MODEL,
        FAISS_INDEX_PATH,
        METADATA_PATH,
        DEFAULT_TOP_K,
        QUERY_PREFIX,
    )


class IndexNotReadyError(RuntimeError):
    """索引文件还没构建好时抛出。CLI 模式下会被 main() 捕获并友好提示；
    被 api/main.py 当模块导入调用时，会被接口捕获并转成 HTTP 503 返回。"""
    pass


def _article_no(item: dict) -> str:
    """统一取得条号，便于为少数高风险法律问题做规则重排序。"""
    return str(item.get("article_no", "")).replace(" ", "")


def rerank_legal_articles(query: str, articles: list[dict]) -> list[dict]:
    """在向量召回结果内，为决定性法条提供轻量、可解释的重排序。

    这不是替代向量检索，而是避免通用条文（例如“试用期最长六个月”）
    压过问题直接要求适用的特别条文。只影响已经进入候选集的结果。
    """
    query = (query or "").replace(" ", "")
    targets: set[str] = set()

    if "合同" in query and ("何时成立" in query or ("要约" in query and "承诺" in query)):
        targets.add("第四百八十三条")
    if "书面劳动合同" in query and any(word in query for word in ("没签", "未签", "不签", "用工")):
        targets.update({"第十条", "第八十二条", "第十四条"})
    if any(word in query for word in ("拖欠工资", "拖欠劳动报酬", "未足额支付")):
        targets.update({"第三十条", "第三十八条", "第四十六条", "第八十五条"})

    if not targets:
        return articles

    def rank_key(item: dict) -> tuple[int, float]:
        # 目标法条优先；同一优先级内仍保留原始向量相似度的排序。
        is_target = _article_no(item) in targets
        return (1 if is_target else 0, float(item.get("score", 0)))

    return sorted(articles, key=rank_key, reverse=True)


class LegalSearcher:
    """
    封装检索逻辑，加载一次索引后可以反复调用 search()，
    避免每次查询都重新读取磁盘上的索引文件（尤其是索引变大之后会比较慢）。
    """

    def __init__(self):
        self._check_index_ready()
        print(f"[加载中] 正在加载 FAISS 索引: {FAISS_INDEX_PATH}")
        self.index = faiss.read_index(FAISS_INDEX_PATH)

        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        print(f"[加载完成] 索引中共有 {self.index.ntotal} 条法律条文")

    @staticmethod
    def _check_index_ready():
        missing = [p for p in (FAISS_INDEX_PATH, METADATA_PATH) if not os.path.exists(p)]
        if missing:
            lines = ["找不到索引文件，请先运行 build_index.py 构建索引："]
            lines += [f"    缺失: {p}" for p in missing]
            raise IndexNotReadyError("\n".join(lines))

    def embed_query(self, query: str) -> np.ndarray:
        """把用户问题转成向量，并做归一化（要和 build_index.py 里的处理方式保持一致）"""
        # 部分模型（如 nomic-embed-text 系列）要求查询文本加 "search_query: " 前缀
        # bge-m3 不需要，QUERY_PREFIX 默认是空字符串
        query = QUERY_PREFIX + query
        try:
            response = ollama.embeddings(model=EMBED_MODEL, prompt=query)
        except Exception as e:
            raise RuntimeError(
                f"调用 {EMBED_MODEL} 生成向量失败，请确认 Ollama 服务已启动。原始错误: {e}"
            ) from e

        vector = np.array([response["embedding"]], dtype="float32")
        faiss.normalize_L2(vector)
        return vector

    def search(self, query: str, top_k: int = DEFAULT_TOP_K):
        """
        检索最相关的 top_k 条法律条文。

        返回值：list[dict]，每个 dict 包含：
            law_name / article_no / content / chapter / source_url / score
        score 是余弦相似度，范围 [-1, 1]，越接近 1 越相关。
        """
        query_vector = self.embed_query(query)
        # 先召回较大的候选集，再做轻量重排序，避免决定性法条仅因排名略低而被截断。
        candidate_k = min(max(top_k * 6, 30), self.index.ntotal)
        scores, indices = self.index.search(query_vector, candidate_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # 索引里数量不足 top_k 时会出现 -1
                continue
            article = dict(self.metadata[idx])
            article["score"] = float(score)
            results.append(article)

        return rerank_legal_articles(query, results)[:top_k]


def print_results(query: str, results: list):
    print(f"\n问题: {query}")
    print("-" * 50)

    if not results:
        print("没有检索到相关条文。")
        return

    for rank, item in enumerate(results, start=1):
        print(f"[{rank}] 相关度: {item['score']:.4f}")
        title = " ".join(p for p in (item.get("law_name"), item.get("article_no")) if p)
        if title:
            print(f"    {title}")
        print(f"    {item['content']}")
        if item.get("source_url"):
            print(f"    来源: {item['source_url']}")
        print()


def interactive_mode(searcher: LegalSearcher):
    print("\n进入交互模式，输入法律问题进行检索（输入 exit 或 quit 退出）")
    while True:
        try:
            query = input("\n请输入问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if query.lower() in ("exit", "quit", ""):
            if query == "":
                continue
            print("已退出。")
            break

        try:
            results = searcher.search(query)
        except RuntimeError as e:
            print(f"[错误] {e}")
            continue
        print_results(query, results)


def main():
    try:
        searcher = LegalSearcher()
    except IndexNotReadyError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    if len(sys.argv) > 1:
        # 命令行单次查询模式：python search.py "问题内容"
        query = " ".join(sys.argv[1:])
        try:
            results = searcher.search(query)
        except RuntimeError as e:
            print(f"[错误] {e}")
            sys.exit(1)
        print_results(query, results)
    else:
        interactive_mode(searcher)


# 供其他脚本（比如后续 RAG 模块）直接调用的便捷函数
_default_searcher = None


def search(query: str, top_k: int = DEFAULT_TOP_K):
    """
    模块级别的便捷调用函数，内部会缓存 LegalSearcher 实例，
    避免每次调用都重新加载索引。用法：
        from search import search
        results = search("试用期最长多久？", top_k=3)
    """
    global _default_searcher
    if _default_searcher is None:
        _default_searcher = LegalSearcher()
    return _default_searcher.search(query, top_k=top_k)


if __name__ == "__main__":
    main()
