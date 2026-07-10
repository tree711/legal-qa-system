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

from config import (
    EMBED_MODEL,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    DEFAULT_TOP_K,
    QUERY_PREFIX,
)


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
            print("[错误] 找不到索引文件，请先运行 build_index.py 构建索引：")
            for p in missing:
                print(f"    缺失: {p}")
            sys.exit(1)

    def embed_query(self, query: str) -> np.ndarray:
        """把用户问题转成向量，并做归一化（要和 build_index.py 里的处理方式保持一致）"""
        # 部分模型（如 nomic-embed-text 系列）要求查询文本加 "search_query: " 前缀
        # bge-m3 不需要，QUERY_PREFIX 默认是空字符串
        query = QUERY_PREFIX + query
        try:
            response = ollama.embeddings(model=EMBED_MODEL, prompt=query)
        except Exception as e:
            print("[错误] 调用 Ollama 生成向量失败，请确认 Ollama 服务已启动。")
            print(f"原始错误: {e}")
            sys.exit(1)

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
        scores, indices = self.index.search(query_vector, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # 索引里数量不足 top_k 时会出现 -1
                continue
            article = dict(self.metadata[idx])
            article["score"] = float(score)
            results.append(article)

        return results


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

        results = searcher.search(query)
        print_results(query, results)


def main():
    searcher = LegalSearcher()

    if len(sys.argv) > 1:
        # 命令行单次查询模式：python search.py "问题内容"
        query = " ".join(sys.argv[1:])
        results = searcher.search(query)
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