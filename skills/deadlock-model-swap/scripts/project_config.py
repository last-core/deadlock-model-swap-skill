"""Load, validate, query and initialise a Deadlock model-swap project.json.

This module is deliberately dependency-free. It is shared by the step
sub-skills and by the user.

Usage:
    python project_config.py init <out.json>
    python project_config.py check <project.json>
    python project_config.py get <project.json> <dotted.key>
    python project_config.py set <project.json> <dotted.key> <json-value>
    python project_config.py resolve <project.json> <dotted.path.key>

The config is the anti-hardcoding contract: every stage reads the same file and
updates its gate. No stage should carry a hero name, bone name, material name or
machine path of its own.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

GATE_VALUES = {"pending", "pass", "fail", "skip"}
FORMATS = {"mmd", "pmx", "fbx", "gltf", "glb", "other"}
AXES = {"X", "Y", "Z", "-X", "-Y", "-Z"}

REQUIRED = {
    "schema_version",
    "game",
    "hero",
    "source",
    "units",
    "stock",
    "paths",
    "tool_versions",
    "gates",
}

REQUIRED_GAME = {"build", "install_dir", "content_addon_dir", "game_addon_dir", "staging_dir"}
REQUIRED_HERO = {
    "display_name",
    "model_asset",
    "panorama_key",
    "model_path",
    "skeleton",
    "hitbox_sets",
    "attachments",
    "camera",
    "bodygroups",
    "lods",
}
REQUIRED_SOURCE = {
    "format",
    "mesh_object",
    "armature_object",
    "vertex_groups",
    "mapping_module",
    "up_axis",
    "forward_axis",
    "depth_axis",
}
REQUIRED_UNITS = {"source", "target", "scale"}
REQUIRED_STOCK = {
    "body_tris",
    "body_verts",
    "tri_budget",
    "materials",
    "portrait_sizes",
    "weapon",
}
REQUIRED_PATHS = {
    "blender",
    "resourcecompiler_game",
    "resourcecompiler_sdk",
    "source2viewer",
    "vpk_tool",
}
REQUIRED_TOOLS = {"blender", "dmx_addon", "csdk", "source2viewer"}
REQUIRED_GATES = {
    "setup",
    "rig_align",
    "decimate",
    "weights",
    "materials",
    "export",
    "modeldoc",
    "animgraph2",
    "weapon",
    "portraits",
    "validate",
}


def template() -> dict[str, Any]:
    """Return a blank project template with placeholders, not guessed values."""
    return {
        "schema_version": SCHEMA_VERSION,
        "game": {
            "build": "",
            "install_dir": "<GAME_INSTALL_DIR>",
            "content_addon_dir": "<CONTENT_ADDON_DIR>",
            "game_addon_dir": "<GAME_ADDON_DIR>",
            "staging_dir": "<STAGING_DIR>",
        },
        "hero": {
            "display_name": "",
            "model_asset": "",
            "panorama_key": "",
            "model_path": "",
            "skeleton": {
                "bone_count": 0,
                "bone_names": [],
                "spine_chain": [],
                "bind_transforms": "stock_skeleton.json",
            },
            "hitbox_sets": [],
            "attachments": [],
            "camera": {},
            "bodygroups": [],
            "lods": [],
        },
        "source": {
            "format": "mmd",
            "mesh_object": "",
            "armature_object": "",
            "vertex_groups": 0,
            "mapping_module": "",
            "up_axis": "Z",
            "forward_axis": "Y",
            "depth_axis": "Y",
            "side_axis": "X",
            "align_axes": "depth",
            "compact_groups": [],
            "long_axis": "",
            "muzzle_axis": "",
        },
        "units": {"source": "m", "target": "in", "scale": 39.37},
        "weights": {
            "smooth_iters": 4,
            "smooth_factor": 0.5,
            "max_influences": 4,
            "cull": 0.001,
            "fallback_bone": "",
            "max_p99": None,
            "force_material": "",
            "force_chain": [],
            "force_root_coord": None,
            "force_tip_coord": None,
        },
        "stock": {
            "body_tris": 0,
            "body_verts": 0,
            "tri_budget": 0,
            "materials": [],
            "portrait_sizes": {},
            "weapon": {
                "bone": "",
                "mesh_name": "",
                "bbox_local": {"lo": [], "hi": []},
                "long_axis": "",
                "up_axis": "",
                "muzzle_axis": "",
            },
        },
        "paths": {
            "blender": "",
            "resourcecompiler_game": "",
            "resourcecompiler_sdk": "",
            "source2viewer": "",
            "vpk_tool": "",
            "material_dir": "",
        },
        "tool_versions": {
            "blender": "",
            "dmx_addon": "io_scene_valvesource2",
            "csdk": "12",
            "source2viewer": "20.0+",
        },
        "gates": {key: "pending" for key in sorted(REQUIRED_GATES)},
    }


def load(path: str | os.PathLike[str]) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return data


def save(path: str | os.PathLike[str], data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def get(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set_value(data: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _missing(data: dict[str, Any], keys: set[str], where: str, errors: list[str]) -> None:
    for key in sorted(keys):
        if key not in data:
            errors.append(f"{where}: missing key {key!r}")


def _check_axes(source: dict[str, Any], errors: list[str]) -> None:
    for key in ("up_axis", "forward_axis", "depth_axis"):
        value = source.get(key)
        if value not in AXES:
            errors.append(f"source.{key}: expected one of {sorted(AXES)}, got {value!r}")


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block a stage; warnings need review."""
    errors: list[str] = []
    warnings: list[str] = []

    _missing(data, REQUIRED, "root", errors)
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version: expected {SCHEMA_VERSION}, got {data.get('schema_version')!r}"
        )

    game = data.get("game", {})
    if isinstance(game, dict):
        _missing(game, REQUIRED_GAME, "game", errors)
    else:
        errors.append("game: expected an object")

    hero = data.get("hero", {})
    if isinstance(hero, dict):
        _missing(hero, REQUIRED_HERO, "hero", errors)
        if not hero.get("model_asset"):
            errors.append("hero.model_asset: required")
        if not hero.get("panorama_key"):
            warnings.append("hero.panorama_key: empty; portraits may target the wrong key")
        skeleton = hero.get("skeleton", {})
        if isinstance(skeleton, dict):
            if not skeleton.get("bone_names"):
                errors.append("hero.skeleton.bone_names: required")
            if not skeleton.get("bind_transforms"):
                warnings.append("hero.skeleton.bind_transforms: empty; skeleton identity cannot be checked")
    else:
        errors.append("hero: expected an object")

    source = data.get("source", {})
    if isinstance(source, dict):
        _missing(source, REQUIRED_SOURCE, "source", errors)
        _check_axes(source, errors)
        fmt = str(source.get("format", "")).lower()
        if fmt not in FORMATS:
            errors.append(f"source.format: expected one of {sorted(FORMATS)}, got {source.get('format')!r}")
        if not source.get("mesh_object"):
            errors.append("source.mesh_object: required")
        if not source.get("armature_object"):
            errors.append("source.armature_object: required")
    else:
        errors.append("source: expected an object")

    units = data.get("units", {})
    if isinstance(units, dict):
        _missing(units, REQUIRED_UNITS, "units", errors)
        try:
            scale = float(units.get("scale", 0))
            if scale <= 0:
                errors.append("units.scale: must be positive")
        except (TypeError, ValueError):
            errors.append("units.scale: must be a number")
    else:
        errors.append("units: expected an object")

    stock = data.get("stock", {})
    if isinstance(stock, dict):
        _missing(stock, REQUIRED_STOCK, "stock", errors)
        body_tris = stock.get("body_tris")
        budget = stock.get("tri_budget")
        if isinstance(body_tris, int) and isinstance(budget, int):
            if body_tris <= 0:
                errors.append("stock.body_tris: must be measured and positive")
            if budget <= 0:
                errors.append("stock.tri_budget: must be positive")
            elif body_tris and budget < body_tris:
                warnings.append("stock.tri_budget is below stock.body_tris")
        if not stock.get("materials"):
            errors.append("stock.materials: required")
        weapon = stock.get("weapon", {})
        if isinstance(weapon, dict):
            if not weapon.get("bone"):
                warnings.append("stock.weapon.bone: empty; weapon swap cannot locate the bone")
            if not weapon.get("mesh_name"):
                warnings.append("stock.weapon.mesh_name: empty; weapon swap cannot find the stock mesh")
    else:
        errors.append("stock: expected an object")

    paths = data.get("paths", {})
    if isinstance(paths, dict):
        _missing(paths, REQUIRED_PATHS, "paths", errors)
        for key, value in paths.items():
            if isinstance(value, str) and ("<" in value or value == ""):
                warnings.append(f"paths.{key}: placeholder or empty; set it before compiling")
    else:
        errors.append("paths: expected an object")

    tools = data.get("tool_versions", {})
    if isinstance(tools, dict):
        _missing(tools, REQUIRED_TOOLS, "tool_versions", errors)
    else:
        errors.append("tool_versions: expected an object")

    gates = data.get("gates", {})
    if isinstance(gates, dict):
        for key in sorted(REQUIRED_GATES):
            if key not in gates:
                errors.append(f"gates: missing {key!r}")
            elif gates[key] not in GATE_VALUES:
                errors.append(f"gates.{key}: expected one of {sorted(GATE_VALUES)}, got {gates[key]!r}")
    else:
        errors.append("gates: expected an object")

    return errors, warnings


