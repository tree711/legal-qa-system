# API 服务模块（组长 Day 3 — 第2周任务①②③）

## 目录结构
```
project_root/
└── api/
    ├── config.py     # 模型名、Ollama地址、监听端口配置
    ├── main.py        # FastAPI 服务：/health + /generate
    └── requirements.txt
```

## 安装依赖
```bash
pip install -r api/requirements.txt
```

## 启动服务
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
看到类似 `Uvicorn running on http://0.0.0.0:8000` 就说明起来了。

## 自测
浏览器打开：
```
http://127.0.0.1:8000/health
```
应该返回：
```json
{"status": "ok"}
```

FastAPI 自带交互式文档（很好用，可以直接在网页上试调接口）：
```
http://127.0.0.1:8000/docs
```

## 测试真实生成（qwen2:7b）
在 `/docs` 页面找到 `POST /generate`，点 Try it out，输入：
```json
{
  "prompt": "试用期最长可以约定多久？"
}
```
或者用 curl：
```bash
curl -X POST http://127.0.0.1:8000/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"试用期最长可以约定多久？\"}"
```
（Windows cmd 下用 `^` 续行；如果是 PowerShell 或 git bash，换成 `\`）

正常情况下会等几秒到十几秒（取决于你电脑跑 qwen2:7b 的速度），然后返回：
```json
{
  "answer": "...",
  "model": "qwen2:7b",
  "elapsed_seconds": 8.3
}
```

## 给同组同学的接入方式
1. 让同学和你连同一个 WiFi/局域网
2. 你在 cmd 里运行 `ipconfig`，找到 IPv4 地址（一般长得像 `192.168.x.x`）
3. 把这个地址发给同学，她们访问 `http://192.168.x.x:8000/docs` 就能看到接口文档并直接调用
4. 不需要在她们电脑上装 Ollama / faiss / 任何模型，所有计算都在你这台机器上跑

## 完成情况
- `generate_answer()` 已经是真实调用了，不用再改
- ✅ `/search` 和 `/rag` 接口已经实现（见下面说明）
- ✅ `/chat` 接口已经实现，支持多轮对话 + 上下文历史（见下面说明）

## `/search` 接口 —— 纯检索，不调用大模型

请求：
```json
POST /search
{
  "query": "试用期最长可以约定多久？",
  "top_k": 3
}
```
返回：
```json
{
  "query": "试用期最长可以约定多久？",
  "results": [
    {
      "law_name": "中华人民共和国劳动法(2018修正)",
      "article_no": "第二十一条",
      "content": "劳动合同可以约定试用期。试用期最长不得超过六个月。",
      "chapter": "",
      "source_url": "...",
      "score": 0.7445
    }
  ]
}
```
B 同学的 `RetrievalAgent` 调用这个接口拿法条。

## `/rag` 接口 —— 检索 + 生成 + 引用

请求：
```json
POST /rag
{
  "prompt": "试用期最长可以约定多久？",
  "top_k": 3
}
```
返回：
```json
{
  "answer": "根据《劳动法》第二十一条...",
  "references": [ /* 结构同 /search 里的 results */ ],
  "model": "qwen2:7b",
  "elapsed_seconds": 14.5,
  "low_confidence": false
}
```
`low_confidence` 为 `true` 时，说明检索到的法条相关度都偏低（top1 分数低于 0.6），
提示这个回答可能没有可靠的法律依据支撑，前端可以据此显示一个警示。

C 同学的 `QAAgent` 调用这个接口拿最终回答。

## `/chat` 接口 —— 多轮对话（带上下文历史）

用法约定：**每次调用都要把完整的历史消息传回来**，服务端不保存状态（无状态设计，方便多个同学同时调用互不干扰）。

第一次提问：
```json
POST /chat
{
  "messages": [
    {"role": "user", "content": "试用期最长可以约定多久？"}
  ]
}
```
返回：
```json
{
  "answer": "根据《劳动法》第二十一条...",
  "messages": [
    {"role": "user", "content": "试用期最长可以约定多久？"},
    {"role": "assistant", "content": "根据《劳动法》第二十一条..."}
  ],
  "references": [ /* 这一轮检索到的法条 */ ],
  "model": "qwen2:7b",
  "elapsed_seconds": 12.3,
  "low_confidence": false
}
```
第二次提问（追问）：把上一轮返回的 `messages` 原样传回来，末尾加一条新的 `user` 消息：
```json
POST /chat
{
  "messages": [
    {"role": "user", "content": "试用期最长可以约定多久？"},
    {"role": "assistant", "content": "根据《劳动法》第二十一条..."},
    {"role": "user", "content": "那试用期工资怎么算？"}
  ]
}
```
每一轮都会用**最新这条 user 消息**重新检索法条，不是只用第一轮的检索结果，保证追问也能查到对的法条。

`use_rag` 默认是 `true`。如果只是想要不查法条的纯闲聊/多轮对话能力，传 `"use_rag": false` 即可，这时 `references` 会是空列表。

## 协助 B / C 调试时的排查清单

按之前踩过的坑，从上到下排查基本能覆盖 90% 的问题：

1. **她们是不是在用 `localhost` 或 `127.0.0.1`？** 这两个都是"她自己的电脑"，必须换成你的局域网 IP（`ipconfig` 查）
2. **是不是同一个 WiFi/局域网？** 不同网络之间互相连不上
3. **Windows 防火墙有没有放行 8000 端口？** 连不上先看这个
4. **请求的 JSON 格式对不对？** 让她们先用 `/docs` 页面手动试一次，确认格式没问题，再回去改 Agent 代码里的请求体
5. **`/chat` 报 400** → 检查 `messages` 最后一条是不是 `role: user`
6. **报 503** → 索引没建好，或者 Ollama 没启动
7. **报 502** → Ollama 调用失败，回到今天排查 503 时用过的方法（`ollama serve` 前台看日志、`ollama ps` 看模型状态）
## 依赖变化
`/search` 和 `/rag` 直接复用了 `embedding/search.py` 里的 `search()` 函数，
所以 `api/requirements.txt` 里新增了 `faiss-cpu` 和 `numpy`，记得重新执行一次：
```bash
pip install -r api/requirements.txt
```

## 重要前提
`/search` 和 `/rag` 依赖 `data/index/` 下已经构建好的 FAISS 索引
（也就是昨天 `build_index.py` 生成的那两个文件）。如果索引还没构建，
这两个接口会返回 `503`，提示先运行 `build_index.py`。