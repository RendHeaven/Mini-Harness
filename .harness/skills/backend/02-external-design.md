---
name: design-java-backend-external-changes
description: 当 Java 后端 Plan 涉及 SQL、Nacos、定时任务、权限、对象存储、消息或外部客户端时使用；产出可评审的外部设计资产，但不安排或执行变更。
---

# Java 后端外部设计

## Objective

将 Plan 中已确认的外部或运行条件设计固化为独立、可评审的资产，供 TDD 与 Exec 引用。本阶段不编码、不申请审批、不指定真实执行窗口、不备份、不执行或记录外部变更。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 当前 Plan、关联 `TASK-BE-*` 与已确认的 `TDEC-*`。
- 真实服务配置、数据库结构、调度框架、消息或外部客户端证据。
- 外部设计依赖未确认业务语义时回流 Plan；运行环境或平台能力不足时保持 `blocked`，不得虚构配置或脚本。

## Workflow

1. 识别每项关联 TASK 的 SQL、Nacos、定时任务、权限、对象存储、消息或外部客户端设计；无外部设计时明确 `n/a` 理由。
2. 在 `2-external-design/external-design.md` 记录类型、关联 TASK、来源、目标对象、设计内容、兼容性、风险与状态。
3. 数据变更需要时，在 `2-external-design/sql/` 生成可评审 SQL 草案，按 `create-structure`、`alter-drop-structure`、`data` 分类；无对应类别不创建空文件。
4. 定时任务明确稳定标识、触发条件、并发/重复处理、失败处理、可观测性与禁用方式；Nacos 等配置只记录无凭据的键、作用域、默认值和兼容影响。
5. 外部设计变更影响 Plan 业务语义、接口、数据口径或 TASK 时回流 Plan；仅实现细节变化可在本阶段追写。

## Decision rules

- 设计资产必须关联 Plan TASK 和来源证据；不得以外部设计补造产品规则。
- SQL 草案是设计输入，不等同于获批、备份、执行窗口、执行顺序或已落库事实。
- 禁止写入密码、Token、连接串、AccessKey、SecretKey 或生产数据。
- Exec 只记录审批、执行、验证与回滚事实；其发现的设计变更回流本阶段。

## Output contract

输出 `2-external-design/external-design.md`，以及适用的 `2-external-design/sql/<版本>-create-structure.sql`、`<版本>-alter-drop-structure.sql`、`<版本>-data.sql`。外部设计必须与 Plan TASK 可追溯；无外部设计时只输出正文和具体不适用依据。
