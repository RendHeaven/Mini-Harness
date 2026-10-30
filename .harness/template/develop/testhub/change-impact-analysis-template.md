# TestHub 代码变更影响分析

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

## 分析信息

- 需求版本：`v<版本>`
- 分析状态：`draft/generated-with-gaps/ready-for-generation`
- baseline revision：`<40位 Git commit 或实际缺口>`
- verified revision：`<40位 Git commit 或实际缺口>`
- 分析时间：`<yyyy-MM-dd HH:mm:ss>`

## 变更证据

| 证据 ID | 仓库 | 提交区间/契约版本 | 改动文件或契约 | 变更摘要 | 状态 |
| --- | --- | --- | --- | --- | --- |
| CHG-001 | <服务 ID> | <baseline..verified> | <相对路径> | <实际变更> | ready/blocked |

## 影响与回归映射

| 影响 ID | 变更证据 | 实现链路 | 受影响功能 | 影响类型 | 回归理由 | REQ | 用例/缺口 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IMP-001 | CHG-001 | <路由/组件/接口/服务/数据/消息链路> | <功能、页面或接口> | direct-change/indirect-impact/unchanged-regression | <共享依赖或调用关系> | REQ-xxx/跨 REQ | <case ID/GAP> | covered/blocked/not-applicable-with-evidence |

## 未改功能的独立性结论

| 功能 | 结论 | 独立性或影响证据 | 关联 IMP/GAP |
| --- | --- | --- | --- |
| <功能> | unchanged-regression/not-applicable-with-evidence/blocked | <代码、契约或调用链路径> | IMP-xxx/GAP-xxx |

## 分析缺口

| GAP | 缺口 | 对回归范围的影响 | 后续动作 |
| --- | --- | --- | --- |
| GAP-001 | <缺失的 revision、diff、源码或调用链> | <不能声明的覆盖结论> | <需要的证据或负责人> |
