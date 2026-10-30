# Review-<NN>：<模块标题>

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 对应：`1-plan/plan-<NN>-<slug>.md`、`3-tdd/tdd-<NN>.md`、`4-exec/exec-<NN>.md`
- 服务与 Revision：`<service-id>@<revision>`
- 接口文档：`6-interface-document/api-document.md`
- 状态：`planned|in_progress|passed|blocked`
- 范围 / 非范围：<本模块审查边界>
- 结论：`pending|passed|blocked`

## REQ 覆盖

| REQ | 结论 | 证据 |
| --- | --- | --- |
| REQ-001 | covered/not-covered | <代码、测试、接口或审查发现的真实证据> |

## 发现

| ID | 优先级 | 位置 | 维度 | 证据与影响 | 修复与复测 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| BR-001 | P0/P1/P2 | <路径> | <架构/安全/数据/性能/契约> | <事实> | <结果> | open/fixed/accepted |

## TestHub 测试盲区

- 接口、业务规则、数据、事务、Feign、缓存、消息、定时、并发、幂等和回滚：<内容>

## 复测追写（仅追加）

| 编辑时间 | 关联发现 | 修复与验证 | 结论 |
| --- | --- | --- | --- |
| <yyyy-MM-dd HH:mm:ss> | BR-<NNN> | <真实命令、结果和证据> | fixed/open |
