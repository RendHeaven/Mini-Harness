---
name: prepare-java-backend-tdd
description: 当 Plan 与外部设计完成检查时使用；在契约所有者仓库生成实现前契约基线、可编译骨架和先行 MockMvc 测试，并固定真实 baseline revision 与 SHA256。
---

# Java 后端 TDD

## Objective

把 plan 转成可验证的契约基线、Controller/Service 骨架和先行失败或最小可运行测试。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 文件编号、总览与详情分工、追写及后端 TASK 状态遵循[后端交付规则](../../rules/backend-delivery.md)。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前 Plan、外部设计及其真实确认状态、目标服务规则、真实响应/异常包装、契约路径和 Maven 测试设施。
- 契约 owner、类型、错误语义或调用方不清时记录告警和真实 blocked 状态，继续不依赖缺失事实的内容，不补造契约。Plan 中未关闭 `DEC-*` 或 `TDEC-*` 的阻塞对象不得进入契约、Controller、DTO、Service 桩或测试。

## Workflow

1. 按后端交付规则登记 TDD 总览，确认本次执行的 Plan 模块及其外部设计。
2. 在 services.yaml 允许的 contractPaths 内选择稳定接口文档路径。
3. 只为来源已确认且不依赖未关闭 `DEC-*` 或 `TDEC-*` 的范围生成 draft/locked 契约基线，明确路径、鉴权、字段、类型、校验、响应、错误和副作用；阻塞接口只记录问题、决策 ID 与解除条件。
4. 只为该可执行范围生成或调整 Controller、DTO、Service 接口和最小桩实现。
5. 只将来源已确认的 acceptance 转成 MockMvc 测试，覆盖正常、边界、异常和权限；不得以测试或桩实现替业务决定状态、持久化或权限语义。
6. 运行目标模块及适用根级 `mvn verify`。
7. 提交基线并在 execution 记录 path、baselineRevision 和 baselineSha256。
8. 使用 TDD 模板记录模块测试、命令和前端通知，按交付规则追写并同步总览。

## Decision rules

- baseline 只表示实现前设计，不能替代由 Plan、TDD、Exec 汇总生成的结构化接口文档。
- “可执行部分”仅指调研、编译检查和不依赖未关闭 `DEC-*` 或 `TDEC-*` 的已确认子范围；它不授权新增公开接口、状态迁移、持久化实体、编号规则、权限规则或外部副作用。
- breaking change 必须记录调用方、兼容期和发布顺序。
- 使用目标服务真实 Maven 模块和命令；禁止 `-DskipTests`、忽略失败、降低断言或伪造响应样例制造通过。
- Controller 使用 MockMvc 覆盖正常、边界、异常和权限。
- 契约 baseline 变更时同步更新 `execution.yaml` 的 revision 和 SHA256。

## Output contract

输出后端交付规则指定的 TDD 总览、模块记录，以及服务仓库内契约基线和测试骨架。verify 失败或 baseline 引用无效时保留真实结果并告警，不阻止进入 Exec 检查。
