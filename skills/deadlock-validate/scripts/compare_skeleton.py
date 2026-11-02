"""Compare a compiled skeleton dump to the stock skeleton record.

    python compare_skeleton.py --stock stock_skeleton.json \
        --compiled compiled_skeleton.json \
        [--tolerance 1e-6] [--json-out skeleton_report.json]

Both files use the shape produced by measure_stock.py:

    {"armatures": [{"name": "...", "bones": [
        {"name": "...", "matrix_local": [[...], ...]}, ...
    ]}]}

Added bones are allowed. Every stock bone must be present, and its matrix must
match within tolerance. The script reports missing, extra and changed bones.

It does not generate the compiled dump; export the compiled model's skeleton
with your Source 2 tool and convert it to this shape.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def flatten_bones(data: dict) -> dict[str, list[list[float]]]:
    bones: dict[str, list[list[float]]] = {}
    for armature in data.get("armatures", []):
        for bone in armature.get("bones", []):
            name = bone.get("name")
            matrix = bone.get("matrix_local")
            if name and matrix:
                bones[name] = matrix
    return bones


def max_delta(a: list[list[float]], b: list[list[float]]) -> float:
    worst = 0.0
    for row_a, row_b in zip(a, b):
        for value_a, value_b in zip(row_a, row_b):
            worst = max(worst, abs(float(value_a) - float(value_b)))
    return worst


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True)
    parser.add_argument("--compiled", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    stock = flatten_bones(load(args.stock))
    compiled = flatten_bones(load(args.compiled))
    if not stock:
        raise SystemExit("no stock bones found")
    if not compiled:
        raise SystemExit("no compiled bones found")

    stock_names = set(stock)
    compiled_names = set(compiled)
    missing = sorted(stock_names - compiled_names)
    extra = sorted(compiled_names - stock_names)
    changed = []
    for name in sorted(stock_names & compiled_names):
        delta = max_delta(stock[name], compiled[name])
        if delta > args.tolerance:
            changed.append({"bone": name, "max_delta": delta})

    print(f"stock bones: {len(stock_names)}  compiled bones: {len(compiled_names)}")
    print(f"missing: {len(missing)}  extra/added: {len(extra)}  changed: {len(changed)}")
    for name in missing:
        print("  MISSING", name)
    for name in extra:
        print("  ADDED  ", name)
    for item in changed:
        print("  CHANGED %-28s max_delta=%.9f" % (item["bone"], item["max_delta"]))

    report = {
        "stock": str(Path(args.stock).resolve()),
        "compiled": str(Path(args.compiled).resolve()),
        "stock_bones": len(stock_names),
        "compiled_bones": len(compiled_names),
        "missing": missing,
        "added": extra,
        "changed": changed,
        "tolerance": args.tolerance,
        "ok": not missing and not changed,
    }
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", out)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
