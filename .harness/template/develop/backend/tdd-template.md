# <需求标题>（<plan-NN> 后端 TDD 记录）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 服务：`<service-id>`
- Plan 模块：`<plan-NN 或 plan-overview.md；单模块固定填写 plan-overview>`
- 外部设计：`2-external-design/external-design.md`
- TDD 文件：`3-tdd/tdd-<NN>.md`
- 契约路径：`<服务仓库相对路径>`
- Baseline Revision：`<40位revision>`
- Baseline SHA256：`<64位SHA256>`

## 骨架与测试

| 接口锚点 | Controller/DTO/Service | MockMvc | verify 命令与结果 |
| --- | --- | --- | --- |
| <锚点> | <路径> | <测试路径> | <真实结果> |

## 调用方与发布

- Consumers：<服务ID>
- 兼容期与发布顺序：<内容>

## 变更追写（仅追加）

> 证据维护遵循[记录追加规则](../../../rules/backend-delivery.md#记录追加)。

| 编辑时间 | 变更/通知 ID | 触发原因与变更摘要 | 影响的契约/测试 | 命令与真实结果 | Consumers 通知 |
| --- | --- | --- | --- | --- | --- |
| <yyyy-MM-dd HH:mm:ss> | <TDD-CHG-NN-NNN> | <内容> | <路径/测试> | <命令与结果> | <内容或 n/a> |
