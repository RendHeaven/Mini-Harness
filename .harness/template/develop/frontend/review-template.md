# <需求标题>（前端独立 Review）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 服务与 Revision：`<service-id>@<revision>`
- 接口文档：`<owner:path>`
- 结论：`pending|passed|blocked`

## 工程边界对照

按真实页面重判；上游错误的 `not-applicable` 记为 `issue`。

| 维度 | 对照结果 | 发现 |
| --- | --- | --- |
| 表格 | passed/issue/not-applicable | <rowKey、render 内请求、分页撑高或 none> |
| 图表 | passed/issue/not-applicable | <空态留白、猜测口径、resize 或 none> |
| 数据格式化与空态 | passed/issue/not-applicable | <假值判断吞掉 0、散落格式化或 none> |
| 代码与请求边界 | passed/issue/not-applicable | <绕过 request、未确认公共改动或 none> |

## 发现

| ID | 优先级 | 位置 | 维度 | 证据与影响 | 修复与复测 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| FR-001 | P0/P1/P2 | <路径> | <状态/权限/接口/竞态/视觉/构建/工程边界> | <事实> | <结果> | open/fixed/accepted |

## Gate 检查（未满足项告警）

- [ ] P0/P1 已修复或由真实负责人接受风险
- [ ] 工程边界对照已按真实页面重判
- [ ] 修复后测试、构建和浏览器验证已重跑
