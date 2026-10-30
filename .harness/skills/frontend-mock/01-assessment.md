---
name: assess-frontend-mock
description: 在新增前端 Mock 运行方式前，盘点真实工程、接口和风险，形成可执行的 Mock 方案与范围边界。
---

# 前端 Mock 盘点与方案

## Objective

基于真实前端工程，确定 Mock 的目标、接口边界、运行时方案、数据来源和不覆盖范围，避免把临时页面数据或远端代理误当作可维护的 Mock 能力。

## Inputs

- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- 目标前端仓库的 `AGENTS.md`、`package.json`、构建配置、环境文件、请求封装、接口服务、路由、测试设施和 `rules/frontend-engineering.md`。
- 当前需求的 PRD、Dev Guide、UI Handoff、接口文档或已知接口清单（可用时）。
- 已有 Mock、静态原型、演示数据和后端契约；缺失时明确记录为假设或风险。

## Workflow

1. 列出可运行的启动脚本、实际 base URL、代理规则、请求前缀与目标页面；区分本地服务、远端代理和真正的 Mock。
2. 为每个需模拟接口确认请求方法、路径、参数、响应、异常语义、鉴权依赖和文件上传/下载等特殊行为。
3. 选择运行时方案：Vite + React 默认优先评估 MSW；记录未选择默认方案的工程事实与取舍。
4. 明确 Mock 模式名称、独立启动命令、加载位置、生产禁用方式，以及真实 API 与 Mock API 的切换规则。
5. 使用 `template/develop/frontend-mock/mock-plan-template.md` 输出方案；将未知响应结构、脱敏要求和未覆盖接口列为风险或待确认项。

## Decision rules

- 不根据页面截图或猜测虚构接口字段；必要的展示性假数据须标记为假设。
- 不修改真实后端、网关或生产环境来实现 Mock；超出前端服务边界时停止并请求确认。
- 只有能被独立脚本启用、并在生产构建中禁用的方案，才可标记为可实施。

## Output contract

输出前端服务仓库中的 `docs/mock/mock-plan.md`。其中必须包含接口清单、方案选择、启动/禁用方式、数据来源、场景范围、风险和验收命令；状态使用真实的 `draft|ready|blocked`。
