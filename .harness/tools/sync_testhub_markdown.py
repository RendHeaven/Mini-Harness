#!/usr/bin/env python3
"""对接 TestHub Harness 生命周期接口；默认只校验，不发起远程请求。"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from validate_testhub_markdown import validate_document


SUCCESS_UPLOAD_STATUSES = {200, 201}
SUCCESS_ACCEPTED_STATUSES = {200, 201, 202}
def _read_response(response: Any) -> tuple[int, dict[str, Any]]:
    body = response.read().decode("utf-8", errors="replace")
    try:
        return response.status, json.loads(body)
    except json.JSONDecodeError:
        return response.status, {"error": body[:1000]}


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body[:1000]}
    except urllib.error.URLError as exc:
        return 0, {"error": f"网络请求失败：{exc.reason}"}


def _multipart_body(file_path: Path, metadata: Mapping[str, Any]) -> tuple[bytes, str]:
    boundary = f"----HarnessTestHub{secrets.token_hex(12)}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "text/markdown"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n\r\n{json.dumps(metadata, ensure_ascii=False)}\r\n".encode("utf-8"),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file_path.name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode("utf-8"),
        file_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), boundary


def _upload(base_url: str, file_path: Path, metadata: Mapping[str, Any], idempotency_key: str) -> tuple[int, dict[str, Any]]:
    body, boundary = _multipart_body(file_path, metadata)
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/ai-ui-testing/projects/harness-import/",
        data=body,
        headers={"Idempotency-Key": idempotency_key, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return _read_response(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body[:1000]}
    except urllib.error.URLError as exc:
        return 0, {"error": f"网络请求失败：{exc.reason}"}


def _optional(config: Mapping[str, Any], source: str, target: str, result: dict[str, Any]) -> None:
    value = config.get(source)
    if value not in (None, ""):
        result[target] = value


def _metadata(config: Mapping[str, Any], version: str, commit_sha: str) -> dict[str, Any]:
    environments: dict[str, dict[str, Any]] = {}
    for code, raw in config.get("environments", {}).items():
        item = dict(raw)
        if not item.get("homepageUrl"):
            raise ValueError(f"environments.{code}.homepageUrl 不得为空")
        environment = {"homepage_url": item["homepageUrl"], "allow_write": item.get("allowWrite", code != "prod")}
        if item.get("authOrigins"):
            environment["auth_origins"] = [origin.strip() for origin in str(item["authOrigins"]).split(",") if origin.strip()]
        if item.get("authStatePath"):
            environment["auth_state_path"] = item["authStatePath"]
        environments[str(code)] = environment
    default_environment = str(config.get("defaultEnvironment", "test"))
    if environments and default_environment not in environments:
        raise ValueError(f"defaultEnvironment={default_environment} 未在 environments 中定义")
    metadata = {
        "external_project_id": str(config["externalProjectId"]),
        "project_name": str(config.get("projectName", config["externalProjectId"])),
        "version": version,
        "source_ref": str(config.get("sourceRef", "refs/heads/main")),
        "commit_sha": commit_sha,
        "case_set_key": str(config.get("caseSetKey", "default")),
        "external_document_id": str(config.get("externalDocumentId", "cases.md")),
        "document_path": str(config.get("documentPath", "testhub/cases.md")),
        "schema_version": str(config.get("schemaVersion", "external-harness-markdown-v1")),
    }
    if config.get("caseSetName"):
        metadata["case_set_name"] = str(config["caseSetName"])
    if environments:
        metadata["default_environment"] = default_environment
        metadata["homepage_url"] = environments[default_environment]["homepage_url"]
        metadata["environments"] = environments
    for source, target in (("projectPath", "project_path"), ("repositoryUrl", "repository_url"), ("defaultBranch", "default_branch"), ("description", "description")):
        _optional(config, source, target, metadata)
    return metadata


def _parse_scalar(value: str) -> Any:
    normalized = value.strip()
    if normalized in {"true", "True"}:
        return True
    if normalized in {"false", "False"}:
        return False
    if (normalized.startswith('"') and normalized.endswith('"')) or (normalized.startswith("'") and normalized.endswith("'")):
        return normalized[1:-1]
    return normalized


def _load_config(path: Path) -> dict[str, Any]:
    """读取本流程模板使用的简单 YAML 映射，避免依赖 PyYAML。"""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if ":" not in stripped:
            raise ValueError(f"{path}:{line_number} 不是 key: value 格式")
        key, value = stripped.split(":", 1)
        if not key or key.strip() != key:
            raise ValueError(f"{path}:{line_number} 配置键非法")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not value.strip():
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _idempotency_key(prefix: str, *parts: str) -> str:
    return "-".join([prefix, *[part.replace("/", "-").replace(" ", "-")[:80] for part in parts if part]])


def _sync(args: argparse.Namespace) -> int:
    errors, count = validate_document(args.cases)
    if errors or count == 0:
        _write_json(args.report_output, {"status": "invalid-for-sync" if errors else "skipped-no-cases", "caseCount": count, "errors": errors})
        return 1 if errors else 0
    config = _load_config(args.config)
    metadata = _metadata(config, args.version, args.commit_sha)
    digest = hashlib.sha256(args.cases.read_bytes()).hexdigest()
    key = _idempotency_key("testhub", metadata["external_project_id"], args.commit_sha[:12], metadata["external_document_id"], digest[:12])
    _write_json(args.metadata_output, metadata)
    if not args.upload:
        _write_json(args.report_output, {"status": "validated-not-uploaded", "documentSha256": digest, "idempotencyKey": key, "caseCount": count})
        return 0
    status, response = _upload(str(config["baseUrl"]), args.cases, metadata, key)
    report = {"status": "synced" if status in SUCCESS_UPLOAD_STATUSES else "failed", "syncedAt": datetime.now(timezone.utc).isoformat(), "documentSha256": digest, "idempotencyKey": key, "httpStatus": status, "response": {key: response[key] for key in ("replayed", "import_id", "project_id", "project_version_id", "task_id", "case_set_id", "case_set_revision_id", "imported_count", "case_count", "executable_count", "automation_blocked_count", "automation_blocked_cases", "environment_codes", "changes", "page_evidence_refresh", "error", "error_message") if key in response}}
    _write_json(args.report_output, report)
    return 0 if status in SUCCESS_UPLOAD_STATUSES else 1


def _run(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    payload: dict[str, Any] = {"case_set_revision_id": args.case_set_revision_id, "selection": {"mode": "case_ids", "case_ids": args.case_id} if args.case_id else {"mode": "all"}, "environment_code": args.environment_code or config.get("defaultEnvironment", "test"), "execution_concurrency": args.execution_concurrency, "cleanup_test_data": args.cleanup_test_data, "enable_gif": args.enable_gif}
    if args.project_version_id is not None:
        payload["project_version_id"] = args.project_version_id
    if args.callback_url or config.get("callbackUrl"):
        payload["callback_url"] = args.callback_url or config["callbackUrl"]
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/case-sets/{args.case_set_id}/runs/", method="POST", payload=payload)
    _write_json(args.report_output, {"operation": "run", "httpStatus": status, "accepted": status == 202 and response.get("accepted") is True, "executionStarted": response.get("execution_started"), "response": response})
    return 0 if status in SUCCESS_ACCEPTED_STATUSES else 1


def _query_import(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/import-batches/{args.import_id}/")
    _write_json(args.report_output, {"operation": "query-import", "httpStatus": status, "response": response})
    return 0 if status == 200 else 1


def _query_projects(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    query = "?search=" + urllib.parse.quote(args.search) if args.search else ""
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/projects/{query}")
    _write_json(args.report_output, {"operation": "query-projects", "httpStatus": status, "response": response})
    return 0 if status == 200 else 1


def _generate_assets(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/tasks/{args.task_id}/generate-assets/", method="POST", payload={})
    _write_json(args.report_output, {"operation": "generate-assets", "httpStatus": status, "response": response})
    return 0 if status in SUCCESS_ACCEPTED_STATUSES else 1


def _query_run(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    base = str(config["baseUrl"]).rstrip("/")
    encoded_run = urllib.parse.quote(args.run_id, safe="")
    status, response = _request(f"{base}/api/ai-ui-testing/runs/{encoded_run}/")
    report: dict[str, Any] = {"operation": "query-run", "httpStatus": status, "response": response}
    if args.case_executions and status == 200:
        suffix = "?status=" + urllib.parse.quote(args.status) if args.status else ""
        case_status, cases = _request(f"{base}/api/ai-ui-testing/runs/{encoded_run}/case-executions/{suffix}")
        report["caseExecutionsHttpStatus"] = case_status
        report["caseExecutions"] = cases
    _write_json(args.report_output, report)
    return 0 if status == 200 else 1


def _retry_failed(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    payload: dict[str, Any] = {"environment_code": args.environment_code or config.get("defaultEnvironment", "test"), "execution_concurrency": args.execution_concurrency, "cleanup_test_data": args.cleanup_test_data, "enable_gif": args.enable_gif}
    if args.case_set_revision_id is not None:
        payload["case_set_revision_id"] = args.case_set_revision_id
    if args.callback_url or config.get("callbackUrl"):
        payload["callback_url"] = args.callback_url or config["callbackUrl"]
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/runs/{urllib.parse.quote(args.run_id, safe='')}/retry-failed/", method="POST", payload=payload)
    _write_json(args.report_output, {"operation": "retry-failed", "httpStatus": status, "response": response})
    return 0 if status in SUCCESS_ACCEPTED_STATUSES else 1


def _delete_document(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    metadata = _metadata(config, args.version, args.commit_sha)
    payload = {"operation": "delete", **{key: metadata[key] for key in ("external_project_id", "version", "case_set_key", "external_document_id")}}
    key = _idempotency_key("testhub-delete", metadata["external_project_id"], args.commit_sha[:12], metadata["external_document_id"], hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12])
    status, response = _request(f"{str(config['baseUrl']).rstrip('/')}/api/ai-ui-testing/projects/harness-document-sync/", method="POST", payload=payload, headers={"Idempotency-Key": key})
    _write_json(args.report_output, {"operation": "delete-document", "idempotencyKey": key, "httpStatus": status, "response": response})
    return 0 if status in SUCCESS_ACCEPTED_STATUSES else 1


def _add_execution_options(parser: argparse.ArgumentParser, *, retry: bool = False) -> None:
    parser.add_argument("--environment-code")
    parser.add_argument("--execution-concurrency", type=int, default=1)
    parser.add_argument("--cleanup-test-data", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-gif", action="store_true")
    parser.add_argument("--callback-url")
    if retry:
        parser.add_argument("--case-set-revision-id", type=int)


def main() -> int:
    parser = argparse.ArgumentParser(description="预检、同步或调用 TestHub Harness 生命周期接口")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser("sync", help="校验并上传完整 Markdown 用例")
    sync.add_argument("--cases", type=Path, required=True)
    sync.add_argument("--config", type=Path, required=True)
    sync.add_argument("--version", required=True)
    sync.add_argument("--commit-sha", required=True)
    sync.add_argument("--metadata-output", type=Path, required=True)
    sync.add_argument("--report-output", type=Path, required=True)
    sync.add_argument("--upload", action="store_true", help="显式允许发起上传")
    sync.set_defaults(handler=_sync)
    run = subparsers.add_parser("run", help="发起已同步用例的远程执行")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--case-set-id", type=int, required=True)
    run.add_argument("--case-set-revision-id", type=int, required=True)
    run.add_argument("--project-version-id", type=int)
    run.add_argument("--case-id", action="append", default=[])
    run.add_argument("--report-output", type=Path, required=True)
    _add_execution_options(run)
    run.set_defaults(handler=_run)
    query_import = subparsers.add_parser("query-import", help="查询上传批次的导入结果")
    query_import.add_argument("--config", type=Path, required=True)
    query_import.add_argument("--import-id", type=int, required=True)
    query_import.add_argument("--report-output", type=Path, required=True)
    query_import.set_defaults(handler=_query_import)
    projects = subparsers.add_parser("query-projects", help="查询 Harness 导入项目")
    projects.add_argument("--config", type=Path, required=True)
    projects.add_argument("--search")
    projects.add_argument("--report-output", type=Path, required=True)
    projects.set_defaults(handler=_query_projects)
    assets = subparsers.add_parser("generate-assets", help="在用例或页面证据变更后重新生成自动化资产")
    assets.add_argument("--config", type=Path, required=True)
    assets.add_argument("--task-id", type=int, required=True)
    assets.add_argument("--report-output", type=Path, required=True)
    assets.set_defaults(handler=_generate_assets)
    query = subparsers.add_parser("query-run", help="查询运行汇总及可选用例明细")
    query.add_argument("--config", type=Path, required=True)
    query.add_argument("--run-id", required=True)
    query.add_argument("--case-executions", action="store_true")
    query.add_argument("--status")
    query.add_argument("--report-output", type=Path, required=True)
    query.set_defaults(handler=_query_run)
    retry = subparsers.add_parser("retry-failed", help="重试原 Run 中失败或阻塞的用例")
    retry.add_argument("--config", type=Path, required=True)
    retry.add_argument("--run-id", required=True)
    retry.add_argument("--report-output", type=Path, required=True)
    _add_execution_options(retry, retry=True)
    retry.set_defaults(handler=_retry_failed)
    delete = subparsers.add_parser("delete-document", help="删除 TestHub 已同步的 Harness 文档")
    delete.add_argument("--config", type=Path, required=True)
    delete.add_argument("--version", required=True)
    delete.add_argument("--commit-sha", required=True)
    delete.add_argument("--report-output", type=Path, required=True)
    delete.set_defaults(handler=_delete_document)
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
