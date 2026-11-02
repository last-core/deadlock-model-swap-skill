"""Cross-cutting validation for a Deadlock model swap.

    python validate.py --config project.json \
        [--checks config,addon,staging,reports,pak,portraits] \
        [--stock-measurements stock_measurements.json] \
        [--weights-report weights_report.json] \
        [--export-report export_report.json] \
        [--decimate-report decimate_report.json] \
        [--weapon-report weapon_report.json] \
        [--alignment-report alignment_report.json] \
        [--vpk pak05_dir.vpk] [--model <compiled>.vmdl_c] \
        [--s2v Source2Viewer-CLI] [--json-out validation_report.json]

Checks that need GUI/Source 2 Viewer dumps are reported as `skip` with the exact
follow-up, not silently passed. The script never modifies assets.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ALLOWED_SUFFIXES = (".vmdl_c", ".vmat_c", ".vtex_c")
FORBIDDEN_SUFFIXES = (
    ".dmx", ".vmdl", ".fbx", ".gltf", ".glb", ".blend",
    ".vtex", ".vmat", ".vdata", ".vpdi",
    ".vnmskel_c", ".vnmclip_c", ".vdata_c",
)
FORBIDDEN_NAMES = {"gameinfo.gi", "image_compiler.vdata_c"}


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def cfg(data: dict, dotted: str, default=None):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def add(report: list, name: str, status: str, detail: str = "") -> None:
    report.append({"check": name, "status": status, "detail": detail})


def inspect_tree(root: Path) -> tuple[list[str], list[str], int]:
    forbidden = []
    unexpected = []
    allowed = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        name = path.name
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
            forbidden.append(rel)
        elif name.endswith(ALLOWED_SUFFIXES):
            allowed += 1
        else:
            unexpected.append(rel)
    return forbidden, unexpected, allowed


def check_config(config: dict) -> list[dict]:
    report = []
    required = ["game", "hero", "source", "units", "stock", "paths", "tool_versions", "gates"]
    missing = [key for key in required if key not in config]
    if missing:
        add(report, "config", "fail", "missing: " + ", ".join(missing))
    else:
        add(report, "config", "pass", "top-level keys present")
    if not cfg(config, "hero.skeleton.bone_names"):
        add(report, "skeleton-record", "fail", "hero.skeleton.bone_names is empty")
    else:
        add(report, "skeleton-record", "pass", f"{len(cfg(config, 'hero.skeleton.bone_names'))} bones recorded")

    gates = cfg(config, "gates", {}) or {}
    required = ["setup", "rig_align", "decimate", "weights", "materials", "export", "modeldoc", "animgraph2"]
    missing_gates = [name for name in required if gates.get(name) != "pass"]
    optional = [name for name in ("weapon", "portraits") if gates.get(name) not in ("pass", "skip")]
    if missing_gates:
        add(report, "gates", "fail", "not pass: " + ", ".join(missing_gates))
    elif optional:
        add(report, "gates", "warn", "optional gate unresolved: " + ", ".join(optional))
    elif gates.get("validate") not in ("pass", "pending"):
        add(report, "gates", "warn", "validate gate is " + str(gates.get("validate")))
    else:
        add(report, "gates", "pass", "all required gates pass")
    return report


def check_reports(config: dict, reports: dict) -> list[dict]:
    report = []
    budget = cfg(config, "stock.tri_budget")
    decimate = reports.get("decimate")
    if decimate:
        tris = decimate.get("tris_after")
        if budget and isinstance(tris, int):
            status = "pass" if tris <= int(budget) else "fail"
            add(report, "triangle-budget", status, f"{tris} <= {budget}")
        else:
            add(report, "triangle-budget", "warn", "report present but budget/tris missing")
    else:
        add(report, "triangle-budget", "skip", "no decimate report")

    weights = reports.get("weights")
    if weights:
        unweighted = weights.get("dest_verts_no_weight")
        influences = weights.get("influences", {})
        max_inf = max((int(k) for k in influences), default=0)
        sums_min = weights.get("weight_sum_min")
        sums_max = weights.get("weight_sum_max")
        status = "pass"
        details = []
        if unweighted not in (0, None):
            status = "fail"
            details.append(f"unweighted={unweighted}")
        if max_inf > 4:
            status = "fail"
            details.append(f"max influences={max_inf}")
        if isinstance(sums_min, (int, float)) and abs(sums_min - 1.0) > 1e-3:
            status = "fail"
            details.append(f"min sum={sums_min}")
        if isinstance(sums_max, (int, float)) and abs(sums_max - 1.0) > 1e-3:
            status = "fail"
            details.append(f"max sum={sums_max}")
        add(report, "weights", status, ", ".join(details) or "0 unweighted; sums ~1; <=4 influences")
    else:
        add(report, "weights", "skip", "no weights report")

    export = reports.get("export")
    if export:
        add(report, "export", "pass", f"dmx={export.get('dmx')} bytes={export.get('bytes')}")
    else:
        add(report, "export", "skip", "no export report")

    weapon = reports.get("weapon")
    if weapon:
        add(report, "weapon", "pass", "weapon report present; confirm fixed-camera render")
    else:
        add(report, "weapon", "skip", "no weapon report (skip if weapon not swapped)")

    alignment = reports.get("alignment")
    if alignment:
        rows = alignment.get("rows", [])
        deltas = [abs(row.get("delta", 0.0)) for row in rows]
        if deltas:
            worst = max(deltas)
            status = "warn" if worst > 0.05 else "pass"
            add(report, "alignment-profile", status, f"worst median delta={worst:.4f}")
        else:
            add(report, "alignment-profile", "warn", "no rows in alignment report")
    else:
        add(report, "alignment-profile", "skip", "no alignment report")

    return report


def check_portraits(config: dict, report_path: str | None) -> list[dict]:
    report = []
    if report_path:
        data = load_json(report_path)
        missing = [item for item in data.get("missing", [])]
        status = "fail" if missing else "pass"
        add(report, "portraits", status, f"{len(missing)} missing" if missing else "all replaced variants compiled")
        return report
    sizes = cfg(config, "stock.portrait_sizes", {}) or {}
    add(report, "portraits", "skip",
        "supply --portrait-report or compare compiled names/sizes in Source 2 Viewer: "
        + ", ".join(f"{k}={v}" for k, v in sizes.items()))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--checks", default="config,addon,staging,reports,portraits")
    parser.add_argument("--stock-measurements", default=None)
    parser.add_argument("--weights-report", default=None)
    parser.add_argument("--export-report", default=None)
    parser.add_argument("--decimate-report", default=None)
    parser.add_argument("--weapon-report", default=None)
    parser.add_argument("--alignment-report", default=None)
    parser.add_argument("--portrait-report", default=None)
    parser.add_argument("--vpk", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--s2v", default=None)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    config = load_json(args.config)
    checks = {c.strip() for c in args.checks.split(",") if c.strip()}
    results: list[dict] = []

    if "config" in checks:
        results.extend(check_config(config))
        shared = Path(__file__).resolve().parents[2] / "deadlock-model-swap" / "scripts" / "project_config.py"
        if shared.exists():
            result = subprocess.run(
                [sys.executable, str(shared), "check", args.config],
                capture_output=True, text=True, errors="replace",
            )
            detail = (result.stdout + result.stderr).strip().splitlines()[-1] if (result.stdout + result.stderr).strip() else ""
            add(results, "config-schema", "pass" if result.returncode == 0 else "fail", detail)
        else:
            add(results, "config-schema", "skip", f"shared checker not found: {shared}")

    if "addon" in checks:
        game_addon = cfg(config, "game.game_addon_dir")
        if game_addon and Path(game_addon).is_dir():
            forbidden, unexpected, allowed = inspect_tree(Path(game_addon))
            if forbidden:
                add(results, "addon-tree", "fail", "forbidden: " + ", ".join(forbidden[:20]))
            elif unexpected:
                add(results, "addon-tree", "warn", "unexpected: " + ", ".join(unexpected[:20]))
            else:
                add(results, "addon-tree", "pass", f"{allowed} compiled files")
        else:
            add(results, "addon-tree", "skip", "game.game_addon_dir not found")

    if "staging" in checks:
        staging = cfg(config, "game.staging_dir")
        if staging and Path(staging).is_dir():
            forbidden, unexpected, allowed = inspect_tree(Path(staging))
            if forbidden:
                add(results, "staging-tree", "fail", "forbidden: " + ", ".join(forbidden[:20]))
            elif unexpected:
                add(results, "staging-tree", "warn", "unexpected: " + ", ".join(unexpected[:20]))
            else:
                add(results, "staging-tree", "pass", f"{allowed} compiled files")
        else:
            add(results, "staging-tree", "skip", "game.staging_dir not found")

    if "reports" in checks:
        reports = {
            "weights": load_json(args.weights_report) if args.weights_report else None,
            "export": load_json(args.export_report) if args.export_report else None,
            "decimate": load_json(args.decimate_report) if args.decimate_report else None,
            "weapon": load_json(args.weapon_report) if args.weapon_report else None,
            "alignment": load_json(args.alignment_report) if args.alignment_report else None,
        }
        results.extend(check_reports(config, reports))

    if "portraits" in checks:
        results.extend(check_portraits(config, args.portrait_report))

    if "pak" in checks:
        if args.vpk:
            script = Path(__file__).resolve().parents[2] / "deadlock-animgraph2-compile" / "scripts" / "check_pak.py"
            if script.exists():
                command = [sys.executable, str(script), "--vpk", args.vpk]
                if args.model:
                    command += ["--model", args.model]
                if args.s2v:
                    command += ["--s2v", args.s2v]
                result = subprocess.run(command, capture_output=True, text=True, errors="replace")
                status = "pass" if result.returncode == 0 else "fail"
                add(results, "pak", status, (result.stdout + result.stderr).strip()[-1200:])
            else:
                add(results, "pak", "skip", f"check_pak.py not found at {script}")
        else:
            add(results, "pak", "skip", "no --vpk supplied")

    if "skeleton" in checks:
        stock = load_json(args.stock_measurements) if args.stock_measurements else {}
        if not stock:
            add(results, "skeleton-identity", "skip",
                "supply stock_measurements.json and a compiled skeleton dump; compare stock bones/transforms")
        else:
            bones = [b.get("name") for arm in stock.get("armatures", []) for b in arm.get("bones", [])]
            add(results, "skeleton-identity", "warn",
                f"{len(bones)} stock bones recorded; compare the compiled .vmdl_c dump manually")

    failures = [item for item in results if item["status"] == "fail"]
    warnings = [item for item in results if item["status"] == "warn"]
    for item in results:
        print(f"{item['status'].upper():5s} {item['check']:22s} {item['detail']}")
    print(f"\n{len(failures)} failure(s), {len(warnings)} warning(s), "
          f"{sum(1 for item in results if item['status'] == 'skip')} skipped")

    report = {
        "config": str(Path(args.config).resolve()),
        "results": results,
        "failures": len(failures),
        "warnings": len(warnings),
        "ok": not failures,
    }
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", out)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
