# 前端 Mock 验证记录

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 状态：`passed|failed|blocked`
- 前端服务：`<service-id>`
- 分支与 Revision：`<branch>@<revision>`
- Mock 启动命令：`<command>`
- Mock 访问地址：`<url>`
- 验证时间：`yyyy-MM-dd HH:mm:ss`

## 启动与隔离

| 检查 | 命令/场景 | 结果 | 证据 |
| --- | --- | --- | --- |
| Mock Runtime 启动 | <command> | passed/failed/blocked | <log/screenshot> |
| Mock 请求被拦截 | <network scenario> | passed/failed/blocked | <network evidence> |
| 普通开发未启用 Mock | <command> | passed/failed/blocked | <evidence> |
| 生产构建未包含 Mock | <build command> | passed/failed/blocked | <evidence> |

## 场景验证

| 接口/页面 | 场景 | 预期 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| <path/route> | normal/empty/error/boundary | <expectation> | passed/failed/blocked | <evidence> |

## 质量与交接

| 项目 | 命令/结论 | 结果 | 说明 |
| --- | --- | --- | --- |
| lint | <command> | passed/failed/blocked | <detail> |
| test | <command> | passed/failed/blocked | <detail> |
| build | <command> | passed/failed/blocked | <detail> |

- 未覆盖接口：`<list>`
- 维护动作：`<contract change/update owner>`
- 真实联调边界：`Mock 验证不替代真实接口联调、生产构建、TestHub 用例同步或实际测试执行结论。`
