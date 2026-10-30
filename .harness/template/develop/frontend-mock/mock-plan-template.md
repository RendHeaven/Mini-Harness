# 前端 Mock 方案

<!-- atlas:generated document-timestamps:start -->
- 创建时间：`<yyyy-MM-dd HH:mm:ss>`
- 最后编辑时间：`<yyyy-MM-dd HH:mm:ss>`
- 时区：`Asia/Shanghai`
- 编辑记录：
  - `<yyyy-MM-dd HH:mm:ss>`｜创建｜首次生成本文档。
<!-- 后续每次编辑在编辑记录末尾追加“时间｜操作｜摘要”，同步最后编辑时间；不得覆盖历史记录。 -->
<!-- atlas:generated document-timestamps:end -->

- 状态：`draft|ready|blocked`
- 前端服务：`<service-id>`
- 目标分支：`<branch>`
- 目标页面/路由：`<route>`
- Mock 启动命令：`<command>`
- Mock 访问地址：`<url>`
- 运行时方案：`MSW|Vite middleware|其他`

## 工程现状

| 项目 | 当前事实 | 证据路径 |
| --- | --- | --- |
| 启动脚本 | <事实> | <path> |
| 请求基址与前缀 | <事实> | <path> |
| 代理规则 | <事实> | <path> |
| 现有 Mock/测试设施 | <事实或无> | <path> |

## 接口与场景范围

| 接口 | 方法 | 页面/功能 | 场景 | 数据来源 | 是否 Mock |
| --- | --- | --- | --- | --- | --- |
| <path> | GET/POST | <feature> | normal/empty/error/boundary | real-sanitized/synthetic/assumption | yes/no |

## 加载与隔离设计

- Mock 模式：`<mode 与环境变量>`
- Runtime 入口：`<path>`
- 真实模式：`<command 与请求去向>`
- 生产禁用策略：`<build-time guard>`
- 漏拦截策略：`<error/warn/explicit exception>`

## 风险与待确认

| 项目 | 影响 | 处理方式 | 状态 |
| --- | --- | --- | --- |
| <risk> | <impact> | <action> | open/closed |
