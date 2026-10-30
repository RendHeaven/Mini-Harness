# TestHub Markdown v1 规则

## 文档结构

阶段根由 [TestHub 工作流](../workflow/testhub-workflow.md#阶段执行)解析，`cases.md` 必须按以下顺序包含：

1. `# TestHub AI UI 测试用例`
2. `## 文档信息`：文档标识、协议版本 `external-harness-markdown-v1`、Excel 字段基线 `external-harness-excel-v3`、需求版本、Git 提交、生成时间，以及 `rules/document-timestamps.md` 规定的创建时间、最后编辑时间、时区和编辑记录。时间字段与编辑记录放在“文档信息”内，不新增用例详情标题或导入表列。
3. `## 参考上下文`：类型、路径、状态、SHA256、使用说明。缺失来源也必须列出。
4. `## 测试用例`：先包含 `## TestHub 导入用例表`，并使用 Excel v3 完全一致的 13 列表头：`用例编号`、`模块`、`页面`、`功能`、`测试标题`、`前置条件`、`测试步骤`、`预期结果`、`优先级`、`用例类型`、`断言`、`测试数据`、`备注`；每个用例再使用 `### <case_id>：<测试标题>` 记录可读详情。

每条用例必须包含：模块、页面、功能、优先级、用例类型、前置条件、`#### 测试步骤`、`#### 预期结果`、`#### 断言`、`#### 测试数据`、`#### 备注`。测试数据是唯一 JSON 代码块。

## 字段与安全规则

- 功能仅允许 `query`、`detail`、`edit`、`delete`、`pagination`、`create`、`upload`、`download`、`share`；优先级仅允许 `P0`、`P1`、`P2`、`P3`。
- 导入表是 TestHub 解析和同步的唯一用例载体；表中的用例编号必须与详情标题的 case ID 一致且唯一。在同一逻辑用例的修订中保持稳定；文档是同一外部文档的完整当前集合。
- 测试数据必须是 JSON 对象；自定义变量必须同时出现在步骤、预期和断言中。
- 需要数据的 detail/edit/delete 用例必须独立声明 Fixture；禁止依赖 create 用例执行顺序。
- 所有写入测试数据用 `${safe_data_prefix}`；清理只能处理本轮创建的数据，并验证清理结果。
- Mock 步骤必须包含完整可解析的 `mock_api_response(...)`，断言页面可观察状态，最后清除 Mock。
- 页面、模块、字段、按钮只使用已参考上下文中的真实可见名称；缺失时记录 `generated-with-gaps`，不编造。
- 每个用例必须能通过“备注”或同目录 `test-design.md`、`coverage-matrix.md` 追溯到至少一种设计方法（等价类、边界值、场景、状态转换、错误推测、判定表或正交）及风险标签或自动化缺口。
- 当用例来自代码变更影响分析时，备注还必须引用 `change-impact-analysis.md` 中的 `IMP-*` 及影响类型（`direct-change`、`indirect-impact` 或 `unchanged-regression`）；未改功能的回归用例同样适用。
- 安全、SQL、性能和并发用例仅在上下文提供可观察权限、口径、阈值、数据规模或受控环境时进入正式导入表；其余内容留在覆盖矩阵中标记 `blocked` 或 `not-applicable-with-evidence`。

## 同步规则

- TestHub 上传只接受完整文档 multipart 导入；不得把每条用例拆为单独远程请求。删除必须使用 `harness-document-sync`，不能用残缺文档覆盖。 metadata 不能包含 Secret。
- 同一 `external_document_id` 的更新不能只上传失败用例；省略的 case 会被 TestHub 视为删除。
- 上传、查询、执行、查询 Run、失败重试和删除同步文档均使用匿名 Harness 生命周期接口；仅可访问 `source_type=gitlab_harness` 项目，不能使用手工项目 ID。不得配置或发送 Authorization 或登录 Token。
- 每次逻辑不同的上传或删除都生成新 `Idempotency-Key`；超时重试同一次请求必须复用原键。`replayed: true` 代表历史导入结果重放。
- 同步报告记录导入统计和 blocked 原因；导入不代表执行或通过。Run 必须记录 `run_id`，并以终态 `status`、`summary` 和 `case_results` 判断结论。
- 回调服务必须在 15 秒内返回 2xx，以 `Idempotency-Key` 或 `run_id` 去重并允许重复通知；基于 HTTPS、网络白名单或反向代理保护回调地址。

- 不记录或输出 Authorization、密码、access/refresh token、Cookie、登录态和敏感测试数据；管理接口若另有需要，必须使用独立受保护流程。

## 本地路径与同步元数据

本地产物路径从工作流解析，上传工具的 `--file` 指向实际 `cases.md`。multipart metadata 的 `documentPath` 来自同步配置（工具默认值为 `testhub/cases.md`），与本地文件参数分开处理；不得根据本地目录重命名擅自改写配置值。稳定 ID 沿用项目配置。
