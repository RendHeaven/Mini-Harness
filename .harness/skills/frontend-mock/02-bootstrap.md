---
name: bootstrap-frontend-mock
description: 为前端工程增加独立 Mock 启动脚本、运行时入口和生产隔离保护。
---

# 前端 Mock 启动基建

## Objective

在不改变正常开发、真实联调和生产构建行为的前提下，让开发者通过一个明确命令启动 Mock Runtime。

## Inputs

- 文档遵循[时间规范](../../rules/document-timestamps.md)。
- `docs/mock/mock-plan.md`、目标前端服务的依赖锁、构建配置、环境文件和请求封装。
- 目标仓库的分支、工作区状态和安装命令；已有 Mock Runtime 时优先复用。

## Workflow

1. 在计划指定的包管理器中添加必要依赖，并更新锁文件；不得使用全局安装作为运行前提。
2. 增加独立 Mock 脚本（例如 `yarn mock`），显式设置 Mock 模式；不要让默认 `dev` 默默启用 Mock。
3. 建立仅在 Mock 模式动态加载的 Runtime 入口，并配置服务工作线程或等价拦截器资源。
4. 让请求保留生产相同的路径、方法和数据结构；Mock 模式通过拦截响应而非改写页面业务逻辑实现。
5. 验证 Mock 模式启动、普通开发启动和生产构建三者的加载边界；使用 `template/develop/frontend-mock/mock-verification-template.md` 记录结果。

## Decision rules

- 禁止在生产源码中静态导入 Mock Runtime，或用环境变量将 Mock 误带入 `build`、`preview`、UAT/生产。
- 若服务工作线程不适用，替代方案必须仍提供显式脚本、等价隔离和可重复验证。
- 不把远端开发环境代理称为 Mock；它只能作为真实接口模式记录。

## Output contract

输出独立启动脚本、必要环境配置与 Mock Runtime 入口，并在 `docs/mock/mock-verification.md` 记录启动命令、访问地址、实际加载状态和生产隔离检查。
