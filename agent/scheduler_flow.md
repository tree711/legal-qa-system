# AgentScheduler 调度流程图

## 1. 当前版本说明

当前由 C 负责的 AgentScheduler 已经可以完成基础调度流程。

当前流程是：

用户输入法律问题 -> Scheduler 接收问题 -> 调用 `/search` 检索相关法条 -> 调用 QAAgent 的 `/rag` 生成最终回答 -> 整理输出答案和引用法条

其中：

- `/search`：负责检索相关法条
- `/rag`：负责检索增强问答，返回最终回答和引用法条
- `QAAgent`：负责封装 `/rag` 调用
- `AgentScheduler`：负责组织整体执行顺序

---

## 2. 当前 AgentScheduler 调度流程图

```mermaid
flowchart TD
    A["用户输入法律问题"] --> B["AgentScheduler 接收问题"]
    B --> C["调用 POST /search"]
    C --> D["返回相关法条"]
    D --> E["调用 QAAgent"]
    E --> F["QAAgent 构造 prompt 和 top_k"]
    F --> G["调用 POST /rag"]
    G --> H["/rag 生成最终回答"]
    H --> I["返回 answer 和 references"]
    I --> J["Scheduler 整理最终输出"]
    J --> K["输出最终答案、引用法条和调度步骤"]