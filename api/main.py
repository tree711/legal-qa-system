# -*- coding: utf-8 -*-
"""
api/main.py
======================================================
给同组同学提供的 HTTP 接口。她们的轻薄本不用装 Ollama、不用装 faiss，
只需要能访问你这台机器的 IP + 端口，就能拿到大模型生成的回答。

今天完成的三件事：
① 安装 FastAPI + uvicorn（见 requirements.txt）
② /health 接口 —— 用来确认服务是否正常运行
③ generate_answer(prompt) 函数 —— 真正调用本地 qwen2:7b 生成回答
   （已经不是 Mock 了，直接走 ollama.chat）

运行方式：
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    或者直接: python api/main.py

跑起来之后，同组同学在浏览器或 Postman 里访问：
    http://<你的电脑局域网IP>:8000/health          确认服务活着
    http://<你的电脑局域网IP>:8000/docs             FastAPI 自带的交互式接口文档

【怎么查你的局域网 IP】
    Windows: 打开 cmd，运行 ipconfig，看"IPv4 地址"那一行（一般是 192.168.x.x）
    注意：同学的电脑要和你在同一个 WiFi/局域网下才能访问到。
======================================================
"""

import time
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import ollama

try:
    # 通过 `uvicorn api.main:app` 以包的方式导入时走这里
    from api.config import CHAT_MODEL, OLLAMA_HOST, GENERATE_TIMEOUT, HOST, PORT
except ImportError:
    # 通过 `python api/main.py` 直接运行脚本时走这里
    from config import CHAT_MODEL, OLLAMA_HOST, GENERATE_TIMEOUT, HOST, PORT

try:
    # 复用 embedding 模块已经写好的检索能力，今天不用重新造轮子。
    # 正常情况下（uvicorn api.main:app 从项目根目录启动）这行直接就能成功。
    from embedding.search import search as retrieve_articles, IndexNotReadyError
except ImportError:
    # 如果是 `python api/main.py` 直接运行脚本，项目根目录不在 sys.path 里，
    # 手动把项目根目录（api/ 的上一级）加进去再导入一次。
    import os as _os
    import sys as _sys
    _project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _project_root not in _sys.path:
        _sys.path.insert(0, _project_root)
    from embedding.search import search as retrieve_articles, IndexNotReadyError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("legal-qa-api")

app = FastAPI(
    title="法律问答系统 API",
    description="给同组同学调用的问答接口，封装了本地 Ollama 大模型",
    version="0.1.0",
)

# 开发阶段先允许所有来源跨域访问，方便同学用不同工具（浏览器/前端页面/Postman）调试。
# 后面如果要上线或者更严谨一点，再改成只允许指定的前端地址。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 用固定 host 的 ollama 客户端，避免依赖环境变量，行为更可控
# 加上 timeout，避免 httpx 默认超时（比较短）在模型生成较慢时把请求打断
_client = ollama.Client(host=OLLAMA_HOST, timeout=GENERATE_TIMEOUT)


# ========== 数据结构定义 ==========

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户输入的问题或提示词")
    system_prompt: str | None = Field(
        default=None,
        description="可选，系统提示词（比如后面做 RAG 时把检索到的法条塞进这里）",
    )


class GenerateResponse(BaseModel):
    answer: str
    model: str
    elapsed_seconds: float


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户输入的法律问题")
    top_k: int = Field(default=3, ge=1, le=20, description="返回最相关的几条法条，默认3条")


class ArticleResult(BaseModel):
    law_name: str = Field(default="", description="法律名称")
    article_no: str = Field(default="", description="条文编号")
    content: str = Field(default="", description="条文正文")
    chapter: str = Field(default="", description="所属章节")
    source_url: str = Field(default="", description="来源链接")
    score: float = Field(description="相关度得分（余弦相似度），越接近1越相关")


class SearchResponse(BaseModel):
    query: str
    results: list[ArticleResult]


class RagRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户输入的法律问题")
    top_k: int = Field(default=3, ge=1, le=20, description="检索并参考的法条数量，默认3条")


class RagResponse(BaseModel):
    answer: str
    references: list[ArticleResult]
    model: str
    elapsed_seconds: float
    low_confidence: bool = Field(
        description="检索到的法条相关度都偏低时为 True，提示这个回答可能不够可靠"
    )


# ========== 核心函数 ==========

