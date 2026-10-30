---
name: assemble-java-backend-external-configuration-checklist
description: 当后端 Exec 与 Review 完成后使用。只汇总仍需在外部系统落地的 SQL、Nacos、权限或对象存储配置；不记录数据口径确认、测试结果、内部实现问题或发布步骤。
---

# 后端外部配置清单

## Objective

在进入 研发证据检查 前，形成一份仅包含“仍待外部配置”的待办清单。每一项都要能明确回答：需要在哪个外部系统做什么变更、由谁审批/执行，以及执行记录在哪里。

## Inputs

- 产物相对[工作流](../../workflow/backend-workflow.md#阶段执行)指定的阶段根。
- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- `4-exec/exec-NN.md`：模块声明的外部执行及其状态。
- `4-exec/sql.md`、`nacos.md`、`permission.md`、`minio.md`：对应外部系统的执行记录（存在时）。
- `2-external-design/`、`7-review/`：仅用于核对外部设计或执行是否遗漏；不将数据口径、样本、接口联调或普通风险写入清单。

## Workflow

1. 扫描 `4-exec/` 的外部执行记录，只提取尚未完成、需要在外部系统执行或审批的变更。
2. 类型仅限 `sql`、`nacos`、`permission`、`minio`；同一系统、环境和同一变更合并为一项，并保留关联 Exec/TASK 和外部变更记录路径。
3. 每项写明目标系统/环境、具体配置或变更、执行/审批责任方、真实状态和执行记录。不得把只读查询、数据样本、业务口径、前后端联调、代码缺陷或发布协调混入。
4. 如果没有待外部配置项，直接写 `无待外部配置项。`，不要为了覆盖类型虚构条目。
5. 生成 `8-checklist/checklist.md`，仅引用原始执行记录；不得复制密码、Token、连接串、AccessKey、SecretKey、内部 URI 或生产数据。

## Decision rules

- 本清单不执行 SQL、Nacos 发布、权限授予或对象存储修改；这些动作仍由相应责任方在受控流程中执行。
- 它不用于记录已完成的外部变更，也不替代 `4-exec/` 下的外部执行记录、测试、发布审批或 TestHub 原始记录。
- 外部配置完成后，应先追写对应的 `sql.md`、`nacos.md`、`permission.md` 或 `minio.md` 及关联 Exec，再从本清单移除该事项。
- 清单状态仅允许 `pending` 或 `blocked`；已完成项应留在原外部变更记录中，不得继续留在清单。尚未授权、环境不可达或依赖方未配合时标记 `blocked`，保留责任人、条件和回流目标。

## Output contract

输出唯一文件 `8-checklist/checklist.md`，使用 `template/develop/backend/checklist-template.md`。除统一的时间元数据与编辑记录外，文件只保留“待外部配置项”表；有事项时每行必须有来源、类型、外部系统/环境、变更内容、执行/审批责任方、状态和外部执行记录。无事项时使用约定的空清单句，不附带输入盘点、已完成项、测试结果、发布建议或汇总。
