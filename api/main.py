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
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import ollama

try:
    # 通过 `uvicorn api.main:app` 以包的方式导入时走这里
    from api.config import (
        CHAT_MODEL, OLLAMA_HOST, GENERATE_TIMEOUT, HOST, PORT,
        MAX_TOKENS, MAX_HISTORY_TURNS, KEEP_ALIVE,
    )
except ImportError:
    # 通过 `python api/main.py` 直接运行脚本时走这里
    from config import (
        CHAT_MODEL, OLLAMA_HOST, GENERATE_TIMEOUT, HOST, PORT,
        MAX_TOKENS, MAX_HISTORY_TURNS, KEEP_ALIVE,
    )

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

API_DESCRIPTION = """
给同组同学调用的法律问答接口，封装了本地 Ollama 大模型（qwen2:7b）和 FAISS 法律条文检索。

## 快速上手
1. 确认你和组长（服务提供方）在**同一个局域网/WiFi**下
2. 用组长电脑的**局域网 IP**访问（不是 `localhost`，也不是 `127.0.0.1`——那两个都指向你自己的电脑）
   例如：`http://192.168.x.x:8000/docs`
3. 点开任意接口 → `Try it out` → 里面已经填好了示例请求 → `Execute` 就能看到真实返回结果

## 接口怎么选
| 你要做的事 | 用哪个接口 |
|---|---|
| 只想拿相关法条，不需要大模型生成回答 | `/search` |
| 拿到法条 + 大模型生成的一次性回答 | `/rag` |
| 需要多轮对话、记得上下文 | `/chat` |
| 纯粹调用大模型、不做法条检索 | `/generate` |

## 几个通用规则
- 所有接口都是 POST，请求体是 JSON
- `references` / `results` 里的 `score` 是余弦相似度（0~1），越接近 1 越相关
- `low_confidence: true` 表示检索到的法条相关度都偏低，回答可能没有可靠法律依据支撑，前端建议做警示提示
- 常见报错：`503` = 索引没建好或 Ollama 没启动；`502` = 调用 Ollama 失败；`422` = 请求 JSON 格式不对（多半是少了逗号或字段类型错了）
"""

app = FastAPI(
    title="法律问答系统 API",
    description=API_DESCRIPTION,
    version="0.2.0",
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

    model_config = {
        "json_schema_extra": {
            "example": {"prompt": "试用期最长可以约定多久？"}
        }
    }


class GenerateResponse(BaseModel):
    answer: str
    model: str
    elapsed_seconds: float


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户输入的法律问题")
    top_k: int = Field(default=5, ge=1, le=20, description="返回最相关的几条法条，默认5条")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "试用期最长可以约定多久？", "top_k": 5}
        }
    }


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
    top_k: int = Field(default=5, ge=1, le=20, description="检索并参考的法条数量，默认5条")

    model_config = {
        "json_schema_extra": {
            "example": {"prompt": "试用期最长可以约定多久？", "top_k": 5}
        }
    }


class RagResponse(BaseModel):
    answer: str
    references: list[ArticleResult]
    model: str
    elapsed_seconds: float
    low_confidence: bool = Field(
        description="检索到的法条相关度都偏低时为 True，提示这个回答可能不够可靠"
    )


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(
        ...,
        min_length=1,
        description=(
            "完整的历史对话消息列表，最后一条必须是 role=user 的新问题。"
            "第一次提问时只传一条 user 消息即可；之后每次调用，"
            "把上一次返回的 messages 原样传回来、并在最后追加新的 user 消息。"
        ),
    )
    top_k: int = Field(default=5, ge=1, le=20, description="每轮检索并参考的法条数量，默认5条")
    use_rag: bool = Field(
        default=True,
        description="是否结合法条检索回答（默认开启）。关闭后就是纯闲聊模式，不查法条。",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "user", "content": "试用期最长可以约定多久？"}
                ],
                "top_k": 5,
                "use_rag": True,
            }
        }
    }


class ChatResponse(BaseModel):
    answer: str
    messages: list[ChatMessage] = Field(description="更新后的完整对话历史（包含这一轮的回答），下一轮原样传回来即可")
    references: list[ArticleResult] = Field(description="这一轮检索到的法条，use_rag=False 时为空列表")
    model: str
    elapsed_seconds: float
    low_confidence: bool = Field(
        description="use_rag=True 且检索到的法条相关度都偏低时为 True"
    )


# ========== 核心函数 ==========

