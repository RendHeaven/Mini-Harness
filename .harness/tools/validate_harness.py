from __future__ import annotations

import argparse
import sys
sys.dont_write_bytecode = True
import json

from local_paths import configure_services, project_config_path
from pathlib import Path

from core_validation import *  # noqa: F403
from asset_registry import load_asset_registry


def artifact_paths(cycle: Path, config: HarnessConfig) -> dict[str, Path]:
    identity = parse_cycle_identity(cycle.name)
    if identity is None:
        raise ValueError(f"需求周期目录名非法: {cycle}")
    product = cycle / Path(*config.product_root.parts)
    ui = cycle / Path(*config.ui_root.parts)
    development = cycle / Path(*config.development_root.parts)
    return {
        "manifest": cycle / Path(*config.cycle_manifest.parts),
        "product": product,
        "discovery": product / Path(*config.product_discovery.parts),
        "prd": product / config.product_prd.format(version=identity.version),
        "prdChangelog": product / "prd-changelog.md",
        "prdReview": product / Path(*config.product_prd_review.parts),
        "devGuide": product / Path(*config.product_dev_guide.parts),
        "ui": ui,
        "uiHandoff": ui / Path(*config.ui_handoff.parts),
        "development": development,
        "execution": development / Path(*config.development_execution.parts),
        "developmentFrontend": development / Path(*config.development_frontend.parts),
        "developmentBackend": development / Path(*config.development_backend.parts),
        "developmentTesthub": development / Path(*config.development_testhub.parts),
    }


def validate_demand_cycle(cycle: Path, config: HarnessConfig, project_root: Path, result: Result) -> dict[str, GateOutcome]:
    if config.schema_version != CONFIG_SCHEMA_VERSION:
        result.error("需求周期只支持 Schema 20 配置")
        return {}
    from role_gates import validate_cycle
    return validate_cycle(cycle, config, project_root, result)


def validate_work_item(work_item: Path, config: HarnessConfig, result: Result, project_root: Path | None = None) -> dict[str, GateOutcome]:
    root = project_root or work_item.resolve().parents[2]
    return validate_demand_cycle(work_item.resolve(), config, root.resolve(), result)


def discover_demand_cycles(project_root: Path, config: HarnessConfig, result: Result) -> list[Path]:
    assets = load_asset_registry(project_root, config, result)
    root = project_root / config.demand_cycle_root
    if not root.exists():
        result.info("demandCycleRoot 中暂无需求版本")
        return []
    if not root.is_dir():
        result.error(f"demandCycleRoot 不是目录: {root}")
        return []
    cycles: list[Path] = []
    for child in sorted(path for path in root.iterdir() if path.is_dir()):
        if parse_cycle_identity(child.name) is None:
            result.error(f"demandCycleRoot 包含非法版本目录: {child.name}")
        elif (child / Path(*config.cycle_manifest.parts)).is_file():
            cycles.append(child)
        else:
            result.error(f"需求周期缺少 manifest.yaml: {child}")
    return cycles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校验 Harness Core、Schema 20 四角色独立 Gate")
    parser.add_argument("demand_cycle", nargs="?", type=Path, help="可选：只校验指定需求周期目录")
    parser.add_argument("--project-root", type=Path, help="项目 Harness 根目录")
    parser.add_argument("--service-paths", type=Path, help="本机服务 ID 到绝对目录的 JSON 映射")
    parser.add_argument("--core-only", action="store_true", help="只校验 Harness Core")
    parser.add_argument("--print-core-hash", action="store_true", help="打印当前 Core 内容哈希")
    parser.add_argument(
        "--allow-dirty-core",
        action="store_true",
        help="仅供 Core 开发期使用；允许按脏工作区内容校验，不能作为发布 Gate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    harness_root = Path(__file__).resolve().parents[1]
    if args.print_core_hash:
        print(compute_content_hash(harness_root, CORE_HASH_DEFAULT_PATHS))
        return 0

    result = Result.empty()
    configure_services(Path.cwd(), {}, {})
    config = validate_core(harness_root, result)
    project_root = args.project_root.resolve() if args.project_root else None
    project_config_valid = True
    if project_root is not None:
        try:
            config_path = project_config_path(project_root)
            parsed = parse_config(config_path, result)
        except ValueError as error:
            result.error(str(error))
            parsed = None
        if parsed is not None:
            config = parsed
            validate_core_pin(
                project_root,
                config,
                result,
                allow_dirty_core=args.allow_dirty_core,
            )
            if args.service_paths:
                try:
                    catalog = load_yaml_mapping(project_root / config.service_catalog, result)
                    overrides = json.loads(args.service_paths.read_text(encoding="utf-8"))
                    configure_services(project_root, catalog["services"], overrides)
                except Exception as error:
                    result.error(f"本地服务路径映射无效: {type(error).__name__}")
                    project_config_valid = False
            validate_service_catalog(project_root, config, result)
            from role_gates import validate_ledger
            validate_ledger(project_root, config, result)
        else:
            project_config_valid = False

    if not args.core_only and (project_root is not None or args.demand_cycle is not None):
        if project_root is not None and not project_config_valid:
            cycles = []
            effective_root = project_root
        elif args.demand_cycle is not None:
            cycles = [args.demand_cycle.resolve()]
            effective_root = project_root or args.demand_cycle.resolve().parents[2]
        else:
            effective_root = project_root
            cycles = discover_demand_cycles(effective_root, config, result) if effective_root else []
        for cycle in cycles:
            validate_demand_cycle(cycle, config, effective_root, result)

    for message in result.infos:
        print(f"[INFO] {message}")
    for message in result.warnings:
        print(f"[WARN] {message}")
    for message in result.errors:
        print(f"[ERROR] {message}")
    if result.errors:
        print(f"Harness 校验失败: {len(result.errors)} 个错误, {len(result.warnings)} 个警告")
        return 1
    print(f"Harness 校验通过: 0 个错误, {len(result.warnings)} 个警告")
    return 0


if __name__ == "__main__":
    sys.exit(main())
