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
import json
from pathlib import Path
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


try:
    from agent.scheduler import AgentScheduler
except ImportError:
    from scheduler import AgentScheduler

try:
    from services.session_store import (
        create_session, list_sessions, get_session, save_messages, clear_session, delete_session
    )
except ImportError:
    from session_store import (
        create_session, list_sessions, get_session, save_messages, clear_session, delete_session
    )

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
    top_k: int = Field(default=3, ge=1, le=20, description="返回最相关的几条法条，默认3条")

    model_config = {
        "json_schema_extra": {
            "example": {"query": "试用期最长可以约定多久？", "top_k": 3}
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
    top_k: int = Field(default=3, ge=1, le=20, description="检索并参考的法条数量，默认3条")

    model_config = {
        "json_schema_extra": {
            "example": {"prompt": "试用期最长可以约定多久？", "top_k": 3}
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
    messages: list[ChatMessage] | None = Field(
        default=None,
        description="兼容旧模式：传完整历史消息，最后一条必须为 user。",
    )
    session_id: str | None = Field(default=None, description="服务器会话 ID；与 message 配合使用")
    message: str | None = Field(default=None, min_length=1, description="服务器会话模式下的新问题")
    top_k: int = Field(default=3, ge=1, le=20, description="每轮检索并参考的法条数量")
    use_rag: bool = Field(default=True, description="是否结合法条检索回答")

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {"role": "user", "content": "试用期最长可以约定多久？"}
                ],
                "top_k": 3,
                "use_rag": True,
            }
        }
    }


class ChatResponse(BaseModel):
    answer: str
    session_id: str | None = None
    rewritten_question: str | None = None
    messages: list[ChatMessage] = Field(description="更新后的完整对话历史（包含这一轮的回答），下一轮原样传回来即可")
    references: list[ArticleResult] = Field(description="这一轮检索到的法条，use_rag=False 时为空列表")
    model: str
    elapsed_seconds: float
    low_confidence: bool = Field(
        description="use_rag=True 且检索到的法条相关度都偏低时为 True"
    )
    steps: list[str] = Field(default_factory=list, description="三个 Agent 的实际调度步骤")
    summary_result: dict = Field(default_factory=dict, description="SummaryAgent 的结构化总结")
    retrieval_result: dict = Field(default_factory=dict, description="RetrievalAgent 的标准化结果")


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
                "num_ctx": 2048,
                "num_predict": MAX_TOKENS,
                # 法律结论应尽量稳定，避免同一问题多次调用出现相反结论。
                "temperature": 0,
                "seed": 42,
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




def _extract_hard_rules(articles: list) -> list[str]:
    """提取检索条文中的强制性表述，供生成阶段作反例约束。"""
    rules = []
    for index, article in enumerate(articles, start=1):
        content = str(article.get("content", ""))
        for sentence in content.replace("；", "。 ").split("。"):
            sentence = sentence.strip()
            if sentence and any(word in sentence for word in ("只能", "不得", "必须", "应当")):
                rules.append(f"[{index}] {sentence}")
    return rules[:8]


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
    hard_rules = _extract_hard_rules(articles)
    hard_rules_text = "\n".join(f"- {rule}" for rule in hard_rules) or "- 无"
    return (
        "你是严谨的法律法规问答助手。你只能使用下面【参考法条】中的文字作答，"
        "不得使用记忆补充法条、案例、法律链接或任何未提供的事实。\n"
        "作答前必须逐项核对问题中的期限、主体、条件和例外；当一般规则与同一批参考法条中的"
        "更具体规则同时出现时，应以能直接适用该事实的具体规则为准。\n"
        "如果参考法条没有决定性依据，第一行必须写“结论：现有参考法条不足以确定”。"
        "不得猜测、不得把不相干条文拼成结论。\n"
        "若依据充分，严格按以下格式输出：\n"
        "结论：用一句话直接回答。\n"
        "依据：列出实际使用的 [编号] 及其法规名称、条号，并简述其如何支持结论。\n"
        "说明：仅补充回答该问题必需的条件、例外或处理建议。\n"
        "只能引用参考法条的 [编号]；不得输出 URL、Markdown 超链接、未提供的法条号，"
        "也不得引用未实际用于结论的条文。\n\n"
        "【反例约束（必须遵守）】\n"
        "以下硬性规则直接适用时，结论不得与其相反，也不得自行增加法条未写明的条件、"
        "例外或豁免。回答中的“通常、首次、例外、除非、可能”等限定语，必须能由同一批"
        "参考法条逐字支持；否则删除该限定语并按硬性规则作答。\n"
        f"{hard_rules_text}\n\n"
        f"参考法条：\n{joined}"
    )




