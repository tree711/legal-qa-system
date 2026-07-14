# 成员 B：RetrievalAgent 与 SummaryAgent 使用说明

## 1. 模块职责

成员 B 负责两个 Agent：

- `RetrievalAgent`：调用组长提供的 `POST /search` 接口，获取相关法律条文。
- `SummaryAgent`：对检索结果进行整理和结构化总结。

本模块不负责前端，也不需要在本地运行 Ollama、FAISS 或 embedding 模型。

整体调用链路如下：

```text
用户问题
→ C 的调度器
→ RetrievalAgent
→ 组长的 /search 接口
→ 返回相关法条
→ SummaryAgent
→ 返回结构化摘要
→ C 的 QAAgent 或调度器继续处理
```

---

## 2. 项目结构

```text
legal-qa-system/
├── agent/
│   ├── __init__.py
│   ├── retrieval_agent.py
│   ├── summary_agent.py
│   └── langchain_tools.py
├── api/
├── cleaner/
├── crawler/
├── data/
├── docs/
├── embedding/
├── rag/
├── tests/
│   └── test_agents.py
├── requirements.txt
└── run_live_demo.py
```

`agent` 与 `embedding`、`rag`、`api` 等目录平级。

---

## 3. 安装依赖

建议先激活虚拟环境：

```powershell
.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

---

## 4. RetrievalAgent 使用方法

### 4.1 基本调用

```python
from agent import RetrievalAgent

retrieval_agent = RetrievalAgent()

result = retrieval_agent.retrieve(
    "劳动合同试用期最长可以约定多久？"
)

print(result)
```

`RetrievalAgent()` 默认使用组长提供的接口地址：

```text
http://172.20.10.2:8000/search
```

如接口地址发生变化，可手动指定：

```python
retrieval_agent = RetrievalAgent(
    base_url="http://新的IP地址:8000"
)
```

### 4.2 主要返回字段

```python
result["status"]
result["question"]
result["results"]
result["trusted_results"]
result["reference_results"]
result["message"]
```

返回结构示例：

```json
{
  "agent": "RetrievalAgent",
  "status": "success",
  "question": "劳动合同试用期最长可以约定多久？",
  "score_threshold": 0.6,
  "results": [],
  "trusted_results": [],
  "reference_results": [],
  "message": "共检索到 3 条法条，其中 3 条 score 不低于 0.6。"
}
```

### 4.3 score 分类规则

```text
score >= 0.6 → trusted_results
score < 0.6  → reference_results
```

低于 0.6 的结果不会直接删除，而是作为参考结果保留。

---

## 5. SummaryAgent 使用方法

### 5.1 基本调用

```python
from agent import RetrievalAgent, SummaryAgent

retrieval_agent = RetrievalAgent()
summary_agent = SummaryAgent()

retrieval_result = retrieval_agent.retrieve(
    "劳动合同试用期最长可以约定多久？"
)

summary_result = summary_agent.summarize(
    retrieval_result
)

print(summary_result["summary"])
```

### 5.2 主要返回字段

```python
summary_result["status"]
summary_result["question"]
summary_result["summary"]
summary_result["references"]
summary_result["message"]
```

返回结构示例：

```json
{
  "agent": "SummaryAgent",
  "status": "success",
  "question": "劳动合同试用期最长可以约定多久？",
  "summary": "1. 《中华人民共和国劳动法》第二十一条：……",
  "references": [],
  "message": "已根据 3 条法条完成结构化总结。"
}
```

---

## 6. 提供给成员 C 的标准调用方式

成员 C 可直接使用下面的代码：

```python
from agent import RetrievalAgent, SummaryAgent

retrieval_agent = RetrievalAgent()
summary_agent = SummaryAgent()

def run_retrieval_and_summary(question: str):
    retrieval_result = retrieval_agent.retrieve(question)

    if retrieval_result["status"] != "success":
        return {
            "status": "error",
            "message": retrieval_result["message"]
        }

    summary_result = summary_agent.summarize(
        retrieval_result
    )

    return {
        "status": summary_result["status"],
        "retrieval_result": retrieval_result,
        "summary_result": summary_result
    }
```

成员 C 主要需要读取：

```python
retrieval_result["status"]
retrieval_result["trusted_results"]
retrieval_result["reference_results"]

summary_result["status"]
summary_result["summary"]
summary_result["references"]
```

---

## 7. 异常处理

### 7.1 空问题

```python
result = retrieval_agent.retrieve("")
```

预期结果：

```json
{
  "status": "error",
  "message": "问题不能为空。"
}
```

### 7.2 接口超时或无法连接

当组长服务关闭、地址错误或网络断开时：

```json
{
  "status": "error",
  "message": "调用 /search 接口超时。"
}
```

或：

```json
{
  "status": "error",
  "message": "无法连接 API 服务……"
}
```

程序不会直接崩溃，`SummaryAgent` 也会停止继续处理并返回错误状态。

---

## 8. 测试方法

### 8.1 自动化测试

在项目根目录执行：

```powershell
python -m unittest discover -s tests -v
```

预期输出：

```text
test_empty_question ... ok
test_retrieve_success ... ok
test_summary_success ... ok

Ran 3 tests
OK
```

### 8.2 真实接口联调

确保组长的 FastAPI 服务已启动，并且可以访问：

```text
http://172.20.10.2:8000/docs
```

然后运行：

```powershell
python run_live_demo.py
```

正常情况下应看到：

```text
=== RetrievalAgent 原始结果 ===
=== 格式化法条 ===
=== SummaryAgent 结果 ===
```

并且：

```text
RetrievalAgent status = success
SummaryAgent status = success
```

---

## 9. 与成员 C 的联调检查项

联调时至少检查：

- C 可以成功导入 `RetrievalAgent` 和 `SummaryAgent`
- C 可以调用 `retrieve(question)`
- C 可以调用 `summarize(retrieval_result)`
- 返回字段与 C 的调度器代码一致
- 正常问题能返回法条和摘要
- 无检索结果时不会崩溃
- API 超时或断开时不会崩溃
- `score >= 0.6` 和 `< 0.6` 的结果能正确分类

---
