# Agent 场景测试报告
## 1. 测试环境
| API 地址 | `http://172.20.10.2:8000`，
| score 阈值 | `0.6` |

## 2. 验收目标

- 至少测试 10 个用例；
- 覆盖劳动法、民法、刑法、公司法、消费者权益法等场景；
- 检查 RetrievalAgent 能否返回相关法条；
- 检查 SummaryAgent 能否生成结构化摘要；
- 检查异常、空输入和低相关度场景；
- 发现 Bug 时记录原因、修改内容和复测结果。

## 3. 场景测试记录
见test_outputs/agent_manual_test_20260716_100809.json

## 4.测试
```text
本轮共执行 10 个测试用例。
RetrievalAgent 能稳定调用 /search 接口并解析返回字段；
SummaryAgent 能正常生成结构化摘要；
测试中未发现问题
```
