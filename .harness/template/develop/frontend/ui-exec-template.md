# EXEC-<编号>：<PLAN 页面名称>

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 阶段：`ui-exec`
- 对应 Plan：`../1-ui-plan/plan-<编号>.md`
- 状态：`in-progress|completed|blocked`
- 前端服务：`<service-id>`
- 基线 Revision：`<开始执行时的 revision；未提交改动须如实说明>`

> 一个 EXEC 文件只记录一个 PLAN。PLAN 内的每次 TASK 执行、补充验证和遗留风险均追加到本文件；不得创建全局 `task.md`、`exec.md`，也不得将执行结果回写到 Plan 基线。

## TASK 执行情况

| TASK | 状态 | 实际修改位置 | 结果 | 偏差与回流 |
| --- | --- | --- | --- | --- |
| TASK-<编号>.01 | in-progress|completed|blocked | `<真实路径>` | <真实结果> | <none 或回流来源> |

## 实际变更

- <只记录已落入工程的变更；计划中的未执行项不写为完成。>

## 工程边界对照

必须按真实页面重判；上游错误的 `not-applicable` 必须推翻为 `applied` 或 `issue`。

| 维度 | 本页适用 | 对照结果 | 证据 |
| --- | --- | --- | --- |
| 表格 | yes/no | applied/not-applicable/issue | <真实实现或缺口> |
| 图表 | yes/no | applied/not-applicable/issue | <真实实现或缺口> |
| 数据格式化与空态 | yes/no | applied/not-applicable/issue | <真实实现或缺口> |
| 代码与请求边界 | yes/no | applied/not-applicable/issue | <真实实现或缺口> |

## 验证

| 类型 | 命令或场景 | 结果 | 证据 |
| --- | --- | --- | --- |
| test/lint/build/browser/http | <真实命令或场景> | passed/failed/blocked | <摘要或路径> |

## 追写记录

### yyyy-MM-dd HH:mm:ss｜TASK-<编号>.01｜<本次动作>

- 变更：<真实变更>
- 验证：<真实命令、结果或阻塞原因>
- 影响与遗留：<回归半径、风险或 none>
