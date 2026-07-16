# Agent 框架选型说明

## 1. 项目需求

本项目需要构建法律法规智能问答系统，并实现检索 Agent、问答 Agent、总结 Agent 及调度逻辑。成员 B 负责 `RetrievalAgent` 与 `SummaryAgent`，两个模块需要调用组长提供的 FastAPI 接口，并能够被成员 C 的调度器直接导入和调用。

## 2. 候选方案比较

### LangChain

LangChain 提供统一的 Tool、Agent 和 Chain 抽象，适合将已有 Python 函数快速封装为可调用工具。它与 FastAPI、requests 等 Python 组件集成简单，便于把 `/search` 接口封装为检索工具，也方便后续由调度器串联多个 Agent。其社区资料较多，学习成本相对较低。

### AutoGen

AutoGen 更侧重多个对话 Agent 之间的自动协作，适合复杂的多角色讨论与任务分配。但本项目当前的调用流程较固定，主要是“检索—总结—问答”，如果直接使用 AutoGen，会增加会话管理和配置成本。

### LangFlow

LangFlow 提供可视化流程搭建能力，适合快速展示 Agent 流程。但其核心逻辑依赖图形化配置，不如纯 Python 代码便于 Git 协作、单元测试和成员之间的模块复用。

## 3. 最终选择

本项目选择 **LangChain** 作为 Agent 框架。主要原因是：第一，现有系统已经使用 Python 与 FastAPI，LangChain 可以直接将 `RetrievalAgent` 和 `SummaryAgent` 封装为 Tool；第二，项目流程明确，不需要复杂的多 Agent 自主对话；第三，LangChain 便于编写单元测试、处理异常并与成员 C 的调度器集成；第四，代码结构清晰，适合在 Git 分支中协作开发。因此，LangChain 在开发效率、可维护性和项目匹配度方面更符合本项目需求。
