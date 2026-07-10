# -*- coding: utf-8 -*-
"""
test_embedding.py
======================================================
作用：验证 Python 能否成功调用本地 Ollama 生成文本向量。
这是后续所有工作（build_index.py / search.py）的前提，必须先跑通这个脚本。

运行前请确认：
1. Ollama 服务已经在本地启动（一般是命令行运行 `ollama serve`，
   或者安装后系统已经自动把它作为后台服务启动了）
2. 已经执行过 `ollama pull nomic-embed-text` 拉取向量模型（昨天已装好）
3. 已经安装 Python 库：pip install ollama numpy

运行方式：
    python embedding/test_embedding.py
======================================================
"""

import sys
import numpy as np

try:
    import ollama
except ImportError:
    print("[错误] 没有安装 ollama 库，请先运行：pip install ollama")
    sys.exit(1)

from config import EMBED_MODEL


def test_single_embedding():
    """测试：给一句话生成向量，检查是否成功、维度是否正常"""
    sample_text = "试用期最长不得超过六个月。"

    print(f"[1/3] 使用模型: {EMBED_MODEL}")
    print(f"[2/3] 测试文本: {sample_text}")

    try:
        response = ollama.embeddings(model=EMBED_MODEL, prompt=sample_text)
    except Exception as e:
        print("\n[失败] 调用 Ollama 生成向量时出错。常见原因排查：")
        print("  1. Ollama 服务没有启动 —— 请在终端运行: ollama serve")
        print(f"  2. 模型 {EMBED_MODEL} 没有拉取 —— 请运行: ollama pull {EMBED_MODEL}")
        print("  3. 端口被占用或防火墙拦截了 11434 端口（Ollama 默认端口）")
        print(f"\n原始错误信息: {e}")
        sys.exit(1)

    vector = response.get("embedding")
    if not vector:
        print("[失败] 返回结果里没有 embedding 字段，返回内容如下：")
        print(response)
        sys.exit(1)

    vector = np.array(vector, dtype="float32")

    print("[3/3] 调用成功！")
    print(f"    向量维度: {vector.shape[0]}")
    print(f"    向量前5个数值: {vector[:5]}")
    print(f"    向量模长(L2 norm): {np.linalg.norm(vector):.4f}")

    return vector


def test_batch_consistency():
    """测试：同一句话生成两次向量，维度应该一致（顺便检查稳定性）"""
    text = "劳动合同应当以书面形式订立。"
    v1 = np.array(ollama.embeddings(model=EMBED_MODEL, prompt=text)["embedding"])
    v2 = np.array(ollama.embeddings(model=EMBED_MODEL, prompt=text)["embedding"])

    if v1.shape != v2.shape:
        print("[警告] 两次调用返回的向量维度不一致，请检查模型是否正常")
    else:
        print(f"\n[额外测试] 两次调用维度一致: {v1.shape[0]} 维，测试通过。")


if __name__ == "__main__":
    print("=" * 50)
    print("Ollama 向量生成 - 连通性测试")
    print("=" * 50)
    test_single_embedding()
    test_batch_consistency()
    print("\n✅ 全部测试通过，可以进入下一步：build_index.py")
