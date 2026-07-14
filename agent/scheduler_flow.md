# QAAgent 调度流程图

## 1. 当前版本说明

当前由 C 负责的 QAAgent 已经可以调用组长提供的 `POST /rag` 接口。

当前流程是：

用户输入法律问题 -> QAAgent 调用 `/rag` -> `/rag` 内部完成检索和生成 -> 返回最终回答和引用法条

---

## 2. 当前 QAAgent 调度流程图

```mermaid
flowchart TD
    A[用户输入法律问题] --> B[QAAgent 接收问题]
    B --> C[构造请求体 prompt 和 top_k]
    C --> D[调用 POST /rag 接口]
    D --> E[/rag 检索相关法条]
    E --> F[/rag 拼接 Prompt]
    F --> G[/rag 调用大模型生成回答]
    G --> H[返回 answer 和 references]
    H --> I[QAAgent 整理结果]
    I --> J[输出最终回答和引用法条]