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