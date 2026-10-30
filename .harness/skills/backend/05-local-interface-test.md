---
name: test-java-backend-interface-locally
description: 当后端 Exec 完成检查时使用；按契约基线执行可行的真实 HTTP、Maven 全集和必要只读数据验证，产出可复核接口测试报告。
---

# 后端本地接口测试

## Objective

使用真实服务验证实现结果，为 Exec 回流、发布判断和后续测试提供可信请求、响应、错误和副作用证据。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 文件编号、总览与详情分工、追写及后端 TASK 状态遵循[后端交付规则](../../rules/backend-delivery.md)。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 契约基线、Exec、服务启动规则、环境、账号、Token 和允许的数据范围。
- 服务、依赖、权限或测试数据不可用时标记 blocked，不伪造结果。

## Workflow

1. 运行目标模块及必要根级 `mvn verify`，先关闭回归失败。
2. 根据已开始的 Plan/TDD/Exec 模块创建 `5-local-interface-test/localTest-NN.md`；先在总览登记范围、依赖与状态，再在模块记录中执行和追写证据。
3. 启动真实服务，按 baseline 为每个接口准备可复核请求。
4. 覆盖正常、空、边界、筛选/排序、非法参数、权限、冲突和重复提交。
5. 对写接口在授权数据上验证前后状态；异步结果记录等待条件和超时。
6. 保存脱敏请求、真实响应、断言、日志摘要和必要只读数据证据。
7. 使用接口测试模板记录 Pass/Fail/Blocked、根因、修复和复测；后续复测必须追写至原模块文件。

## Decision rules

- 使用真实服务和可复核 HTTP 证据；服务、依赖、权限或授权样本不可用时标记 `blocked`，不能以 Mock 或 Maven 测试替代真实接口验证，也不虚报 Pass。
- 实现错误必须追写到原 `exec-NN.md` 并回流对应 TASK；仅在修复后以真实服务复测通过，方可更新模块状态。baseline 错误返回 TDD 并通知 consumers。

- 已确认 `backend n/a` 的 Plan 仍保留对应 `localTest-NN.md`，写明无独立后端实现/HTTP 变更、保持的既有接口，以及数仓或其他责任方的验证交接；不得把它写成未执行的后端接口通过。
- 失败未闭环时保留 Fail/Blocked 和告警，不阻止进入接口文档阶段；接口文档仍只依据 Plan、TDD、Exec 生成，不复制本地测试结论。
- 密钥、Token 和个人数据不得写入报告。

## Output contract

输出后端交付规则指定的 LocalTest 总览和模块记录。所有适用接口按真实结果记录，失败、Blocked 或 verify 未通过形成告警，阶段检查仍完成并允许继续。
