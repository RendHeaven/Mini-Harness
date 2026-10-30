# 项目数据库查询工具

`db_tool.py` 参考 FileSystem-Harness 历史 `.harness/tools/pg_query.py` 的 PostgreSQL 查询方式，支持 SQL 文本、文件或标准输入、绑定参数、表格/JSON/CSV 输出、查询超时和返回行数上限。数据库连接信息独立存放在本机配置中。

采用与数据工作台相同的 uv / PEP 723 单文件运行方式：脚本顶部声明 Python `>=3.10`、Psycopg 与 sqlparse 依赖，uv 自动选择或下载 Python 并准备隔离依赖环境，无需预先安装 Python、pip 包或手动创建 venv。

## 准备 uv

本机需要可用的 `uv`，安装方式见 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/)。安装后运行 `uv --version` 验证。已有 uv 时无需重复安装。

首次运行或缓存不齐时需要访问 Python 下载源与包索引；缓存完整后可加 `--offline`，例如 `uv run --offline .harness/tools/db_tool.py --help`。仍需本地数据库配置与数据库网络访问。uv 使用自己的缓存，不向项目创建依赖目录；脚本声明了内联依赖，不使用项目其他 Python 依赖。需要明确隔离系统 Python 时可加 `--managed-python`。

## 初始化本地配置

在项目 Harness 根目录执行：

```powershell
Copy-Item .harness/tools/.env.example .harness/tools/.env.local
# 只准备运行环境并查看帮助，不读取数据库配置或连接数据库
uv run .harness/tools/db_tool.py --help
```

仅首次复制，已有 `.env.local` 时直接编辑，避免覆盖。Linux/macOS 可使用 `cp -n` 完成首次复制。

在本机编辑 `.env.local`：

| 配置项 | 用途 |
| --- | --- |
| `DB_HOST` | 数据库主机地址，必填 |
| `DB_PORT` | 端口，默认 5432 |
| `DB_NAME` | 库名，必填 |
| `DB_USERNAME` | 账号，必填，使用数据库只读账号 |
| `DB_PASSWORD` | 密码，必填 |
| `DB_SSLMODE` | TLS 模式，默认 prefer；支持 PostgreSQL 标准六种模式 |
| `DB_CONNECT_TIMEOUT_SECONDS` | 连接超时，默认 10 秒，最大 60 秒 |
| `DB_STATEMENT_TIMEOUT_MS` | 语句超时，默认 30000 毫秒，最大 300000 毫秒 |
| `DB_MAX_ROWS` | 输出行数上限，默认 500，最大 10000 |

连接信息只从该本地文件读取，不读取 `PGHOST`、`DB_PASSWORD` 等环境变量来替换配置，也不提供账号、密码或数据库地址命令行参数。不要将账号密码拼进 URL。不同环境使用不同本地文件并通过 `--config` 明确选择；额外本地配置应保存在仓库外或自行加入忽略规则。

配置支持 `KEY=value`、单引号和 JSON 兼容双引号；空格后 `#` 表示行尾注释。密码包含空格或 `#` 时使用引号，不进行 `$VAR` 展开或命令执行。未知项、重复项、格式错误及必填项为空时直接报错，不回显配置值。

`.env.example` 可入库，`.env.local` 已在项目模板 `.gitignore` 中排除。不要把真实配置复制回模板、项目上下文、执行日志或版本库；本工具也不会创建或覆盖本地配置。

## 查询

```powershell
# 检查连接，只执行 SELECT 1
uv run .harness/tools/db_tool.py check

# 查询与格式
uv run .harness/tools/db_tool.py query --sql "SELECT current_date AS today" --format json
uv run .harness/tools/db_tool.py query --file query.sql --format csv

# 绑定参数（%s 由驱动处理，不进行字符串拼接）
uv run .harness/tools/db_tool.py query --sql 'SELECT %s::int AS value' --params '[42]'

# 指定其他本地配置，--config 放在子命令前
uv run .harness/tools/db_tool.py --config C:/local-config/project-db.env check

# 标准输入
'SELECT 1 AS value' | uv run .harness/tools/db_tool.py query
```

默认配置路径相对脚本定位，切换工作目录不会误用其他项目配置。`--file` 和显式 `--config` 相对当前工作目录解析。

只接收单条 SELECT、只读 WITH、SHOW 或 EXPLAIN，拒绝明显写语句、会话修改及 EXPLAIN ANALYZE；普通引号内文本和注释不当作写操作关键词。嵌套块注释等解析器不支持的结构可能被保守拒绝，请简化后再查询。连接使用只读事务，设置语句超时，成功或失败都回滚并关闭连接。SQL 预检查不是完整的权限沙箱，数据库侧只读账户与函数权限仍由数据库管理方控制。

超过行数上限时仅输出上限内数据并在 stderr 提示截断。行数上限限制输出，不限制数据库扫描量或驱动接收缓冲；大表查询仍应加 WHERE/LIMIT。重复列名需用 AS 区分。连接或执行失败只显示 SQLSTATE，不回显包含连接信息、参数或 SQL 的数据库异常原文。

## 运行依赖

使用 `uv run db_tool.py ...` 执行 `check/query` 子命令，依赖以脚本顶部声明为准。本机连接配置保存在被 Git 忽略的 `.env.local`。

Atlas 仓库内运行 `uv run .harness/tools/test_project_db_tool.py` 执行回归；测试脚本声明自己的测试环境，并检查与工具依赖声明一致。回归测试使用连接替身，不读取真实 `.env.local` 或连接项目数据库。

实现依据：[uv 脚本依赖机制](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies)、[Psycopg 连接与事务接口](https://www.psycopg.org/psycopg3/docs/api/connections.html)、[sqlparse 语句分析接口](https://sqlparse.readthedocs.io/en/latest/analyzing.html)。
