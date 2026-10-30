# Jenkins MCP 本地接入

本能力直接使用客户端连接的远端 Streamable HTTP MCP 网关，不新增 Python/Node 查询脚本，不依赖本机 Java、Jenkins CLI 或 Jenkins SDK。仍需要支持该协议的客户端、可达网关的网络、有效 MCP Token 和服务端权限；并非完全不依赖运行环境。

Atlas 提供通用 skill，项目填写 [服务与 Job 映射](../projectContext/jenkins.md)。项目 hook 继续用于采集，不代理 Jenkins 请求、不自动触发部署，也不充当权限控制。网关持有 Jenkins API Token，普通用户只使用管理员分配的 MCP Token。

## Codex 配置

运维手册的 `mcpServers` JSON 适用于采用该格式的客户端；Codex 原生配置为 TOML。以下为手工合并至用户 `~/.codex/config.toml` 的示例，**占位域名不可直接使用**，本模板不会创建或修改实际配置：

```toml
[mcp_servers.jenkins]
url = "https://jenkins-mcp.example.invalid/mcp"
bearer_token_env_var = "JENKINS_MCP_TOKEN"
```

将 URL 换为管理员确认的地址（须包含 `http://` 或 `https://`，正式地址优先 HTTPS）。由本机凭据管理方式向启动 Codex 的进程提供 `JENKINS_MCP_TOKEN`；不把值写入 TOML、项目 `.env.example`、Git、命令参数或聊天。不要复用数据库 `.env.local`。在已运行工具 shell 中设置环境变量，不会自动更新桌面客户端父进程；配置/环境变化后重载或重新启动相应客户端，再新建会话验证。

也可手动使用 CLI 注册（先替换占位 URL，已有同名配置先检查并保留其他设置）：

```powershell
codex mcp add jenkins --url "https://jenkins-mcp.example.invalid/mcp" --bearer-token-env-var JENKINS_MCP_TOKEN
```

Codex 也支持受信任项目的 `.codex/config.toml`；本模板默认采用用户本地配置，不随项目分发真实地址或凭据。配置依据：[Codex 官方 MCP 文档](https://developers.openai.com/codex/mcp)。命令格式经本机 `codex mcp add --help` 核对。

## 首次验证与工具边界

1. 确认可用工具后调用 `whoami`，核对管理员分配的服务身份。
2. 调用 `list_jobs`，按需 `list_folder_jobs` 查询目标目录；完整 Job 路径保留原始中文和大小写。
3. 使用 `get_job_info` 核对任务及参数，再用 `get_build_status`、`get_build_log` 读取明确构建编号的结果。
4. `trigger_build` 是写操作，只在目标、参数及授权齐全后执行；首次连接验证不需要触发构建。

| 工具 | 用途 | 手册中的参数线索 |
| --- | --- | --- |
| `whoami` | 服务身份 | 无 |
| `list_jobs` | 顶层任务/目录 | 无 |
| `list_folder_jobs` | 目录内容 | folder |
| `get_job_info` | 任务与构建信息 | job |
| `get_build_status` | 构建状态 | job、build（或工具支持的 lastBuild） |
| `get_build_log` | 控制台日志 | job、build、max_chars |
| `trigger_build` | 触发构建 | job、可选 parameters |

以上来源为运维《Jenkins MCP 使用说明》V1.0（2026-08-03），环境基线 Jenkins 2.504.1。参数类型、必填项、返回字段以运行时工具 Schema 为准。手册没有列出 queue 查询工具，不能假设能通过它追踪触发回执；完整执行规则读取项目锁定 Core 的 Jenkins skill。

## 常见问题

| 提示 | 处理 |
| --- | --- |
| Invalid URL | 补齐协议头，保存后让客户端重新加载实际配置 |
| 401 Unauthorized | 核查 MCP Token 是否有效及客户端进程是否获得环境变量；由管理员轮换，不索取 Jenkins API Token |
| Job is not in ALLOWED_JOBS | 提供准确 Job/Folder 路径给管理员申请权限 |
| Jenkins API 403 | 管理员检查 Overall/Read、Job/Read、Job/Build 等实际权限 |
| Build triggering is disabled | `ENABLE_BUILD=false` 等服务端限制；按流程申请开放 |
| 超时 | 检查客户端网络与管理员提供的 `/healthz`，再联系平台负责人；trigger 超时不能据此直接重发 |

仅看到顶层 Folder 不保证可以读取内容。模板文档不证明现场已连接、已授权或已完成部署；构建记录必须绑定本次编号，访问地址必须有实际证据。
