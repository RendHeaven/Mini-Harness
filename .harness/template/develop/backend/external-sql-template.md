# SQL 变更

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 记录原则：按 Exec/TASK 追加，不能覆盖既有变更记录。

## Exec-<NN> / TASK-BE-<NNN>

- 编辑时间：`<yyyy-MM-dd HH:mm:ss>`

- 类型：`sql`
- 目标系统/环境：<真实目标；不得包含连接串或凭据>
- 状态：`done|blocked`
- 前置条件与审批：<DBA 审批、执行窗口、备份>
- 执行说明：<幂等、批次与锁策略>
- 前置校验：<只读 SQL 或校验方法>
- 后置校验：<只读 SQL 或校验方法>
- 回滚：<受审计回滚步骤>

## 外部设计 SQL 来源与服务仓库资产

- 需求版本：`v<主版本>.<次版本>`
- 外部设计新增结构草案：`n/a：<无新增表/结构理由>|2-external-design/sql/v<主版本>.<次版本>-create-structure.sql`
- 外部设计编辑/删除结构草案：`n/a：<无编辑结构或删表理由>|2-external-design/sql/v<主版本>.<次版本>-alter-drop-structure.sql`
- 外部设计数据草案：`n/a：<无 DML 理由>|2-external-design/sql/v<主版本>.<次版本>-data.sql`
- 服务仓库同步位置：`<服务仓库相对路径>/v<主版本>.<次版本>-<类型>.sql`
- 执行顺序：`<按外键依赖填写；重置场景为 alter-drop-structure → create-structure → data → 应用发布>`（不适用项跳过）

外部设计草案与服务仓库同步文件均仅允许以下三类；Exec 必须校验二者内容一致：

- `版本号-create-structure.sql`：只含新增表、新增字段、索引、约束、序列、视图、触发器、函数或存储过程。
- `版本号-alter-drop-structure.sql`：只含编辑既有表结构、删除结构或删除表；需要先删后建时，删除语句必须放在本脚本。
- `版本号-data.sql`：只含 DML（初始化、回填、修复、迁移、清理）。

不得按 TASK、Plan、日期、Flyway 序号或其他维度新增 SQL 文件；无对应类别时不生成空脚本，必须保留 `n/a：具体理由`。

## SQL

```sql
-- 在此记录待执行 SQL 摘要或校验 SQL；完整 SQL 只存放上方声明的版本脚本。
-- 禁止填入生产数据、密码、Token 或连接串。
```
