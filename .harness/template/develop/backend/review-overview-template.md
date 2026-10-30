# <需求标题>：后端 CodeReview 总览

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 服务与 Revision：`<service-id>@<revision>`
- 阶段：`7-review`
- 生成时间：`<yyyy-MM-dd HH:mm:ss>`
- 总体状态：`planned|in_progress|passed|blocked`

## 模块矩阵

| 模块 | Plan | TDD | Exec | LocalTest | 接口文档 | Review | 状态 | 当前结论 / 依赖 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <NN> | `1-plan/plan-<NN>-<slug>.md` | `3-tdd/tdd-<NN>.md` | `4-exec/exec-<NN>.md` | `5-local-interface-test/localTest-<NN>.md` | `6-interface-document/api-document.md` | `review-<NN>.md` | planned/in_progress/passed/blocked | <摘要> |

## 共享验证与跨模块依赖

- <revision、Maven/SQL/环境等共享证据>

## REQ 聚合

| REQ | 模块 | 结论 | 模块证据 |
| --- | --- | --- | --- |
| REQ-001 | <NN> | covered/not-covered | `review-<NN>.md` |

## 全局发现索引

| ID | 优先级 | 所属模块 | 摘要 | 状态 |
| --- | --- | --- | --- |
| BR-001 | P0/P1/P2 | <NN> | <摘要> | open/fixed/accepted |

## TestHub 测试盲区

- <跨模块测试盲区；模块内详细证据见 review-NN.md>

## 阶段结论

- <结论、回流和下一步>
