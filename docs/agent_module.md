# Agent 模块技术文档

## 1. 模块概述

成员 B 负责实现以下两个 Agent：

- `RetrievalAgent`：接收法律问题，调用组长提供的 `POST /search` 接口，获取相关法律条文。
- `SummaryAgent`：接收检索结果，将多条法律条文整理为结构化摘要，并保留引用信息。

整体流程：

```text
用户问题
→ 成员 C 的调度器
→ RetrievalAgent
→ POST /search
→ 返回法律条文
→ SummaryAgent
→ 结构化摘要
→ QAAgent 或调度器继续处理
```

## 2. 文件结构

```text
agent/
├── __init__.py
├── retrieval_agent.py
├── summary_agent.py
└── langchain_tools.py
```

测试文件：

```text
tests/
└── test_agents.py
```

真实接口联调脚本：

```text
run_live_demo.py
```

## 3. RetrievalAgent

### 3.1 初始化

```python
from agent import RetrievalAgent

agent = RetrievalAgent(
    base_url="http://172.20.10.2:8000",
    score_threshold=0.6,
    timeout=30,
)
```

参数说明：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `base_url` | FastAPI 服务地址 | `http://172.20.10.2:8000` |
| `score_threshold` | 可信结果阈值 | `0.6` |
| `timeout` | HTTP 超时时间，单位为秒 | `30` |

### 3.2 调用方法

```python
result = agent.retrieve("劳动合同试用期最长可以约定多久？")
```

### 3.3 返回字段

| 字段 | 说明 |
|---|---|
| `agent` | Agent 名称 |
| `status` | `success`、`empty` 或 `error` |
| `question` | 用户问题 |
| `score_threshold` | 当前可信度阈值 |
| `results` | 全部标准化结果 |
| `trusted_results` | `score >= 0.6` 的结果 |
| `reference_results` | `score < 0.6` 的结果 |
| `message` | 状态说明 |

单条法条结构：

```json
{
  "law_name": "中华人民共和国劳动合同法(2012修正)",
  "article_no": "第十九条",
  "content": "……",
  "chapter": "第二章劳动合同的订立",
  "source_url": "crawler/lawhtml/labor_contract_law_pkulaw.html",
  "score": 0.798,
  "trusted": true
}
```

## 4. SummaryAgent

### 4.1 调用方法

```python
from agent import SummaryAgent

summary_agent = SummaryAgent()
summary_result = summary_agent.summarize(retrieval_result)
```

### 4.2 返回字段

| 字段 | 说明 |
|---|---|
| `agent` | Agent 名称 |
| `status` | `success`、`empty` 或 `error` |
| `question` | 原始问题 |
| `summary` | 法条结构化摘要 |
| `references` | 法规名称、条文编号、来源和分数 |
| `message` | 状态说明 |

## 5. 成员 C 调用示例

```python
from agent import RetrievalAgent, SummaryAgent

retrieval_agent = RetrievalAgent()
summary_agent = SummaryAgent()

question = "劳动合同试用期最长可以约定多久？"

retrieval_result = retrieval_agent.retrieve(question)

if retrieval_result["status"] == "success":
    summary_result = summary_agent.summarize(retrieval_result)
    print(summary_result["summary"])
else:
    print(retrieval_result["message"])
```

## 6. 异常处理

模块已处理以下情况：

- 问题为空；
- API 连接失败；
- API 调用超时；
- HTTP 状态码异常；
- 返回内容不是合法 JSON；
- `results` 字段类型错误；
- 检索结果为空；
- `score` 不是合法数字。

异常发生时返回结构化错误信息，不直接使调度器崩溃。

## 7. 测试方式

运行自动化测试：

```powershell
python -m unittest discover -s tests -v
```

运行真实接口联调：

```powershell
python run_live_demo.py
```

手工场景测试方法见：

```text
docs/agent_test_report.md
```
