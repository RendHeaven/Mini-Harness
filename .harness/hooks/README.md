# Mini-Harness 交互采集

通用 Collector 将一次 Codex 提问保存为一条交互快照：

```text
UserPromptSubmit
  -> 项目与 Git 用户
  -> 输入脱敏/500 字截断
  -> transcript 累计 Token 基线
  -> SQLite revision 1
  -> 云端上传

Stop
  -> 输出脱敏/500 字截断
  -> Token 基线差值与缓存命中率
  -> 本轮明确访问的 Atlas 资源
  -> SQLite revision 2
  -> 云端条件 upsert
```

Collector 不保存模型、权限模式、匿名 actor、指纹、原始 payload 或完整问答。
任何解析或网络失败都不会阻断 Codex。

## 采集字段

- `harness.yaml` 中的项目 ID 和名称；
- 当前仓库有效的 Git `user.name`、`user.email`（local 优先于 global）；
- 输入与输出正文，先脱敏，最多 500 个 Unicode 字符；
- 明确触发的 `workflow`、`skills`、`template`、`rules` 相对路径；
- 本轮 input/output/reasoning/total Token；
- cached input Token 和 `cached / input` 命中率。

只分析本轮 transcript 中的工具输入。目录扫描、工具输出偶然包含的文件名、
不存在的路径以及 Mini-Harness 之外的文件都不会计入资源。

transcript 不可读、格式变化或 Token 计数回退时，项目、Git、输入和输出仍会
保存；资源数组为空，Token/缓存字段为 `null`。诊断日志不含问答正文。

## 本地 Outbox

默认路径：

- Windows：`%LOCALAPPDATA%/HarnessProjects/<project-id>/telemetry/spool.db`
- Linux/macOS：`$XDG_STATE_HOME/harness-projects/<project-id>/telemetry/spool.db`
- 未设置 XDG：`~/.local/state/harness-projects/<project-id>/telemetry/spool.db`

Collector 只连接 Schema 2 的当前表结构。不存在的数据库或没有任何表、索引、视图且版本为 0 的空库可首次初始化；既有数据库先在临时独立副本中检查，副本包含实际 WAL；检查期间源文件变化则停止本次采集。其他版本或结构不符时拒绝打开原数据库，不创建或修改其 WAL/SHM 文件，不执行自动升级。诊断记录 `outbox_open_failed`，采集暂停但不阻断 Codex。使用新的空队列目录可开始采集，既有数据库由其所有者单独管理。

环境变量：

| 变量 | 说明 |
| --- | --- |
| `HARNESS_PROJECT_ROOT` | 项目 Harness 根目录，由项目入口设置 |
| `HARNESS_TELEMETRY_DIR` | 覆盖本地 Outbox 目录 |
| `HARNESS_TELEMETRY_URL` | 自建采集服务根地址或 `/api/v1/interactions/batch` 完整地址；未设置或为空时不上传，只保留本地队列 |
| `HARNESS_TELEMETRY_TIMEOUT_SECONDS` | 上传超时，默认 1 秒，范围 0.1～3 秒 |
| `HARNESS_TELEMETRY_BATCH_SIZE` | 上传批量，默认 20，范围 1～100 |

当前受控内网接口不发送 Token。

## 项目接入

项目 `.codex/hooks.json` 注册 `UserPromptSubmit` 和 `Stop`，项目
`.harness/hooks/usage_hook.py` 根据 `core.localPath` 加载本 Collector。
Windows 通过 `usage_hook.cmd` 使用 Codex 工作区 Python 运行时。

可复制的项目配置、入口与 Windows 启动脚本统一维护在
[`project-harness-template`](../../project-harness-template/README.md)。项目入口不复制 Collector；
`core.localPath` 相对项目根目录解析。入口本身不校验 revision/contentHash，精确 pin 由项目升级和正式 Gate 校验。

查询本地快照：

```powershell
$database = Join-Path $env:LOCALAPPDATA `
  "HarnessProjects/filesystem/telemetry/spool.db"

@'
import sqlite3, sys
connection = sqlite3.connect(sys.argv[1])
for row in connection.execute("""
    SELECT interaction_id, revision, project_id,
           input_text, output_text, input_tokens, cache_hit_rate
    FROM interactions
"""):
    print(row)
'@ | & "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" - $database
```

## 测试

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  -X utf8 .harness/hooks/test_usage_hook.py -v
```
