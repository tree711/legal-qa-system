# -*- coding: utf-8 -*-
"""
build_index.py
======================================================
作用：读取 D 同学清洗好的法律文本数据，逐条调用 Ollama 生成向量，
      构建 FAISS 索引并保存到磁盘，供 search.py 检索使用。

【重要】目前数据文件还没准备好，脚本会先检查文件是否存在。
        等 D 同学交付数据后，把文件放到 config.py 里 CLEANED_DATA_PATH
        指定的路径（默认是 data/cleaned_articles.json），再运行本脚本。

【数据格式约定】——请提前同步给 D 同学——
cleaned_articles.json 应该是一个 JSON 数组，每一项是一条法律条文，格式如下：

[
  {
    "law_name": "中华人民共和国劳动合同法",   // 法律名称，必填
    "article_no": "第十九条",                // 条文编号，必填
    "content": "劳动合同期限三个月以上不满一年的，试用期不得超过一个月……", // 条文正文，必填
    "chapter": "第二章 劳动合同的订立",        // 所属章节，选填
    "source_url": "https://www.pkulaw.com/...", // 原始来源链接，选填
    "id": "law_civil_labor_019"               // 唯一ID，选填（不填会自动生成）
  },
  ...
]

如果字段名不一样（比如 D 同学用的是 "title" 而不是 "law_name"），
只需要改下面 load_articles() 函数里的字段映射即可，不用改其他逻辑。

运行方式：
    python embedding/build_index.py
======================================================
"""

import os
import sys
import json
import time

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
    CLEANED_DATA_PATH,
    INDEX_DIR,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    DOC_PREFIX,
)


def check_data_ready():
    """检查 D 同学的数据文件是否已经交付"""
    if not os.path.exists(CLEANED_DATA_PATH):
        print("[提示] 还没有找到清洗后的数据文件，暂时无法构建索引。")
        print(f"       期望路径: {CLEANED_DATA_PATH}")
        print("       等 D 同学交付数据后，把文件放到上面这个路径，再重新运行本脚本。")
        print("       （代码框架已经准备好，数据到位后可以直接跑）")
        sys.exit(0)


def load_articles():
    """读取并校验清洗后的法律条文数据"""
    with open(CLEANED_DATA_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if not isinstance(raw_data, list):
        print("[错误] 数据文件格式不对，最外层应该是一个 JSON 数组 [...]")
        sys.exit(1)

    articles = []
    for i, item in enumerate(raw_data):
        # 字段映射：如果 D 同学的字段名不一样，改这里就行
        law_name = item.get("law_name") or item.get("title") or ""
        article_no = item.get("article_no") or item.get("article") or ""
        content = item.get("content") or item.get("text") or ""

        if not content:
            print(f"[跳过] 第 {i} 条数据缺少 content 字段，已跳过")
            continue

        articles.append({
            "id": item.get("id", f"article_{i}"),
            "law_name": law_name,
            "article_no": article_no,
            "content": content,
            "chapter": item.get("chapter", ""),
            "source_url": item.get("source_url", ""),
        })

    print(f"[数据加载] 共读取到 {len(raw_data)} 条原始数据，有效条文 {len(articles)} 条")
    return articles


def build_embed_text(article):
    """
    拼接用于生成向量的文本。
    把法律名称 + 条文号 拼进去，能让检索时更容易匹配到"哪部法律第几条"，
    而不仅仅是内容语义。
    """
    parts = [article["law_name"], article["article_no"], article["content"]]
    text = " ".join(p for p in parts if p)
    # 部分模型（如 nomic-embed-text 系列）要求文档文本加 "search_document: " 前缀
    # bge-m3 不需要，DOC_PREFIX 默认是空字符串
    return DOC_PREFIX + text


def embed_articles(articles, checkpoint_every=50):
    """逐条调用 Ollama 生成向量，返回 (向量矩阵, 元数据列表)"""
    vectors = []
    metadata = []
    total = len(articles)
    start_time = time.time()

    for i, article in enumerate(articles):
        text = build_embed_text(article)
        try:
            response = ollama.embeddings(model=EMBED_MODEL, prompt=text)
            vector = response["embedding"]
        except Exception as e:
            print(f"[警告] 第 {i+1}/{total} 条生成向量失败，已跳过: {e}")
            continue

        vectors.append(vector)
        metadata.append(article)

        if (i + 1) % checkpoint_every == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            print(f"  进度: {i+1}/{total}  已用时 {elapsed:.1f}s")

    vectors = np.array(vectors, dtype="float32")
    return vectors, metadata


def build_faiss_index(vectors):
    """
    构建 FAISS 索引。
    这里用 IndexFlatIP（内积）配合向量归一化 = 余弦相似度检索，
    对法律文本这种"语义相似"场景比较合适，且数据量不大时无需近似索引。
    """
    # 归一化，使内积等价于余弦相似度
    faiss.normalize_L2(vectors)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    print(f"[索引构建] 向量维度: {dim}, 索引中条文数量: {index.ntotal}")
    return index


def save_index(index, metadata):
    os.makedirs(INDEX_DIR, exist_ok=True)

    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"[保存完成] FAISS 索引: {FAISS_INDEX_PATH}")
    print(f"[保存完成] 元数据: {METADATA_PATH}")


def main():
    print("=" * 50)
    print("构建法律条文 FAISS 索引")
    print("=" * 50)

    check_data_ready()
    articles = load_articles()

    if not articles:
        print("[错误] 没有可用的法律条文数据，请检查数据文件内容")
        sys.exit(1)

    print(f"\n开始生成向量，共 {len(articles)} 条，模型: {EMBED_MODEL}")
    vectors, metadata = embed_articles(articles)

    if len(vectors) == 0:
        print("[错误] 没有成功生成任何向量，请检查 Ollama 服务是否正常")
        sys.exit(1)

    index = build_faiss_index(vectors)
    save_index(index, metadata)

    print("\n✅ 索引构建完成，可以进入下一步：search.py 测试检索效果")


if __name__ == "__main__":
    main()