def generate_answer(prompt: str, system_prompt: str | None = None) -> str:
    """
    调用本地 qwen2:7b 生成回答。

    这是 api/main.py 的核心函数，今天从 Mock 换成了真实调用。
    第2周做 RAG 时，直接把检索到的法条内容拼进 system_prompt 或者 prompt 里传进来即可，
    这个函数本身不用改。

    参数：
        prompt: 用户的问题
        system_prompt: 系统提示词（可选）。RAG 场景下通常是：
            "你是一个法律助手，请根据以下法律条文回答问题：\n{检索到的条文}"

    返回：
        模型生成的回答文本

    异常：
        调用失败时抛出 RuntimeError，由上层接口转换成 HTTP 错误返回给调用方。
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = _client.chat(
            model=CHAT_MODEL,
            messages=messages,
            options={"num_ctx": 2048},  # 显存有限（4GB显卡），先调小一点，够用再说
        )
    except Exception as e:
        logger.exception("调用 Ollama 生成回答失败")
        raise RuntimeError(
            f"调用 {CHAT_MODEL} 失败，请确认 Ollama 服务已启动且模型已拉取。原始错误: {e}"
        ) from e

    answer = response.get("message", {}).get("content", "")
    if not answer:
        raise RuntimeError("Ollama 返回了空结果，请检查模型状态或输入内容")

    return answer


# ========== RAG 相关 ==========

# 相关度阈值：top1 分数低于这个值，说明检索到的法条大概率文不对题，
# 给前端一个 low_confidence 提示，避免用户误信一个其实没有法律依据的回答。
# 这个值是根据实测调整的：无关问题（比如问天气）top1 大概 0.47，
# 正常法律问题 top1 基本在 0.73 以上，中间留了不少余量，先定在 0.6。
RELEVANCE_THRESHOLD = 0.6


def build_rag_system_prompt(articles: list) -> str:
    """把检索到的法条拼成 system prompt，交给大模型参考后回答问题。"""
    if not articles:
        return (
            "你是一个法律助手。这次没有检索到相关的法律条文，"
            "请明确告诉用户没有找到相关法律依据，不要编造法条内容。"
        )

    law_texts = []
    for i, a in enumerate(articles, start=1):
        title = " ".join(p for p in (a.get("law_name"), a.get("article_no")) if p)
        law_texts.append(f"[{i}] {title}\n{a.get('content', '')}")

    joined = "\n\n".join(law_texts)
    return (
        "你是一个法律助手，请仅根据下面提供的法律条文回答用户的问题。\n"
        "如果条文里没有能回答问题的内容，请明确说明现有条文不足以回答，不要编造。\n"
        "回答时请指出依据的是第几条法条（用 [编号] 标注）。\n\n"
        f"参考法条：\n{joined}"
    )


# ========== 接口路由 ==========

@app.get("/health")
def health():
    """
    健康检查接口。
    同学第一次连接时，先访问这个接口确认服务和网络是通的，
    不涉及调用大模型，所以响应很快，用来快速排查"服务没起来"还是"模型调用慢"。
    """
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    """
    对话生成接口。同学可以直接 POST 一个问题过来，拿到大模型的回答。
    第2周接入检索之后，可以在这个接口基础上再加一个 /ask 接口做完整 RAG 流程
    （检索 + 拼 prompt + 生成），这个 /generate 可以继续保留作为底层能力。
    """
    start = time.time()
    try:
        answer = generate_answer(req.prompt, req.system_prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    elapsed = time.time() - start
    logger.info(f"生成完成，用时 {elapsed:.2f}s，prompt: {req.prompt[:30]}...")

    return GenerateResponse(answer=answer, model=CHAT_MODEL, elapsed_seconds=elapsed)


@app.post("/search", response_model=SearchResponse)
def search_articles(req: SearchRequest):
    """
    检索接口。输入一个法律问题，返回最相关的 top_k 条法条（不经过大模型，纯检索）。
    B 同学的 RetrievalAgent 调用这个接口拿法条。
    """
    try:
        results = retrieve_articles(req.query, top_k=req.top_k)
    except IndexNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return SearchResponse(query=req.query, results=results)


@app.post("/rag", response_model=RagResponse)
def rag(req: RagRequest):
    """
    完整 RAG 接口：检索相关法条 → 拼进 prompt → 调用大模型生成回答 → 返回答案和引用的法条。
    C 同学的 QAAgent 调用这个接口拿最终回答。
    """
    start = time.time()

    try:
        articles = retrieve_articles(req.prompt, top_k=req.top_k)
    except IndexNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    system_prompt = build_rag_system_prompt(articles)

    try:
        answer = generate_answer(req.prompt, system_prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    low_confidence = (not articles) or (articles[0]["score"] < RELEVANCE_THRESHOLD)
    elapsed = time.time() - start

    logger.info(
        f"RAG 完成，用时 {elapsed:.2f}s，检索到 {len(articles)} 条法条，"
        f"prompt: {req.prompt[:30]}..."
    )

    return RagResponse(
        answer=answer,
        references=articles,
        model=CHAT_MODEL,
        elapsed_seconds=elapsed,
        low_confidence=low_confidence,
    )


if __name__ == "__main__":
    import uvicorn
    # 直接传 app 对象，不用字符串 "main:app"，这样不管从哪里运行都不会因为
    # 模块路径找不到而报错。缺点是不支持 --reload 热重载，
    # 需要热重载时用: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    uvicorn.run(app, host=HOST, port=PORT)