---
name: execute-java-backend-plan
description: 当后端 TDD 检查完成时使用；TDD 告警不阻止执行可行部分。在当前 plan 和契约基线内实现 Java 业务逻辑并用 Service JUnit 与 Maven verify 证明核心规则。
---

# Java 后端 Exec

## Objective

按 Plan 模块完成真实实现和外部变更资产，保留与 plan/baseline 的偏差、测试、审批和回滚证据。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 文件编号、总览与详情分工、追写及后端 TASK 状态遵循[后端交付规则](../../rules/backend-delivery.md)。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前 Plan 模块、同编号 `tdd-NN.md`、契约基线、测试骨架、目标服务源码和用户已有改动。
- 来源失效或必要环境不可用时记录对应 TASK 的告警和真实 blocked 状态，并继续其他可执行 TASK；人审/DBA 未放行时不得执行相应高风险写入、DDL 或迁移，也不得伪造审批。

## Workflow

1. 按后端交付规则建立 Exec 总览及已开始模块的详情，逐项更新 TASK 表；以外部设计作为 SQL、Nacos、定时任务等实现依据。
2. 实现 Controller、Service、Mapper、DTO、配置和适用外部依赖。
3. 为核心规则补充 Service JUnit，覆盖正常、边界、异常、权限和适用并发/幂等。
4. 每个 `exec-NN.md` 必须有“外部执行记录”章节。实际执行 SQL/DDL/数据修复、Nacos、权限或 MinIO 时，在 `4-exec/` 根目录按主体追加无凭据文件：`sql.md`、`nacos.md`、`permission.md`、`minio.md`；记录关联外部设计、审批、实际步骤、验证与回滚。无外部执行则写 `n/a：具体理由`。
5. 不得在 Exec 临时设计 SQL、Nacos 或定时任务。对外部设计资产只可同步、执行和记录证据；任何设计内容变化必须回流 `2-external-design/`，业务语义变化同时回流 Plan。未经授权不得运行 SQL、修改 Nacos、权限或 MinIO。
6. 运行聚焦测试、目标模块和适用根级 `mvn verify`。
7. 使用 Exec 总览、模块与外部变更模板记录变更、偏差、证据、审批和风险。

## Decision rules

- 业务或契约语义变化回到 plan/TDD，不只在实现中兼容。
- 使用目标服务真实 Maven 模块和命令；不删除有效断言、吞异常或使用 `-DskipTests`。
- 核心业务规则使用 Service JUnit；DDL、数据迁移和高风险数据操作必须记录 DBA 审批、前后校验、执行窗口与回滚。
- 已确认 `backend n/a` 的 Plan 仍保留对应 `exec-NN.md`，在 TASK 章节写 `n/a：<后端无执行 TASK 的具体依据>`，并记录数仓或其他责任方的外部变更交接；不得伪造 `TASK-BE`。
- 生成外部设计不等于已执行。需要 DBA、配置管理员、IAM/安全负责人、对象存储管理员或变更窗口的事项，必须在对应 `exec-NN.md` 和文件内保留真实状态；未获授权不得实际写库、发布 Nacos 或修改权限/桶策略。
- 严禁提交密码、Token、AccessKey、SecretKey、连接串或生产数据。
- 结构化接口文档在 Exec 后由 Plan、TDD、Exec 共同生成；不得在单独的实现文件中维护第二套接口定义。

## Output contract

输出 `4-exec/exec-overview.md`、每个已执行 Plan 对应的 `exec-NN.md`、适用的 `4-exec/sql.md|nacos.md|permission.md|minio.md`、实现和测试；未完成 TASK、外部审批或 verify 失败保留真实状态并告警，不阻止进入本地接口测试阶段检查。
