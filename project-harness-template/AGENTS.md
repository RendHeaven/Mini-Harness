# 项目 Harness 入口

## Atlas 入口

先读取 [.harness/harness.yaml](.harness/harness.yaml)，将 `core.localPath` 相对本项目根解析，再读取该 Core 根目录的 `AGENTS.md` 并执行其中约定。

## 项目结构

| 位置 | 用途 |
| --- | --- |
| `.harness/harness.yaml` | 项目配置、Core 精确 pin 与各类资产路径 |
| `.harness/projectContext/project-context.md` | 项目事实、边界与上下文入口 |
| `.harness/projectContext/services.yaml` | 服务目录及源码仓库定位 |
| `.harness/demandCycle/<周期>/` | 当前需求及阶段交付；实际根目录读取配置 |
| `.harness/history/` | 历史需求与归档；实际根目录读取配置 |
| `原型仓库/` | Schema 20 项目共用原型；实际路径为 project.prototypeRoot |
| `Gate.yaml` | Schema 20 项目的角色确认记录 |
| `.harness/projectContext/jenkins.md`、`testhub.yaml` | 项目工具与测试接入上下文 |
| `.harness/projectContext/frontend-stack.md` | 项目前端组件库、Token 与业务展示约定 |
| `.harness/tools/README.md` | 项目工具的命令、配置与使用限制 |
| `.codex/hooks.json`、`.harness/hooks/` | 项目 Hook 配置与入口 |

本仓库保存项目事实和交付文档；服务源码通过配置指定的服务目录定位。采用模板时按实际配置与目录更新本表，项目专项约束在 projectContext 中维护并加入结构索引。
