# AgentScheduler 模块说明与调度流程图

## 1. 模块定位

`AgentScheduler` 是 C 负责的 Agent 调度模块，主要负责把不同 Agent 串联起来，形成完整的法律问答流程。

当前接入的 Agent 包括：

1. `RetrievalAgent`：调用 `/search` 接口，检索相关法条
2. `QAAgent`：调用 `/rag` 接口，生成最终法律问答结果
3. `SummaryAgent`：对检索到的法条做结构化总结

三个 Agent 不是同时运行，而是由 `AgentScheduler` 按顺序调度。

当前完整流程为：

```text
用户问题 -> RetrievalAgent -> QAAgent -> SummaryAgent -> 最终输出