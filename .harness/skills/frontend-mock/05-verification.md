---
name: verify-frontend-mock
description: 验证前端 Mock 的启动、数据场景、隔离和维护信息，并输出可复核交接记录。
---

# 前端 Mock 验证与交接

## Objective

证明 Mock 启动方式和数据源可用、可重复且不会影响真实联调或生产构建，同时交接后续维护边界。

## Inputs

- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- Mock 计划、数据源矩阵、启动脚本、环境配置、页面路由和现有测试/构建命令。
- 浏览器、网络面板、自动化测试或等价可复核证据。

## Workflow

1. 从干净依赖状态执行 Mock 启动命令，记录端口、访问地址和 Runtime 已就绪证据。
2. 逐项验证矩阵中的正常、空、错误和关键边界场景；记录请求被拦截而非访问远端服务的证据。
3. 执行项目已有的 lint、测试和生产构建；确认生产构建未打入 Mock Runtime，普通开发与真实联调模式没有启用 Mock。
4. 核查敏感数据、场景选择入口、未覆盖接口和契约更新时间；列出维护负责人或待确认项。
5. 使用 `template/develop/frontend-mock/mock-verification-template.md` 形成验证记录，并将真实接口联调留给 `frontend-workflow.md` 的 API 实现阶段。

## Decision rules

- 无法验证的项目应如实记为 `blocked` 或 `failed`，不得以截图或启动日志代替构建/网络隔离证据。
- Mock 验证通过不等于真实接口联调、生产构建、TestHub 用例同步或实际测试执行结论。
- 发现生产泄漏、敏感数据或静默远端回落时，立即停止将该方案标记为可交接并回流集成阶段。

## Output contract

输出 `docs/mock/mock-verification.md`，至少包含命令、环境、场景结果、网络去向、lint/test/build 结果、生产隔离结论、未覆盖范围和后续维护动作。
