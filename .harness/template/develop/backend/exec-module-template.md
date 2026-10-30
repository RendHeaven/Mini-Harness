# <需求标题>（后端 Exec-<NN>）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 服务：`<service-id>`
- Plan：`1-plan/plan-overview.md|plan-<NN>-<slug>.md`
- 外部设计：`2-external-design/external-design.md`
- TDD：`3-tdd/tdd-<NN>.md`
- Exec：`4-exec/exec-<NN>.md`
- 状态：`planned|in-progress|implement|blocked|done|n/a`

TASK 状态、唯一性及退出条件见[后端交付规则](../../../rules/backend-delivery.md#task-状态)。

## TASK

| TASK | 状态 | 修改位置 | 实现与测试 | 偏差/审批/风险 |
| --- | --- | --- | --- | --- |
| TASK-BE-001 | planned/in-progress/implement/blocked/done/n/a | <真实路径> | <JUnit、MockMvc 与 verify> | <内容> |



已确认 `backend n/a` 的模块不使用 TASK 表，改写 `n/a：<后端无执行 TASK 的具体依据>`，但仍须记录外部变更与交接状态。

## 外部执行记录

无外部变更时：`n/a：<具体理由>`。

| 类型 | 状态 | 文件 | 外部设计与目标系统/环境 | 执行、验证与回滚 |
| --- | --- | --- | --- | --- |
| sql/nacos/permission/minio | done/blocked | `sql.md`/`nacos.md`/`permission.md`/`minio.md` | <真实目标与审批状态> | <内容> |

外部文件仅保存无凭据的变更说明或脚本；生成不等于已执行。

## 模块执行证据

- 代码与测试：<命令、结果、revision>
- 偏差与调用方通知：<内容或 n/a：具体理由>

## 变更追写（仅追加）

本节按[Exec 追写规则](../../../rules/backend-delivery.md#exec-追写)填写。

### TASK-BE-001

| 编辑时间 | 触发原因与变更 | 代码/外部文件 | 验证与结果 | 审批、风险与消费者通知 |
| --- | --- | --- | --- | --- |
| <yyyy-MM-dd HH:mm:ss> | 首次 Exec：<摘要> | <真实路径或 n/a：具体理由> | <命令与结果> | <内容或 n/a：具体理由> |
