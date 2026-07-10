# -*- coding: utf-8 -*-
"""
config.py
统一配置文件：所有脚本（test_embedding.py / build_index.py / search.py）共用这里的参数。
这样以后要换模型、换路径，只需要改这一个文件。
"""

import os

# ========== Ollama 模型配置 ==========
# 用于生成向量（embedding）的模型
# 【重要】原本用的 nomic-embed-text 对中文支持很差（该模型主要基于英文语料训练），
# 实测中文检索几乎文不对题，已换成 bge-m3（BAAI 出品，中文/多语言检索效果更好）。
# 换模型前请先执行: ollama pull bge-m3
# 注意：换模型后必须删除旧索引重新跑 build_index.py，
# 因为不同模型输出的向量维度不同、语义空间也不兼容，不能混用旧索引。
EMBED_MODEL = "bge-m3"

# 有些 embedding 模型（比如 nomic-embed-text 系列）要求给文本加任务前缀，
# 区分"这是被检索的文档"还是"这是用户的查询"，不加前缀会明显降低效果。
# bge-m3 不需要前缀，所以这里留空。
# 如果以后换回 nomic-embed-text / nomic-embed-text-v2-moe，把下面两行改成：
#   QUERY_PREFIX = "search_query: "
#   DOC_PREFIX = "search_document: "
QUERY_PREFIX = ""
DOC_PREFIX = ""

# 用于对话生成的模型（第2周 RAG 阶段会用到，这里先留好配置）
CHAT_MODEL = "qwen2:7b"



# ========== 路径配置 ==========
# 项目根目录 = 本文件所在目录的上一级
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# D 同学清洗好之后交付的数据文件（JSON 格式，见 build_index.py 顶部的格式说明）
# 等数据到位后，把文件放到这个路径，或者改这里的路径指向实际位置
CLEANED_DATA_PATH = os.path.join(BASE_DIR, "data", "clean", "cleaned_articles.json")

# FAISS 索引和元数据的保存位置
INDEX_DIR = os.path.join(BASE_DIR, "data", "index")
FAISS_INDEX_PATH = os.path.join(INDEX_DIR, "law_index.faiss")
METADATA_PATH = os.path.join(INDEX_DIR, "law_metadata.json")


# ========== 检索配置 ==========
# 默认返回最相关的几条法律条文
DEFAULT_TOP_K = 5