def _normalize_chat_request(req: ChatRequest) -> tuple[list[ChatMessage], str | None]:
    """兼容前端传完整 messages 与服务器 session_id + message 两种模式。"""
    if req.session_id:
        session = get_session(req.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        messages = [ChatMessage(**m) for m in session.get("messages", [])]
        if req.message and req.message.strip():
            messages.append(ChatMessage(role="user", content=req.message.strip()))
        elif req.messages:
            messages = req.messages
        else:
            raise HTTPException(status_code=400, detail="session_id 模式必须提供 message")
        return messages, req.session_id

    if not req.messages:
        raise HTTPException(status_code=400, detail="请提供 messages，或提供 session_id + message")
    return req.messages, None


def rewrite_question(messages: list[ChatMessage]) -> str:
    """将依赖上下文的追问改写成可独立检索的问题；失败时退化为最近用户问题拼接。"""
    latest = next((m.content for m in reversed(messages) if m.role == "user"), "")
    previous = [m for m in messages[:-1] if m.role in {"user", "assistant"}][-4:]
    if not previous:
        return latest
    context = "\n".join(f"{m.role}: {m.content}" for m in previous)
    prompt = (
        "请把最后一个用户问题改写成一个无需上下文也能理解、适合检索法律条文的完整问题。"
        "只输出改写后的问题，不要解释；不要增加对话中没有的事实。\n\n"
        f"对话上下文：\n{context}\n\n最后问题：{latest}"
    )
    try:
        rewritten = generate_answer(prompt).strip().strip('"“”')
        if rewritten and len(rewritten) <= 300:
            return rewritten
    except Exception:
        logger.warning("问题改写失败，使用规则兜底", exc_info=True)
    recent_users = [m.content for m in messages if m.role == "user"][-3:]
    return "；".join(recent_users)


def _local_search_handler(query: str, top_k: int) -> dict:
    """供 RetrievalAgent 在 API 进程内调用，避免再通过 HTTP 请求本机 /search。"""
    results = retrieve_articles(query, top_k=top_k)
    return {"query": query, "results": results}


def _local_rag_handler(question: str, top_k: int) -> dict:
    """供 QAAgent 单轮调用，逻辑与 /rag 一致，但不发 HTTP 请求。"""
    start = time.time()
    articles = retrieve_articles(question, top_k=top_k)
    answer = generate_answer(question, build_rag_system_prompt(articles))
    return {
        "answer": answer,
        "references": articles,
        "model": CHAT_MODEL,
        "elapsed_seconds": time.time() - start,
        "low_confidence": (not articles) or articles[0]["score"] < RELEVANCE_THRESHOLD,
    }


def _local_multiturn_handler(
    messages: list[dict], top_k: int, search_query: str | None,
    retrieval_result: dict | None,
) -> dict:
    """供 QAAgent 多轮调用；复用 RetrievalAgent 已检索的结果，避免二次检索。"""
    start = time.time()
    articles = (retrieval_result or {}).get("results", [])
    # RetrievalAgent 会补充 trusted 字段，返回前端前去除该内部字段。
    references = [
        {k: v for k, v in item.items() if k != "trusted"}
        for item in articles
    ]
    system_prompt = build_rag_system_prompt(references)
    history = [m for m in messages if m.get("role") != "system"][-MAX_HISTORY_TURNS * 2:]
    ollama_messages = [{"role": "system", "content": system_prompt}] + history
    answer = _call_ollama_chat(ollama_messages)
    updated = messages + [{"role": "assistant", "content": answer}]
    return {
        "answer": answer,
        "messages": updated,
        "references": references,
        "model": CHAT_MODEL,
        "elapsed_seconds": time.time() - start,
        "low_confidence": (not references) or references[0]["score"] < RELEVANCE_THRESHOLD,
        "rewritten_question": search_query,
    }


def process_chat(req: ChatRequest) -> ChatResponse:
    """/chat 的统一 Agent 入口：首轮与多轮都经过三个 Agent。"""
    messages, session_id = _normalize_chat_request(req)
    if messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="最后一条消息必须是 role=user 的新问题")

    start = time.time()
    message_dicts = [m.model_dump() for m in messages]
    latest_query = messages[-1].content
    user_turns = sum(1 for m in messages if m.role == "user")
    rewritten_query = rewrite_question(messages) if user_turns > 1 and req.use_rag else latest_query

    # 关闭 RAG 时不应仍然执行检索和 Agent 调度。此前 use_rag 仅影响问题改写，
    # 前端开关与后端行为不一致；这里保留多轮上下文，但明确返回空引用。
    if not req.use_rag:
        history = [m.model_dump() for m in messages if m.role != "system"][-MAX_HISTORY_TURNS * 2:]
        try:
            answer = _call_ollama_chat([
                {
                    "role": "system",
                    "content": "你是法律学习助手。请说明回答仅供学习参考；不确定时明确说明，不要编造法条或结论。",
                },
                *history,
            ])
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        updated = messages + [ChatMessage(role="assistant", content=answer)]
        if session_id:
            title = next((m.content[:24] for m in updated if m.role == "user"), "新对话")
            save_messages(session_id, [m.model_dump() for m in updated], title)
        return ChatResponse(
            answer=answer,
            session_id=session_id,
            rewritten_question=latest_query,
            messages=updated,
            references=[],
            model=CHAT_MODEL,
            elapsed_seconds=time.time() - start,
            low_confidence=True,
            steps=["接收用户对话历史", "RAG 已关闭，直接调用本地模型", "完成非检索问答"],
            summary_result={},
            retrieval_result={},
        )

    try:
        scheduler = AgentScheduler(
            base_url="http://127.0.0.1:8000",
            top_k=req.top_k,
            search_handler=lambda q: _local_search_handler(q, req.top_k),
            rag_handler=_local_rag_handler,
            chat_handler=_local_multiturn_handler,
        )
        # 首轮和多轮均走 chat 调度链路。这样 RetrievalAgent 的同一份结果会
        # 同时供 QAAgent 生成答案、SummaryAgent 汇总和前端展示使用，避免首轮
        # 先检索一次、/rag 再检索一次造成引用与答案不一致。
        result = scheduler.chat(message_dicts, search_query=rewritten_query)
    except IndexNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Agent 调度失败"))

    raw = result.get("raw", {}) or {}
    answer = result.get("final_answer", "")
    references = [
        {k: v for k, v in item.items() if k != "trusted"}
        for item in result.get("references", [])
    ]
    updated_dicts = raw.get("messages") or (message_dicts + [{"role": "assistant", "content": answer}])
    updated = [ChatMessage(**m) for m in updated_dicts]

    if session_id:
        title = next((m.content[:24] for m in updated if m.role == "user"), "新对话")
        save_messages(session_id, [m.model_dump() for m in updated], title)

    low_confidence = raw.get("low_confidence")
    if low_confidence is None:
        low_confidence = (not references) or references[0]["score"] < RELEVANCE_THRESHOLD

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        rewritten_question=rewritten_query,
        messages=updated,
        references=references,
        model=raw.get("model", CHAT_MODEL),
        elapsed_seconds=raw.get("elapsed_seconds") or (time.time() - start),
        low_confidence=bool(low_confidence),
        steps=result.get("steps", []),
        summary_result=result.get("summary_result", {}),
        retrieval_result=result.get("retrieval_result", {}),
    )


