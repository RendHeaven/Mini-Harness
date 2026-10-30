# 产品事实与追溯

## 事实归属

PRD 是周期内唯一业务事实源；Discovery 保存 HYP 与反馈，accepted DEC → REQ 可追溯。原型表达界面和 Mock 数据，路径与共用方式见[项目资产](project-assets.md#项目原型与历史路径)。静态数据不代替接口事实，源码和长期契约仍由服务持有。

UI 先记录内容与 UI 规则，再生成逐轮文档和 Handoff。UI 不决定业务字段、流程、权限和验收；遇到这些变化按[角色执行约定](project-execution.md#角色执行)记录并询问用户，不自行修改其事实。产品和 UI 的代码权限见[原型写入边界](project-execution.md#原型写入边界)。

## PRD 修订

该版本 `product/<版本号>-prd.md` 第一次交付后开始追踪，初始化 `product/prd-changelog.md` 和 `prd-changes/revisions.yaml`。首次交付不表示定稿、封板或产品确认，也不由 Git 提交、推送或 Manifest `phase` 判定。开始追踪后，每次完整的正文修改必须追加 `CHG-*`；同一次连续编辑可合并为一条，后续独立修改不得覆盖旧记录。

每次通过 `prd_revision.py` 原位修改，保存 CHG 独立文档、原因、真实时间、影响的 REQ/文件和必要的局部 diff。`prd-changelog.md` 是可读索引，`prd-changes/revisions.yaml` 使用修订 Schema 2 记录操作；不保存 `baseline.md`、`*.before.md` 或 `*.after.md` 全文副本，也不要求持久保存正文摘要链。工具写入事务中的临时摘要只用于防止覆盖后续编辑，不绑定角色确认。历史记录不可覆盖，回滚追加记录，未完成事务先恢复；具体命令见 [PRD 构建步骤](../skills/product/prd-build.md#workflow)。

原型改动沿用 `product/mock-changelog.md`、UI 调整文档或原型补建的 iterations，每次修改追加唯一 CHG、独立 UI-ADJ 文档或 iteration，记录时间、原因、修改文件、影响与验证；持续追加的 Mock 日志须提供 CHG 锚点，原型补建引用 iteration 序号，不为 Gate 再建一套原型变更日志。每次封板只记录一次真实确认及其覆盖的变更，之后仍原位修改并持续记账。完整历史由实际 Git 提交保存；逐次变更记录不承诺恢复每个未提交的中间全文。

## 派生与回流

Dev Guide、Word 导出为可选派生物，来源变化后不能当作当前结论。这些派生物不成为其他角色前置。产品反问的分轮问答与共同理解确认见 [产品反问（grilling）](../skills/product/prd-review.md#decision-rules)，不强制落盘报告；确认后已授权的业务变更仍回写 Discovery 并按 PRD 修订协议执行。只读代码分析不授权产品修改代码。

前后端共同消费当前 PRD 和项目原型，各轨道的 `sources` 记录路径和已消费的变更引用。确认覆盖范围及新增变更的独立复核统一见 [Gate 规则](review-gates.md)。

## 来源与验证

Gate 和 Execution 不再要求 PRD/原型的整份摘要或不可变副本，也不向 `.harness/evidence/` 写入产品快照。独有的验证截图、测试报告、原型补建证据继续按各自流程保存；它们的校验摘要不等于封板。外部资源仍需固定版本或本地化。历史资产及其导入摘要见[项目资产](project-assets.md)。