def _call_ollama_chat(messages: list[dict]) -> str:
    """
    实际调用 Ollama chat 接口的底层函数，接收完整的 messages 列表
    （可以是单轮的 [system?, user]，也可以是多轮历史 [system?, user, assistant, user, ...]）。

    generate_answer()（单轮）和 /chat 接口（多轮对话）都复用这个函数，
    避免重复写一遍调用逻辑和错误处理。

    异常：
        调用失败时抛出 RuntimeError，由上层接口转换成 HTTP 错误返回给调用方。
    """
    try:
        response = _client.chat(
            model=CHAT_MODEL,
            messages=messages,
            options={
                "num_ctx": 2048,       # 显存有限（4GB显卡），先调小一点，够用再说
                "num_predict": MAX_TOKENS,  # 限制单次生成长度，避免回答过长拖慢速度
            },
            keep_alive=KEEP_ALIVE,  # 联调期间让模型常驻显存，避免反复加载卸载
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


def generate_answer(prompt: str, system_prompt: str | None = None) -> str:
    """
    调用本地 qwen2:7b 生成回答（单轮，没有历史上下文）。

    这是 /generate 和 /rag 接口用的核心函数。
    多轮对话场景（带历史消息）用的是下面 /chat 接口里直接调用的 _call_ollama_chat()。

    参数：
        prompt: 用户的问题
        system_prompt: 系统提示词（可选）。RAG 场景下通常是：
            "你是一个法律助手，请根据以下法律条文回答问题：\n{检索到的条文}"

    返回：
        模型生成的回答文本
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return _call_ollama_chat(messages)


# ========== RAG 相关 ==========

# 相关度阈值：top1 分数低于这个值，说明检索到的法条大概率文不对题，
# 给前端一个 low_confidence 提示，避免用户误信一个其实没有法律依据的回答。
# 这个值是根据实测调整的：无关问题（比如问天气）top1 大概 0.47，
# 正常法律问题 top1 基本在 0.73 以上，中间留了不少余量，先定在 0.6。
RELEVANCE_THRESHOLD = 0.6


def build_retrieval_query(messages: list) -> str:
    """
    多轮对话里，用户的追问经常是简短、依赖上文的（比如"那如果一直没签怎么办？"），
    只拿这一句去检索，容易在语义上飘偏（比如"公司"两个字单独检索会匹配到不相关的公司法条款）。

    这里做一个简单、低成本的改进：把上一轮用户提问也拼进检索文本里，帮检索抓住话题；
    不改变喂给大模型生成回答用的完整对话历史，只影响"用什么去检索法条"这一步。
    """
    user_turns = [m.content for m in messages if m.role == "user"]
    if len(user_turns) >= 2:
        return f"{user_turns[-2]} {user_turns[-1]}"
    return user_turns[-1] if user_turns else ""




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
        "不要引用与问题无关的法律条文来凑内容，只使用真正相关的条文。\n"
        "如果条文中包含按数值/期限分档的规则（例如按合同期限、金额、天数分为几档），"
        "请先逐档核对用户问题里的具体数值落在哪一档，写出这个匹配过程，再给出结论，"
        "不要跳过匹配直接下结论，也不要混用其他档位的规则。\n"
        "如果问题是一个是非判断题（比如\"是否合法\"\"是否构成\"），"
        "请明确给出\"是/否\"或\"合法/不合法\"的结论，不要只罗列可能性、回避明确判断。\n"
        "回答时请指出依据的是第几条法条（用 [编号] 标注）。\n\n"
        f"参考法条：\n{joined}"
    )


# ========== 接口路由 ==========

@app.get("/health", tags=["系统状态"], summary="健康检查")
def health():
    """
    健康检查接口。
    同学第一次连接时，先访问这个接口确认服务和网络是通的，
    不涉及调用大模型，所以响应很快，用来快速排查"服务没起来"还是"模型调用慢"。
    """
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateResponse, tags=["对话生成"], summary="纯生成（不检索法条）")
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


@app.post("/search", response_model=SearchResponse, tags=["法条检索"], summary="纯检索，返回 top_k 条法条")
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


@app.post("/rag", response_model=RagResponse, tags=["法条检索"], summary="检索 + 生成 + 引用（单轮）")
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


@app.post("/chat", response_model=ChatResponse, tags=["多轮对话"], summary="多轮对话（带上下文历史）")
def chat(req: ChatRequest):
    """
    多轮对话接口：接收完整的历史消息列表，返回带上下文的回答。

    用法约定：
    - 第一次提问：messages = [{"role": "user", "content": "问题1"}]
    - 拿到返回后，把返回的 messages 原样保存下来
    - 下一轮提问：把上一轮返回的 messages 追加一条新的 user 消息再传进来
      即 messages = 上一轮返回的 messages + [{"role": "user", "content": "问题2"}]

    每一轮都会用"最新这条用户消息"重新检索一次法条（如果 use_rag=True），
    保证多轮对话中每次回答依据的都是当前问题最相关的法条，而不是第一轮检索的旧结果。
    """
    if req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="messages 的最后一条必须是 role=user 的新问题")

    start = time.time()
    latest_query = req.messages[-1].content
    # 检索用的 query 额外拼上上一轮问题，帮助理解简短追问的真实意图；
    # 传给大模型生成回答的 latest_query / 完整历史不受影响
    retrieval_query = build_retrieval_query(req.messages)

    articles = []
    system_prompt = None
    if req.use_rag:
        try:
            articles = retrieve_articles(retrieval_query, top_k=req.top_k)
        except IndexNotReadyError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        system_prompt = build_rag_system_prompt(articles)

    # 历史消息里可能已经带了旧的 system 消息（比如上一轮的检索结果），
    # 这里统一过滤掉，换成这一轮最新检索到的，避免新旧法条信息互相打架
    history_without_system = [m for m in req.messages if m.role != "system"]

    # 只保留最近 MAX_HISTORY_TURNS 轮（一问一答算一轮 = 2 条消息），
    # 避免对话轮数一多，每轮都要重新处理越来越长的历史，导致越聊越慢。
    # 注意：这里只是"这次发给模型看多少"，接口最终返回的 messages 仍是完整历史。
    max_messages = MAX_HISTORY_TURNS * 2
    if len(history_without_system) > max_messages:
        history_without_system = history_without_system[-max_messages:]

    ollama_messages = []
    if system_prompt:
        ollama_messages.append({"role": "system", "content": system_prompt})
    ollama_messages += [{"role": m.role, "content": m.content} for m in history_without_system]

    try:
        answer = _call_ollama_chat(ollama_messages)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    updated_messages = req.messages + [ChatMessage(role="assistant", content=answer)]
    low_confidence = req.use_rag and ((not articles) or articles[0]["score"] < RELEVANCE_THRESHOLD)
    elapsed = time.time() - start

    logger.info(
        f"/chat 完成，用时 {elapsed:.2f}s，历史长度 {len(req.messages)}，"
        f"最新提问: {latest_query[:30]}..."
    )

    return ChatResponse(
        answer=answer,
        messages=updated_messages,
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