# ========== 接口路由 ==========

@app.get("/health", tags=["系统状态"], summary="健康检查")
def health():
    """
    健康检查接口。
    同学第一次连接时，先访问这个接口确认服务和网络是通的，
    不涉及调用大模型，所以响应很快，用来快速排查"服务没起来"还是"模型调用慢"。
    """
    checks = {"api": "ok", "ollama": "error", "model": "unknown", "faiss_index": "missing"}
    try:
        models = _client.list()
        checks["ollama"] = "ok"
        checks["model"] = "ok" if CHAT_MODEL in json.dumps(models, ensure_ascii=False) else "missing"
    except Exception:
        pass
    try:
        from embedding.config import FAISS_INDEX_PATH, METADATA_PATH
        if Path(FAISS_INDEX_PATH).exists() and Path(METADATA_PATH).exists():
            checks["faiss_index"] = "ok"
    except Exception:
        pass
    return {"status": "ok" if checks["api"] == "ok" else "error", "checks": checks}


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


@app.post("/chat", response_model=ChatResponse, tags=["Agent 对话"], summary="统一 Agent 入口（三 Agent + 多轮上下文）")
def chat(req: ChatRequest):
    return process_chat(req)


class SessionCreateRequest(BaseModel):
    title: str = "新对话"


@app.post("/sessions", tags=["会话管理"])
def create_session_route(req: SessionCreateRequest):
    return create_session(req.title)


@app.get("/sessions", tags=["会话管理"])
def list_sessions_route():
    return {"sessions": list_sessions()}


@app.get("/sessions/{session_id}", tags=["会话管理"])
def get_session_route(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.delete("/sessions/{session_id}", tags=["会话管理"])
def delete_session_route(session_id: str):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True}


@app.post("/sessions/{session_id}/clear", tags=["会话管理"])
def clear_session_route(session_id: str):
    session = clear_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.get("/stats", tags=["系统状态"])
def stats():
    from embedding.config import CLEANED_DATA_PATH, METADATA_PATH
    law_count = article_count = 0
    updated_at = None
    try:
        data = json.loads(Path(CLEANED_DATA_PATH).read_text(encoding="utf-8"))
        article_count = len(data)
        law_count = len({x.get("law_name", "") for x in data if x.get("law_name")})
    except Exception:
        try:
            meta = json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))
            article_count = len(meta)
            law_count = len({x.get("law_name", "") for x in meta if x.get("law_name")})
        except Exception:
            pass
    try:
        updated_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(Path(METADATA_PATH).stat().st_mtime))
    except Exception:
        pass
    return {"law_count": law_count, "article_count": article_count, "index_updated_at": updated_at,
            "model": CHAT_MODEL, "sessions": len(list_sessions())}


if __name__ == "__main__":
    import uvicorn
    # 直接传 app 对象，不用字符串 "main:app"，这样不管从哪里运行都不会因为
    # 模块路径找不到而报错。缺点是不支持 --reload 热重载，
    # 需要热重载时用: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    uvicorn.run(app, host=HOST, port=PORT)
