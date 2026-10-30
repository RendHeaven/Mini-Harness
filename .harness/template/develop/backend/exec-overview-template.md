# <需求标题>（后端 Exec 总览）

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 服务：`<service-id>`
- 需求版本：`v<主版本>.<次版本>`
- Exec 状态：`planned|in-progress|implement|blocked|done|n/a`

## 模块索引

| Exec | Plan | TDD | TASK | 状态 | 外部变更文件 | 依赖/发布顺序 |
| --- | --- | --- | --- | --- | --- | --- |
| `exec-01.md` | `1-plan/plan-overview.md|plan-01-<slug>.md` | `3-tdd/tdd-01.md` | `TASK-BE-001` | planned/in-progress/implement/blocked/done/n/a | `n/a：具体理由` 或 `sql.md`/`nacos.md`/`permission.md`/`minio.md` | <内容> |

## 跨模块结论

- 代码与测试：<聚焦测试、verify、失败或 blocked 结论>
- 外部执行：<按 SQL、Nacos、权限、MinIO 汇总实际审批、执行、验证与回滚；无则写 n/a：具体理由>
- 发布与回滚：<服务、外部系统和消费者的顺序；回滚责任与条件>
