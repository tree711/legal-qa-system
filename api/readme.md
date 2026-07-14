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

## 下一步（第2周后续任务）
- `generate_answer()` 已经是真实调用了，不用再改
- 接下来做"基础问答：检索 → 生成"时，新建一个 `/ask` 接口：
  1. 调用 `embedding/search.py` 里的 `search(query)` 拿到相关法条
  2. 把法条拼成 `system_prompt`，调用 `generate_answer(prompt, system_prompt)`
  3. 把回答 + 引用的法条一起返回给前端
- 多轮对话：现在 `/generate` 是无状态的（每次都是新对话），后面要维护上下文，
  可以在请求里加一个 `session_id`，服务端用字典缓存每个 session 的历史 messages，
  拼进 `messages` 列表一起传给 `ollama.chat`