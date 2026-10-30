# Nacos 变更

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

- 类型：`nacos`
- 目标系统/环境：<真实目标；不得包含凭据>
- 状态：`done|blocked`
- 前置条件与审批：<配置管理员审批、命名空间、发布窗口>
- 验证：<健康检查、配置读取与回归>
- 回滚：<历史配置版本或回退步骤>

## 配置差异

```yaml
<dataId>:
  <key>: <value>
```

仅包含允许发布的配置差异；禁止密码、Token、AccessKey、SecretKey、连接串。
