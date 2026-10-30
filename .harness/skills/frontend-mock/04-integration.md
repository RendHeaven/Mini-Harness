---
name: integrate-frontend-mock
description: 将 Mock Runtime 与真实请求路径安全集成，确保 Mock、真实联调和生产构建之间可显式切换。
---

# 前端 Mock 集成与隔离

## Objective

接入 Mock 拦截器和数据源，并验证各模式的请求路径、加载边界和失败行为，防止 Mock 泄漏到真实环境或静默回落到远端接口。

## Inputs

- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- Mock 方案、Runtime 入口、处理器、请求封装、环境配置和目标页面。
- 已知真实 API 前缀、代理规则和认证/权限处理。

## Workflow

1. 在应用启动阶段按 Mock 模式加载 Runtime，并等待其就绪后再挂载依赖接口的页面。
2. 确认 Mock 与真实模式使用同一请求路径；检查相对/绝对 base URL、代理、微前端宿主域名和跨域行为。
3. 对漏拦截请求设定明确策略：本地开发默认告警或失败，不得静默请求远端服务；例外必须在计划中逐项说明。
4. 验证接口错误、超时、权限失败和上传/下载等特殊请求仍能触发页面既有处理逻辑。
5. 记录 Mock 与真实模式的切换方式、已知例外和回归范围。

## Decision rules

- Mock 模式不得绕过页面的鉴权、错误处理或请求转换逻辑；仅替换网络响应来源。
- 不改写生产 base URL 或部署代理来解决本地问题；若需改变共享配置，先取得影响范围确认。
- 真实联调不使用 Mock 成功结果作为证据。

## Output contract

输出已接入的 Mock Runtime、场景选择和模式隔离实现；`docs/mock/mock-verification.md` 必须说明每种模式下的请求去向与未覆盖接口处理方式。
