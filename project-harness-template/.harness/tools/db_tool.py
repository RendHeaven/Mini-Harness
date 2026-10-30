# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "psycopg[binary]>=3.2,<4",
#   "sqlparse>=0.5.3,<0.6",
# ]
# ///

"""通过 uv 管理运行环境，从本地配置读取连接信息的 PostgreSQL 只读查询工具。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().with_name(".env.local")
CONFIG_KEYS = {
    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USERNAME", "DB_PASSWORD",
    "DB_SSLMODE", "DB_CONNECT_TIMEOUT_SECONDS", "DB_STATEMENT_TIMEOUT_MS", "DB_MAX_ROWS",
}
WRITE_WORDS = {
    "INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "CREATE", "ALTER", "DROP",
    "GRANT", "REVOKE", "COPY", "CALL", "DO", "VACUUM", "ANALYZE", "ANALYSE",
    "COMMENT", "LISTEN", "NOTIFY", "UNLISTEN", "SET", "RESET", "INTO", "SET_CONFIG",
}


class ToolError(Exception):
    """可直接显示的错误；不得包含配置值或数据库异常原文。"""


@dataclass(frozen=True, repr=False)
class DatabaseConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str
    connect_timeout: int
    statement_timeout_ms: int
    max_rows: int


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool


def parse_value(raw: str, line_number: int) -> str:
    raw = raw.strip()
    try:
        if raw.startswith('"'):
            value, end = json.JSONDecoder().raw_decode(raw)
            tail = raw[end:].strip()
            if not isinstance(value, str) or (tail and not tail.startswith("#")):
                raise ValueError()
            return value
        if raw.startswith("'"):
            match = re.fullmatch(r"'([^']*)'\s*(?:#.*)?", raw)
            if not match:
                raise ValueError()
            return match.group(1)
        return re.split(r"\s+#", raw, maxsplit=1)[0].strip()
    except ValueError:
        raise ToolError(f"本地配置第 {line_number} 行的引号或格式无效。") from None


def positive_int(value: str, key: str, maximum: int) -> int:
    try:
        number = int(value)
        if not 1 <= number <= maximum:
            raise ValueError()
        return number
    except ValueError:
        raise ToolError(f"{key} 必须是 1～{maximum} 的整数。") from None


def load_config(path: Path) -> DatabaseConfig:
    try:
        content = path.expanduser().read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise ToolError("无法读取本地配置；请复制 .env.example 为 .env.local 并填写，或指定 --config。") from None
    values: dict[str, str] = {}
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, raw = line.partition("=")
        key = key.strip()
        if not separator or key not in CONFIG_KEYS or key in values:
            raise ToolError(f"本地配置第 {number} 行存在未知、重复或无效配置项。")
        values[key] = parse_value(raw, number)
    required = ("DB_HOST", "DB_NAME", "DB_USERNAME", "DB_PASSWORD")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ToolError("本地配置未填写：" + "、".join(missing))
    if any("\x00" in value or "\n" in value or "\r" in value for value in values.values()):
        raise ToolError("本地配置值不能包含换行或 NUL 字符。")
    sslmode = values.get("DB_SSLMODE", "prefer")
    if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ToolError("DB_SSLMODE 无效。")
    return DatabaseConfig(
        host=values["DB_HOST"],
        port=positive_int(values.get("DB_PORT", "5432"), "DB_PORT", 65535),
        database=values["DB_NAME"], username=values["DB_USERNAME"], password=values["DB_PASSWORD"],
        sslmode=sslmode,
        connect_timeout=positive_int(values.get("DB_CONNECT_TIMEOUT_SECONDS", "10"), "DB_CONNECT_TIMEOUT_SECONDS", 60),
        statement_timeout_ms=positive_int(values.get("DB_STATEMENT_TIMEOUT_MS", "30000"), "DB_STATEMENT_TIMEOUT_MS", 300000),
        max_rows=positive_int(values.get("DB_MAX_ROWS", "500"), "DB_MAX_ROWS", 10000),
    )


def validate_read_only_sql(sql: str) -> str:
    try:
        import sqlparse
        from sqlparse import tokens
    except ImportError:
        raise ToolError("缺少 sqlparse，请使用 uv run harness/tools/db_tool.py 启动，由 uv 自动准备依赖。") from None
    try:
        statements = [item for item in sqlparse.parse(sql) if sqlparse.format(str(item), strip_comments=True).strip()]
    except sqlparse.exceptions.SQLParseError:
        raise ToolError("SQL 结构过于复杂或无法解析，请简化查询。") from None
    if len(statements) != 1:
        raise ToolError("只允许一条非空只读 SQL。")
    meaningful = [
        token for token in statements[0].flatten()
        if not token.is_whitespace and token.ttype not in tokens.Comment
    ]
    if not meaningful or meaningful[0].value.upper() not in {"SELECT", "WITH", "SHOW", "EXPLAIN"}:
        raise ToolError("只允许 SELECT/WITH/SHOW/EXPLAIN 查询。")
    for token in meaningful:
        if token.ttype in tokens.Literal or token.ttype in tokens.Comment:
            continue
        if set(token.value.upper().split()) & WRITE_WORDS:
            raise ToolError("SQL 包含写入、修改会话或执行分析的操作。")
        if token.ttype in tokens.Error:
            raise ToolError("SQL 引号或词法结构无效。")
    return str(statements[0]).strip()


def run_query(config: DatabaseConfig, sql: str, params=None) -> QueryResult:
    sql = validate_read_only_sql(sql)
    try:
        import psycopg
    except ImportError:
        raise ToolError("缺少 psycopg，请使用 uv run harness/tools/db_tool.py 启动，由 uv 自动准备依赖。") from None
    try:
        with psycopg.connect(
            host=config.host, port=config.port, dbname=config.database,
            user=config.username, password=config.password, sslmode=config.sslmode,
            connect_timeout=config.connect_timeout, application_name="project_harness_readonly_query",
            autocommit=False,
        ) as connection:
            connection.read_only = True
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_catalog.set_config('statement_timeout', %s, true)", (str(config.statement_timeout_ms),))
                    cursor.execute(sql, params)
                    columns = [column.name for column in cursor.description or ()]
                    if len(set(columns)) != len(columns):
                        raise ToolError("结果存在重复列名，请使用 AS 指定唯一列名。")
                    rows = cursor.fetchmany(config.max_rows + 1)
                    return QueryResult(
                        columns, [dict(zip(columns, row)) for row in rows[:config.max_rows]],
                        len(rows) > config.max_rows,
                    )
            finally:
                connection.rollback()
    except psycopg.Error as error:
        state = error.sqlstate if re.fullmatch(r"[A-Z0-9]{5}", error.sqlstate or "") else "unknown"
        raise ToolError(f"数据库连接或查询失败（SQLSTATE: {state}）；请在本机核对连接配置与 SQL。") from None


def print_result(result: QueryResult, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result.rows, ensure_ascii=False, default=str, indent=2))
    elif output_format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=result.columns)
        writer.writeheader()
        writer.writerows(result.rows)
    else:
        values = [["" if row[name] is None else str(row[name]) for name in result.columns] for row in result.rows]
        widths = [min(max([len(name), *[len(row[index]) for row in values]]), 80) for index, name in enumerate(result.columns)]
        for row in [result.columns, *values]:
            print(" | ".join(value[:width].ljust(width) for value, width in zip(row, widths)))
        print(f"({len(result.rows)} rows)")
    if result.truncated:
        print("结果已截断到 DB_MAX_ROWS；请缩小查询范围或调整本地配置。", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从本地配置连接 PostgreSQL 并执行只读查询。")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="本地配置路径，默认脚本同目录 .env.local。")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="使用 SELECT 1 检查连接。")
    query = commands.add_parser("query", help="执行只读查询。")
    sources = query.add_mutually_exclusive_group()
    sources.add_argument("--sql")
    sources.add_argument("--file", type=Path)
    query.add_argument("--params", help="JSON 数组或对象，作为驱动绑定参数。")
    query.add_argument("--format", choices=("table", "json", "csv"), default="table")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        params = None
        if args.command == "check":
            sql = "SELECT 1 AS connection_ok"
        else:
            if args.sql is not None:
                sql = args.sql
            elif args.file:
                sql = args.file.read_text(encoding="utf-8-sig")
            elif not sys.stdin.isatty():
                sql = sys.stdin.read()
            else:
                raise ToolError("请通过 --sql、--file 或 stdin 提供 SQL。")
            if args.params is not None:
                try:
                    params = json.loads(args.params)
                except ValueError:
                    raise ToolError("--params 必须是 JSON 数组或对象。") from None
                if not isinstance(params, (list, dict)):
                    raise ToolError("--params 必须是 JSON 数组或对象。")
        result = run_query(load_config(args.config), sql, params)
        print_result(result, "table" if args.command == "check" else args.format)
        return 0
    except ToolError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("无法读取输入文件或文本编码无效。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
