from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib import request as urllib_request


COLLECTOR_VERSION = "1.0.0"
OUTBOX_SCHEMA_VERSION = 2
TEXT_MAX_CHARS = 500
DEFAULT_UPLOAD_BATCH_SIZE = 20
DEFAULT_UPLOAD_TIMEOUT_SECONDS = 1.0
INTERACTION_NAMESPACE = uuid.UUID("d6beb4b8-28a8-4e40-a589-a387dd9dc8aa")
RESOURCE_CATEGORIES = ("workflow", "skills", "template", "rules")

REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?i)([A-Za-z][A-Za-z0-9+.-]*://[^:/@\s]+:)"
            r"([^@\s]+)(@)"
        ),
        r"\1[REDACTED]\3",
    ),
    (
        re.compile(
            r"(?i)(--(?:api[_-]?key|access[_-]?token|token|password|secret)"
            r"\s+)([^\s]+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"""(?ix)
            (
              ["']?(?:api[_-]?key|access[_-]?token|token|password|secret)
              ["']?\s*[:=]\s*["']?
            )
            ([^"'\s,;}]{4,})
            """
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        "Bearer [REDACTED]",
    ),
    (
        re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_OPENAI_KEY]",
    ),
    (
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}\b"),
        "[REDACTED_GITHUB_TOKEN]",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|token|password|secret)"
            r"(\s*[:=]\s*)([^\s,;]{4,})"
        ),
        r"\1\2[REDACTED]",
    ),
)
RESOURCE_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9_.-])\.harness[\\/](workflow|skills|template|rules)"
    r"[\\/]([A-Za-z0-9._/\\-]+)"
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def redact_and_truncate(value: Any) -> tuple[str, bool]:
    text = normalize_text(value)
    for pattern, replacement in REDACTION_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:TEXT_MAX_CHARS], len(text) > TEXT_MAX_CHARS


def normalize_yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            parsed, end = json.JSONDecoder().raw_decode(value)
            tail = value[end:].strip()
            if isinstance(parsed, str) and (not tail or tail.startswith("#")):
                return parsed
        except ValueError:
            pass
    if value.startswith("'"):
        quoted = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if quoted:
            return quoted.group(1).replace("''", "'")
    return re.split(r"\s+#", value, maxsplit=1)[0].strip()


def parse_harness_yaml(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    values: dict[str, str] = {}
    section: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        top = re.match(
            r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$",
            raw_line,
        )
        if top:
            key, raw_value = top.groups()
            section = key if not raw_value else None
            if raw_value:
                values[key] = normalize_yaml_scalar(raw_value)
            continue
        nested = re.match(
            r"^\s+([A-Za-z][A-Za-z0-9_-]*):\s*(.*?)\s*$",
            raw_line,
        )
        if section and nested:
            key, raw_value = nested.groups()
            values[f"{section}.{key}"] = normalize_yaml_scalar(raw_value)
    return values


def project_config_path(root: Path) -> Path:
    return root / ".harness" / "harness.yaml"


def find_project_root(cwd: Any) -> Path | None:
    configured = os.environ.get("HARNESS_PROJECT_ROOT", "").strip()
    try:
        start = Path(configured or normalize_text(cwd) or os.getcwd()).resolve()
    except (OSError, RuntimeError):
        return None
    if start.is_file():
        start = start.parent
    candidates = (start,) if configured else (start, *start.parents)
    for candidate in candidates:
        config = project_config_path(candidate)
        if not config.is_file():
            continue
        try:
            values = parse_harness_yaml(config)
        except (OSError, UnicodeError):
            continue
        if (
            values.get("kind") == "project"
            and values.get("project.id")
            and values.get("project.name")
        ):
            return candidate
    return None


def project_metadata(root: Path) -> dict[str, str] | None:
    try:
        values = parse_harness_yaml(project_config_path(root))
    except (OSError, UnicodeError):
        return None
    if values.get("kind") != "project":
        return None
    project_id = values.get("project.id", "").strip()
    project_name = values.get("project.name", "").strip()
    if not project_id or not project_name:
        return None
    return {"id": project_id, "name": project_name}


def atlas_root(root: Path) -> Path | None:
    try:
        values = parse_harness_yaml(project_config_path(root))
        local_path = values.get("core.localPath", "").strip()
        return (root / local_path).resolve() if local_path else None
    except (OSError, RuntimeError, UnicodeError):
        return None


def default_telemetry_dir(project_id: str) -> Path:
    configured = os.environ.get("HARNESS_TELEMETRY_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    project_key = re.sub(r"[^A-Za-z0-9._-]+", "-", project_id)
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        return (
            Path(local_app_data)
            / "HarnessProjects"
            / project_key
            / "telemetry"
        )
    state_home = os.environ.get("XDG_STATE_HOME", "").strip()
    if state_home:
        return Path(state_home) / "harness-projects" / project_key / "telemetry"
    return (
        Path.home()
        / ".local"
        / "state"
        / "harness-projects"
        / project_key
        / "telemetry"
    )


def git_config(root: Path, key: str) -> str | None:
    for scope in ("--local", "--global"):
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "config", scope, "--get", key],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode == 0:
            value = result.stdout.decode("utf-8", errors="replace").strip()
            if value:
                return value[:256] if key == "user.name" else value[:320]
    return None


def git_user(root: Path) -> dict[str, str | None]:
    return {
        "name": git_config(root, "user.name"),
        "email": git_config(root, "user.email"),
    }


def interaction_id(project_id: str, session_id: str, turn_id: str) -> str:
    return str(
        uuid.uuid5(
            INTERACTION_NAMESPACE,
            f"{project_id}\0{session_id}\0{turn_id}",
        )
    )


OUTBOX_TABLE_SQL = """
CREATE TABLE interactions (
                interaction_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                turn_id TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision BETWEEN 1 AND 2),
                project_id TEXT NOT NULL,
                project_name TEXT NOT NULL,
                git_user_name TEXT,
                git_user_email TEXT,
                input_text TEXT NOT NULL,
                input_truncated INTEGER NOT NULL,
                output_text TEXT,
                output_truncated INTEGER NOT NULL DEFAULT 0,
                workflows_json TEXT NOT NULL DEFAULT '[]',
                skills_json TEXT NOT NULL DEFAULT '[]',
                templates_json TEXT NOT NULL DEFAULT '[]',
                rules_json TEXT NOT NULL DEFAULT '[]',
                baseline_json TEXT,
                transcript_path TEXT,
                transcript_offset INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_tokens INTEGER,
                total_tokens INTEGER,
                cached_input_tokens INTEGER,
                cache_hit_rate REAL,
                upload_revision INTEGER NOT NULL DEFAULT 0,
                upload_attempts INTEGER NOT NULL DEFAULT 0,
                last_upload_error TEXT,
                next_attempt_at TEXT,
                dead_letter_revision INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (project_id, session_id, turn_id)
            )
"""
OUTBOX_INDEX_SQL = """
CREATE INDEX idx_interactions_upload_ready_v2
            ON interactions (
                upload_revision,
                revision,
                dead_letter_revision,
                next_attempt_at,
                updated_at
            )
"""


def _outbox_state(connection: sqlite3.Connection) -> bool:
    """Validate the current schema without changing the database; return empty."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    objects = list(connection.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY name"
    ))
    if version == 0 and not objects:
        return True
    if version != OUTBOX_SCHEMA_VERSION:
        raise RuntimeError("unsupported_outbox_schema")
    expected = {
        ("table", "interactions"): OUTBOX_TABLE_SQL,
        ("index", "idx_interactions_upload_ready_v2"): OUTBOX_INDEX_SQL,
    }
    actual = {(row[0], row[1]): row[2] for row in objects if row[2] is not None}
    normalize = lambda sql: re.sub(r"\s+", " ", sql.strip()).casefold()
    if set(actual) != set(expected) or any(
        normalize(actual[key]) != normalize(value) for key, value in expected.items()
    ):
        raise RuntimeError("unsupported_outbox_schema")
    return False


def _outbox_files(database_path: Path) -> dict[Path, tuple[int, int, int]]:
    files = {}
    for suffix in ("", "-wal", "-journal"):
        path = database_path.with_name(database_path.name + suffix)
        try:
            state = path.stat()
        except FileNotFoundError:
            continue
        files[path] = (state.st_ino, state.st_size, state.st_mtime_ns)
    return files


def _inspect_outbox(database_path: Path) -> None:
    # A read-only SQLite connection can still create or update a WAL index.
    # Inspect independent files so refusal cannot change the original directory.
    before = _outbox_files(database_path)
    with tempfile.TemporaryDirectory(prefix="atlas-outbox-inspection-") as directory:
        copied = Path(directory) / database_path.name
        for source in before:
            shutil.copyfile(source, copied.with_name(source.name))
        if before != _outbox_files(database_path):
            raise RuntimeError("outbox_changed_during_inspection")
        inspection = sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True)
        try:
            empty = _outbox_state(inspection)
            # A nonempty WAL with no visible schema may be incomplete; it is not
            # evidence that the source is a new empty database.
            if empty and any(path.suffix == ".db-wal" and state[1] for path, state in before.items()):
                raise RuntimeError("unsupported_outbox_schema")
        finally:
            inspection.close()
        if before != _outbox_files(database_path):
            raise RuntimeError("outbox_changed_during_inspection")


def connect_database(telemetry_dir: Path) -> sqlite3.Connection:
    database_path = telemetry_dir / "spool.db"
    if database_path.exists():
        _inspect_outbox(database_path)
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=3.0)
    connection.row_factory = sqlite3.Row
    try:
        # Recheck under the writer lock to handle another collector initializing it.
        connection.execute("BEGIN IMMEDIATE")
        empty = _outbox_state(connection)
        if empty:
            connection.execute(OUTBOX_TABLE_SQL)
            connection.execute(OUTBOX_INDEX_SQL)
            connection.execute(f"PRAGMA user_version={OUTBOX_SCHEMA_VERSION}")
        connection.commit()
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=3000")
        return connection
    except Exception:
        connection.rollback()
        connection.close()
        raise


def transcript_position(path_value: Any) -> tuple[str | None, int | None]:
    path_text = normalize_text(path_value).strip()
    if not path_text:
        return None, None
    try:
        path = Path(path_text).expanduser()
        return str(path), path.stat().st_size
    except OSError:
        return path_text, None


def _find_token_usage(value: Any) -> dict[str, int] | None:
    if isinstance(value, dict):
        for key in ("total_token_usage", "total_usage"):
            candidate = value.get(key)
            normalized = _normalize_token_usage(candidate)
            if normalized is not None:
                return normalized
        for nested in value.values():
            found = _find_token_usage(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_token_usage(nested)
            if found is not None:
                return found
    return None


def _normalize_token_usage(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    aliases = {
        "input": ("input_tokens", "input"),
        "cached": ("cached_input_tokens", "cached_tokens"),
        "output": ("output_tokens", "output"),
        "reasoning": ("reasoning_output_tokens", "reasoning_tokens"),
        "total": ("total_tokens", "total"),
    }
    result: dict[str, int] = {}
    for target, keys in aliases.items():
        raw = next((value[key] for key in keys if key in value), None)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None
        number = int(raw)
        if number < 0:
            return None
        result[target] = number
    return result


def latest_token_usage(path_value: Any) -> dict[str, int] | None:
    path_text = normalize_text(path_value).strip()
    if not path_text:
        return None
    try:
        with Path(path_text).open("rb") as transcript:
            transcript.seek(0, os.SEEK_END)
            position = transcript.tell()
            partial = b""
            while position > 0:
                size = min(65_536, position)
                position -= size
                transcript.seek(position)
                lines = (transcript.read(size) + partial).splitlines()
                if position > 0 and lines:
                    partial = lines.pop(0)
                else:
                    partial = b""
                for raw_line in reversed(lines):
                    try:
                        record = json.loads(raw_line.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeError):
                        continue
                    found = _find_token_usage(record)
                    if found is not None:
                        return found
    except OSError:
        return None
    return None


def _tool_input_values(record: dict[str, Any]) -> Iterable[Any]:
    payload = record.get("payload")
    candidates = [record]
    if isinstance(payload, dict):
        candidates.append(payload)
    for candidate in candidates:
        type_name = normalize_text(candidate.get("type")).lower()
        if "output" in type_name or "result" in type_name:
            continue
        if (
            "call" not in type_name
            and type_name not in {"tool_use", "tool"}
        ):
            continue
        for key in (
            "arguments",
            "input",
            "command",
            "path",
            "file",
            "file_path",
        ):
            if key in candidate:
                yield candidate[key]


def _all_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _all_strings(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _all_strings(nested)


def _decode_tool_input(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _tool_input_has_core_context(value: Any, core_root: Path) -> bool:
    core_text = str(core_root).replace("\\", "/").rstrip("/").lower()
    for text in _all_strings(value):
        normalized = text.replace("\\\\", "\\").replace("\\", "/").lower()
        if core_text in normalized:
            return True
    return False


def _resource_paths(
    tool_input: Any,
    core_root: Path,
) -> Iterable[tuple[str, str]]:
    decoded_input = _decode_tool_input(tool_input)
    core_text = str(core_root).replace("\\", "/").rstrip("/").lower()
    has_core_context = _tool_input_has_core_context(decoded_input, core_root)
    for text in _all_strings(decoded_input):
        normalized = text.replace("\\\\", "\\").replace("\\", "/")
        for match in RESOURCE_PATTERN.finditer(normalized):
            marker_start = match.start()
            prefix = normalized[:marker_start]
            lower_prefix = prefix.lower()
            core_position = lower_prefix.rfind(core_text)
            direct_core_path = False
            if core_position >= 0:
                between = prefix[core_position + len(core_text):]
                direct_core_path = not between.strip(" /'\"")
            relative_path = (
                marker_start == 0
                or normalized[marker_start - 1].isspace()
                or normalized[marker_start - 1] in "'\"=([{"
            )
            if not direct_core_path and not (
                relative_path and has_core_context
            ):
                continue
            category = match.group(1).lower()
            suffix = match.group(2).replace("\\", "/")
            suffix = suffix.rstrip(".,:;)]}")
            if not suffix or ".." in Path(suffix).parts:
                continue
            try:
                candidate = (
                    project_config_path(core_root).parent / category / Path(suffix)
                ).resolve()
                base = (project_config_path(core_root).parent / category).resolve()
                candidate.relative_to(base)
            except (OSError, RuntimeError, ValueError):
                continue
            if candidate.is_file():
                yield category, f"{category}/{candidate.relative_to(base).as_posix()}"


def parse_transcript_segment(
    path_value: Any,
    offset: int | None,
    core_root: Path | None,
    turn_id: str | None = None,
) -> tuple[dict[str, list[str]], dict[str, int] | None, bool]:
    empty = {category: [] for category in RESOURCE_CATEGORIES}
    path_text = normalize_text(path_value).strip()
    if not path_text or offset is None or core_root is None:
        return empty, None, False
    latest: dict[str, int] | None = None
    parsed_records = 0
    seen = {category: set() for category in RESOURCE_CATEGORIES}
    try:
        with Path(path_text).open("r", encoding="utf-8") as transcript:
            transcript.seek(offset)
            for line in transcript:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeError):
                    continue
                if not isinstance(record, dict):
                    continue
                parsed_records += 1
                found = _find_token_usage(record)
                if found is not None:
                    latest = found
                record_turn_id = _record_turn_id(record)
                if (
                    turn_id
                    and record_turn_id
                    and record_turn_id != turn_id
                ):
                    continue
                for tool_input in _tool_input_values(record):
                    for category, relative_path in _resource_paths(
                        tool_input,
                        core_root,
                    ):
                        if relative_path not in seen[category]:
                            if (
                                len(relative_path) > 512
                                or len(empty[category]) >= 100
                            ):
                                continue
                            seen[category].add(relative_path)
                            empty[category].append(relative_path)
    except (OSError, ValueError):
        return {category: [] for category in RESOURCE_CATEGORIES}, None, False
    return empty, latest, parsed_records > 0


def token_delta(
    baseline: dict[str, int] | None,
    current: dict[str, int] | None,
) -> tuple[dict[str, int] | None, dict[str, int | float] | None]:
    if baseline is None or current is None:
        return None, None
    delta = {key: current[key] - baseline[key] for key in baseline}
    if any(value < 0 for value in delta.values()):
        return None, None
    if delta["cached"] > delta["input"] or delta["reasoning"] > delta["output"]:
        return None, None
    tokens = {
        "input_tokens": delta["input"],
        "output_tokens": delta["output"],
        "reasoning_tokens": delta["reasoning"],
        "total_tokens": delta["total"],
    }
    cache = {
        "cached_input_tokens": delta["cached"],
        "hit_rate": (
            delta["cached"] / delta["input"] if delta["input"] > 0 else 0.0
        ),
    }
    return tokens, cache


def _record_turn_id(record: dict[str, Any]) -> str | None:
    payload = record.get("payload")
    for candidate in (payload, record):
        if not isinstance(candidate, dict):
            continue
        metadata = candidate.get("internal_chat_message_metadata_passthrough")
        if isinstance(metadata, dict):
            turn_id = normalize_text(metadata.get("turn_id")).strip()
            if turn_id:
                return turn_id
    return None


def telemetry_endpoint() -> str | None:
    configured = os.environ.get("HARNESS_TELEMETRY_URL", "").strip()
    if not configured:
        return None
    endpoint = configured.rstrip("/")
    if endpoint.endswith("/api/v1/interactions/batch"):
        return endpoint
    if endpoint.endswith("/api/v1/interactions"):
        return f"{endpoint}/batch"
    return f"{endpoint}/api/v1/interactions/batch"


def upload_timeout_seconds() -> float:
    raw = os.environ.get("HARNESS_TELEMETRY_TIMEOUT_SECONDS", "")
    try:
        value = float(raw) if raw else DEFAULT_UPLOAD_TIMEOUT_SECONDS
    except ValueError:
        return DEFAULT_UPLOAD_TIMEOUT_SECONDS
    return min(max(value, 0.1), 3.0)


def upload_batch_size() -> int:
    raw = os.environ.get("HARNESS_TELEMETRY_BATCH_SIZE", "")
    try:
        value = int(raw) if raw else DEFAULT_UPLOAD_BATCH_SIZE
    except ValueError:
        return DEFAULT_UPLOAD_BATCH_SIZE
    return min(max(value, 1), 100)


def retry_at(attempt: int) -> str:
    delay = min(300, 2 ** min(max(attempt, 1), 8))
    return (
        (datetime.now(timezone.utc) + timedelta(seconds=delay))
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def remote_interaction(row: sqlite3.Row) -> dict[str, Any]:
    interaction: dict[str, Any] = {
        "interaction_id": row["interaction_id"],
        "revision": row["revision"],
        "project": {
            "id": row["project_id"],
            "name": row["project_name"],
        },
        "git_user": {
            "name": row["git_user_name"],
            "email": row["git_user_email"],
        },
        "input": {
            "text": row["input_text"],
            "truncated": bool(row["input_truncated"]),
        },
        "resources": {
            "workflows": json.loads(row["workflows_json"]),
            "skills": json.loads(row["skills_json"]),
            "templates": json.loads(row["templates_json"]),
            "rules": json.loads(row["rules_json"]),
        },
    }
    if row["revision"] == 2:
        interaction["output"] = {
            "text": row["output_text"] or "",
            "truncated": bool(row["output_truncated"]),
        }
    if row["input_tokens"] is not None:
        interaction["tokens"] = {
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "reasoning_tokens": row["reasoning_tokens"],
            "total_tokens": row["total_tokens"],
        }
        interaction["cache"] = {
            "cached_input_tokens": row["cached_input_tokens"],
            "hit_rate": row["cache_hit_rate"],
        }
    return interaction


def post_batch(endpoint: str, interactions: list[dict[str, Any]]) -> dict[str, Any]:
    body = json.dumps(
        {"interactions": interactions},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib_request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"Mini-Harness/{COLLECTOR_VERSION}",
        },
        method="POST",
    )
    with urllib_request.urlopen(
        request,
        timeout=upload_timeout_seconds(),
    ) as response:
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("response_too_large")
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("invalid_response")
    return parsed


def _safe_error_code(error: BaseException | str) -> str:
    if isinstance(error, str):
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", error)[:100] or "error"
    return type(error).__name__[:100]


def upload_pending(connection: sqlite3.Connection) -> int:
    endpoint = telemetry_endpoint()
    if endpoint is None:
        return 0
    rows = connection.execute(
        """
        SELECT *
        FROM interactions
        WHERE upload_revision < revision
          AND (dead_letter_revision IS NULL
               OR dead_letter_revision < revision)
          AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
        ORDER BY updated_at
        LIMIT ?
        """,
        (utc_now(), upload_batch_size()),
    ).fetchall()
    if not rows:
        return 0
    try:
        response = post_batch(
            endpoint,
            [remote_interaction(row) for row in rows],
        )
    except Exception as error:
        for row in rows:
            attempt = int(row["upload_attempts"]) + 1
            connection.execute(
                """
                UPDATE interactions
                SET upload_attempts = ?,
                    last_upload_error = ?,
                    next_attempt_at = ?
                WHERE interaction_id = ?
                  AND revision = ?
                """,
                (
                    attempt,
                    _safe_error_code(error),
                    retry_at(attempt),
                    row["interaction_id"],
                    row["revision"],
                ),
            )
        connection.commit()
        return 0

    successful = {
        normalize_text(item)
        for key in ("upserted", "unchanged")
        for item in (response.get(key) or [])
    }
    rejected = {
        normalize_text(item.get("interaction_id", "")): "server_rejected"
        for item in (response.get("rejected") or [])
        if isinstance(item, dict) and item.get("interaction_id")
    }
    uploaded = 0
    for row in rows:
        row_id = row["interaction_id"]
        revision = row["revision"]
        if row_id in successful:
            connection.execute(
                """
                UPDATE interactions
                SET upload_revision = ?,
                    upload_attempts = 0,
                    last_upload_error = NULL,
                    next_attempt_at = NULL,
                    dead_letter_revision = NULL
                WHERE interaction_id = ? AND revision = ?
                """,
                (revision, row_id, revision),
            )
            uploaded += 1
        elif row_id in rejected:
            connection.execute(
                """
                UPDATE interactions
                SET dead_letter_revision = ?,
                    last_upload_error = ?,
                    next_attempt_at = NULL
                WHERE interaction_id = ? AND revision = ?
                """,
                (revision, rejected[row_id], row_id, revision),
            )
        else:
            attempt = int(row["upload_attempts"]) + 1
            connection.execute(
                """
                UPDATE interactions
                SET upload_attempts = ?,
                    last_upload_error = 'missing_result',
                    next_attempt_at = ?
                WHERE interaction_id = ? AND revision = ?
                """,
                (attempt, retry_at(attempt), row_id, revision),
            )
    connection.commit()
    return uploaded


def record_diagnostic(
    telemetry_dir: Path,
    code: str,
    error: BaseException | None = None,
) -> None:
    try:
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "at": utc_now(),
            "code": code,
            "error_type": type(error).__name__ if error else None,
        }
        with (telemetry_dir / "collector.log").open(
            "a",
            encoding="utf-8",
        ) as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _save_prompt(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    root: Path,
    metadata: dict[str, str],
) -> None:
    session_id = normalize_text(payload.get("session_id")).strip() or "unknown"
    turn_id = normalize_text(payload.get("turn_id")).strip() or str(uuid.uuid4())
    input_text, input_truncated = redact_and_truncate(payload.get("prompt"))
    transcript_path, transcript_offset = transcript_position(
        payload.get("transcript_path")
    )
    baseline = latest_token_usage(transcript_path)
    current_git_user = git_user(root)
    now = utc_now()
    connection.execute(
        """
        INSERT INTO interactions (
            interaction_id, session_id, turn_id, revision,
            project_id, project_name, git_user_name, git_user_email,
            input_text, input_truncated,
            baseline_json, transcript_path, transcript_offset,
            created_at, updated_at
        ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (project_id, session_id, turn_id) DO NOTHING
        """,
        (
            interaction_id(metadata["id"], session_id, turn_id),
            session_id,
            turn_id,
            metadata["id"],
            metadata["name"],
            current_git_user["name"],
            current_git_user["email"],
            input_text,
            int(input_truncated),
            json.dumps(baseline) if baseline is not None else None,
            transcript_path,
            transcript_offset,
            now,
            now,
        ),
    )
    connection.commit()


def _save_stop(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    root: Path,
    metadata: dict[str, str],
    telemetry_dir: Path,
) -> None:
    session_id = normalize_text(payload.get("session_id")).strip() or "unknown"
    turn_id = normalize_text(payload.get("turn_id")).strip() or "unknown"
    row = connection.execute(
        """
        SELECT *
        FROM interactions
        WHERE project_id = ? AND session_id = ? AND turn_id = ?
        """,
        (metadata["id"], session_id, turn_id),
    ).fetchone()
    if row is None:
        _save_prompt(
            connection,
            {
                **payload,
                "prompt": "",
                "transcript_path": payload.get("transcript_path"),
            },
            root,
            metadata,
        )
        row = connection.execute(
            """
            SELECT *
            FROM interactions
            WHERE project_id = ? AND session_id = ? AND turn_id = ?
            """,
            (metadata["id"], session_id, turn_id),
        ).fetchone()
    if row is None:
        return
    if int(row["revision"]) >= 2:
        return

    output_text, output_truncated = redact_and_truncate(
        payload.get("last_assistant_message")
    )
    transcript_path = (
        normalize_text(payload.get("transcript_path")).strip()
        or row["transcript_path"]
    )
    resources, current, readable = parse_transcript_segment(
        transcript_path,
        row["transcript_offset"],
        atlas_root(root),
        turn_id,
    )
    baseline = (
        json.loads(row["baseline_json"]) if row["baseline_json"] else None
    )
    tokens, cache = token_delta(baseline, current)
    if not readable:
        resources = {category: [] for category in RESOURCE_CATEGORIES}
        tokens, cache = None, None
        record_diagnostic(telemetry_dir, "transcript_unavailable")
    connection.execute(
        """
        UPDATE interactions
        SET revision = 2,
            output_text = ?,
            output_truncated = ?,
            workflows_json = ?,
            skills_json = ?,
            templates_json = ?,
            rules_json = ?,
            input_tokens = ?,
            output_tokens = ?,
            reasoning_tokens = ?,
            total_tokens = ?,
            cached_input_tokens = ?,
            cache_hit_rate = ?,
            upload_attempts = 0,
            last_upload_error = NULL,
            next_attempt_at = NULL,
            dead_letter_revision = NULL,
            updated_at = ?
        WHERE interaction_id = ?
        """,
        (
            output_text,
            int(output_truncated),
            json.dumps(resources["workflow"]),
            json.dumps(resources["skills"]),
            json.dumps(resources["template"]),
            json.dumps(resources["rules"]),
            tokens["input_tokens"] if tokens else None,
            tokens["output_tokens"] if tokens else None,
            tokens["reasoning_tokens"] if tokens else None,
            tokens["total_tokens"] if tokens else None,
            cache["cached_input_tokens"] if cache else None,
            cache["hit_rate"] if cache else None,
            utc_now(),
            row["interaction_id"],
        ),
    )
    connection.commit()


def process_hook(
    payload: dict[str, Any],
    telemetry_dir: Path | None = None,
) -> bool:
    event_name = normalize_text(payload.get("hook_event_name")).strip()
    if event_name not in {"UserPromptSubmit", "Stop"}:
        return False
    root = find_project_root(payload.get("cwd"))
    if root is None:
        return False
    metadata = project_metadata(root)
    if metadata is None:
        return False
    target_dir = telemetry_dir or default_telemetry_dir(metadata["id"])
    try:
        connection = connect_database(target_dir)
    except Exception as error:
        record_diagnostic(target_dir, "outbox_open_failed", error)
        return True
    try:
        if event_name == "UserPromptSubmit":
            _save_prompt(connection, payload, root, metadata)
        else:
            _save_stop(
                connection,
                payload,
                root,
                metadata,
                target_dir,
            )
        upload_pending(connection)
    except Exception as error:
        record_diagnostic(target_dir, "collector_failed", error)
    finally:
        connection.close()
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            process_hook(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
