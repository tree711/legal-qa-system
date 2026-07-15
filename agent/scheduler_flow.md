# AgentScheduler 调度流程图

## 1. 当前版本说明

当前版本已经接入三个 Agent：

1. `RetrievalAgent`：调用 `/search` 接口，检索相关法条
2. `QAAgent`：调用 `/rag` 接口，生成最终法律问答结果
3. `SummaryAgent`：对检索到的法条做结构化总结

三个 Agent 不是同时运行，而是由 `AgentScheduler` 按顺序调度。

当前完整流程为：

用户问题 -> RetrievalAgent -> QAAgent -> SummaryAgent -> 最终输出

---

## 2. 三个 Agent 调度流程图

```mermaid
flowchart TD
    A[用户输入法律问题] --> B[AgentScheduler 接收问题]

    B --> C[RetrievalAgent]
    C --> D[调用 POST /search 接口]
    D --> E[返回相关法条 results]
    E --> F[区分 trusted_results 和 reference_results]

    F --> G[QAAgent]
    G --> H[调用 POST /rag 接口]
    H --> I[返回 answer 和 references]

    I --> J[SummaryAgent]
    J --> K[对 RetrievalAgent 的结果做结构化总结]

    K --> L[AgentScheduler 整理最终输出]
    L --> M[输出 final_answer、references、summary_result、retrieval_result 和 steps]
```

---

## 3. Day 4 异常处理流程图

```mermaid
flowchart TD
    A[用户输入法律问题] --> B[AgentScheduler 接收问题]
    B --> C{问题是否为空}

    C -- 是 --> D[返回错误：问题不能为空]
    C -- 否 --> E[调用 RetrievalAgent]

    E --> F{RetrievalAgent 是否成功}
    F -- 成功 --> G[保存检索结果]
    F -- 失败或超时 --> H[记录错误信息]

    G --> I[调用 QAAgent]
    H --> I[继续调用 QAAgent 作为兜底]

    I --> J{QAAgent 是否成功}
    J -- 否 --> K[返回 QAAgent 错误信息]
    J -- 是 --> L[获得最终回答和引用法条]

    L --> M[调用 SummaryAgent]
    M --> N{SummaryAgent 是否成功}

    N -- 成功 --> O[返回结构化总结]
    N -- 失败 --> P[记录总结失败，但保留最终回答]

    O --> Q[输出最终结果]
    P --> Q[输出最终结果]
```

---

## 4. 三个 Agent 的职责

### RetrievalAgent

负责检索相关法条。

调用方式：

```python
retrieval_result = RetrievalAgent().retrieve(question)
```

主要返回字段：

```text
status
results
trusted_results
reference_results
message
```

### QAAgent

负责生成最终法律问答结果。

调用方式：

```python
qa_result = QAAgent().answer(question)
```

主要返回字段：

```text
success
answer
references
raw
```

### SummaryAgent

负责对检索结果做结构化总结。

调用方式：

```python
summary_result = SummaryAgent().summarize(retrieval_result)
```

主要返回字段：

```text
status
summary
references
message
```

---

## 5. Day 4 更新内容

Day 4 对调度器进行了以下完善：

1. 增加空问题检查
2. 增加 RetrievalAgent 超时后的兜底处理
3. RetrievalAgent 调用失败时，继续调用 QAAgent
4. QAAgent 失败时返回明确错误信息
5. SummaryAgent 失败时不影响最终回答
6. 输出完整 steps，方便联调和测试