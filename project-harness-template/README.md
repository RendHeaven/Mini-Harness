# 项目 Harness 模板

本目录是项目脚手架的唯一模板入口，目录结构与新项目落盘结构一致。项目持有需求资产与接入配置；Atlas Core 持有流程、规则、阶段模板、校验器和通用采集器。

```text
project-harness-template/
  AGENTS.md
  .gitignore
  .codex/hooks.json
  .harness/
    harness.yaml
    hooks/usage_hook.py
    hooks/usage_hook.cmd
    projectContext/project-context.md
    projectContext/services.yaml
    projectContext/testhub.yaml
    projectContext/jenkins.md
    projectContext/frontend-stack.md
    history/README.md
    tools/db_tool.py
    tools/.env.example
    tools/README.md
    tools/jenkins-mcp.md
```

## 使用方式

1. 将 `AGENTS.md`、`.gitignore`、`.codex/`、`.harness/`、`Gate.yaml`、`原型仓库/` 复制到新项目 Harness 根目录。已有项目先对比并合并，不能覆盖自己的 AGENTS、hook、忽略规则或项目配置。
2. 填写 `.harness/harness.yaml` 的项目 ID、名称及 Core 精确 pin。`core.localPath` 相对项目根目录，指向真实 Core checkout；version、revision、contentHash 使用同一已确认提交的真实值。
3. 按实际服务填写 `.harness/projectContext/`；示例服务与占位符不是工程事实。`testhub.yaml` 按需填写，不能直接使用占位地址；`frontend-stack.md` 按需声明项目组件库、Token 与业务展示约定，未采用时可删除。
4. 同步填写 Gate.yaml 的 projectId，保留空 cycles；所有角色初始均未确认。原型在项目根持续维护，不创建周期子目录。
5. 按需在 `.harness/demandCycle/<版本>/` 创建需求周期，使用 Core 的阶段模板。
5. 采用新模板的正式项目按 Core 使用说明执行项目校验。本模板自身含占位符，不能当成已经初始化的项目。

## 数据库查询工具

[`.harness/tools`](.harness/tools/README.md) 提供 PostgreSQL 只读查询工具。安装 uv 后用 `uv run .harness/tools/db_tool.py` 启动，由 uv 自动准备 Python 与脚本声明的依赖，无需手动安装 Python、pip 依赖或维护虚拟环境。将 `.env.example` 复制为本机 `.env.local`，分别填写数据库地址、端口、库名、账号与密码。真实配置由 `.gitignore` 排除，并且不参与模板内容哈希；模板中不提供真实账号或默认业务数据库。

## Jenkins MCP

按需填写 [Job 映射](.harness/projectContext/jenkins.md)，按 [本地接入说明](.harness/tools/jenkins-mcp.md) 配置客户端。直接使用远端 MCP 网关，无需额外 Jenkins 脚本运行环境；仍依赖客户端、网络和权限。Atlas 的 delivery skill 负责通用查询与受控构建协议，项目按次记录构建和部署验证结果。采用模板不会自动注册 MCP、提供凭据或触发构建，已有项目只合并所需入口与文档。

## 项目 hook

```text
UserPromptSubmit / Stop
  → .codex/hooks.json
  → .harness/hooks/usage_hook.py（Windows 先经过 usage_hook.cmd）
  → core.localPath/.harness/hooks/usage_hook.py
  → 项目维度的本地队列与采集服务
```

- `.codex/hooks.json` 注册两个事件；实际触发还依赖运行端加载该项目配置。
- 项目 Python 入口固定项目根目录，读取 `kind: project` 与 `core.localPath`，用 `runpy` 加载通用采集器，保留原始 stdin，不复制采集、脱敏或上传实现。
- Python 入口只读取项目 `.harness/harness.yaml`。
- `core.localPath` 支持单行未引号、单引号、JSON 兼容双引号路径及行尾注释；建议 Windows 使用 `/`。加载器不做 YAML 模板展开，不校验 revision/contentHash，正式 pin 校验仍由 Core 校验器负责。
- Windows 默认使用 Codex 工作区 Python，可用 `HARNESS_PYTHON` 指定解释器；`.cmd` 通过自身目录定位 Python 脚本，支持中文、空格路径和任意工作目录。Linux/macOS 使用 `python3`。
- Windows 注册命令使用 `powershell.exe -EncodedCommand`。Codex 可能先通过 PowerShell 或 cmd 执行这条命令；UTF-16LE Base64 编码可避免外层 PowerShell 提前展开 `$projectRoot` 等变量。不要改回带双引号脚本的 `-Command` 包装。
- 编码仅用于传递脚本，不是加密。维护时可用 Python 的 `base64.b64decode(command.split()[-1]).decode('utf-16-le')` 查看脚本，用 `base64.b64encode(script.encode('utf-16-le')).decode()` 生成新值，并同时更新两个事件。脚本仍优先使用 `HARNESS_PROJECT_ROOT`，否则通过 `git rev-parse --show-toplevel` 定位后调用 `.harness/hooks/usage_hook.cmd`。
- 修改 Hook 定义会改变 Codex 信任指纹；采用后须在 Hook 管理界面重新审阅并信任两个事件，再以新的真实消息确认采集。测试覆盖配置命令在 PowerShell/cmd 外壳中的执行和 stdin 传递；仅直接运行 `.cmd` 或 Python 不能证明 Codex 启动链正常。
- 从项目子目录启动时配置会定位项目根目录；从独立服务仓库接入时须由运行端加载这份 hook 配置，并设置 `HARNESS_PROJECT_ROOT` 为对应项目 Harness 根目录。
- Core 缺失、项目配置错误或加载异常时，Python 入口输出不含配置/问答正文的错误类型并跳过采集。Windows 解释器缺失返回 127，便于发现安装问题。

## 采集配置与数据

项目入口默认不上传，只保留本地队列；上传超时默认 3 秒。需要上传时通过环境变量 `HARNESS_TELEMETRY_URL` 指定团队自建的采集服务地址，`HARNESS_TELEMETRY_TIMEOUT_SECONDS` 可覆盖超时；也可在项目入口 `DEFAULT_TELEMETRY_URL` 中固定团队地址。单独运行模板测试不上传。

`HARNESS_TELEMETRY_DIR` 可覆盖队列位置；默认按项目 ID 分目录。采集内容包含项目、Git 用户、脱敏截断的问答、Token 与明确访问的 Atlas 资源，详见 [Collector 说明](../.harness/hooks/README.md)。hook 用于采集，不承担 workflow/Gate 强制执行。

## 模板维护

模板与 Core 一起纳入 `.harness/version.lock`。项目入口回归测试位于 `.harness/hooks/test_project_hook.py`，Core 采集器测试位于 `.harness/hooks/test_usage_hook.py`。本目录 README 是模板维护说明，不必复制为项目 README。