def resolve_path(data: dict[str, Any], dotted: str) -> str:
    value = get(data, dotted)
    if not isinstance(value, str) or not value:
        raise KeyError(f"{dotted}: no path value")
    return str(Path(value).expanduser().resolve())


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="write a blank project.json template")
    p_init.add_argument("out")

    p_check = sub.add_parser("check", help="validate a project.json")
    p_check.add_argument("config")
    p_check.add_argument("--strict", action="store_true", help="treat warnings as errors")

    p_get = sub.add_parser("get", help="print a dotted value")
    p_get.add_argument("config")
    p_get.add_argument("key")

    p_set = sub.add_parser("set", help="set a dotted value from JSON or text")
    p_set.add_argument("config")
    p_set.add_argument("key")
    p_set.add_argument("value")

    p_resolve = sub.add_parser("resolve", help="print an absolute path")
    p_resolve.add_argument("config")
    p_resolve.add_argument("key")

    args = parser.parse_args(argv)

    if args.command == "init":
        save(args.out, template())
        print(f"wrote {args.out}")
        return 0

    try:
        data = load(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        errors, warnings = validate(data)
        for warning in warnings:
            print(f"WARN  {warning}")
        for error in errors:
            print(f"ERROR {error}")
        if errors or (args.strict and warnings):
            print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
            return 1
        print(f"\nOK: {len(warnings)} warning(s)")
        return 0

    if args.command == "get":
        value = get(data, args.key)
        if value is None:
            print(f"error: key not found: {args.key}", file=sys.stderr)
            return 1
        print(json.dumps(value, indent=2, ensure_ascii=False) if isinstance(value, (dict, list)) else value)
        return 0

    if args.command == "set":
        set_value(data, args.key, _parse_value(args.value))
        save(args.config, data)
        print(f"set {args.key}")
        return 0

    if args.command == "resolve":
        try:
            print(resolve_path(data, args.key))
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
