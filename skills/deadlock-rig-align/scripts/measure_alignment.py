"""Measure a mesh's per-material/per-height profile against a bone chain.

Run inside Blender:

    blender -b -P measure_alignment.py -- \
        --config project.json \
        --blend aligned.blend \
        [--mesh NAME] [--armature NAME] \
        [--chain pelvis,spine_0,spine_1,spine_2,neck_0,head] \
        [--skip-materials hair_mat,cape_mat] \
        [--json-out alignment_report.json]

The output is a table of, per height band and material: vertex count, depth
range, median depth, interpolated chain depth, and delta. A systematic delta
means the mesh is displaced from the skeleton.

This is a diagnostic. It does not move anything.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:  # pragma: no cover
    raise SystemExit("This script must be run with Blender's Python") from exc


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


def axis_index(axis: str) -> int:
    axis = axis.upper().lstrip("+")
    if axis not in ("X", "Y", "Z"):
        raise ValueError(f"axis must be X, Y or Z, got {axis!r}")
    return "XYZ".index(axis)


def side_axis_for(depth_axis: str, up_axis: str) -> str:
    depth = depth_axis.upper()
    up = up_axis.upper()
    for candidate in ("X", "Y", "Z"):
        if candidate not in (depth, up):
            return candidate
    return "X"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--mesh", default=None)
    parser.add_argument("--armature", default=None)
    parser.add_argument("--chain", default=None,
                        help="comma-separated bone names, root to head")
    parser.add_argument("--axis", default=None, help="depth axis: X, Y or Z")
    parser.add_argument("--side-axis", default=None, help="left/right axis: X, Y or Z")
    parser.add_argument("--up-axis", default=None, help="height axis: X, Y or Z")
    parser.add_argument("--side-window", type=float, default=None,
                        help="exclude vertices outside +/- this side coordinate")
    parser.add_argument("--skip-materials", default="",
                        help="comma-separated material names to exclude")
    parser.add_argument("--min-height", type=float, default=None,
                        help="ignore bands below this height")
    parser.add_argument("--band", type=float, default=0.1,
                        help="height band size in scene units (default 0.1)")
    parser.add_argument("--min-verts", type=int, default=40)
    parser.add_argument("--json-out", default=None)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    config = load_json(args.config)

    mesh_name = args.mesh or cfg(config, "source.mesh_object")
    arm_name = args.armature or cfg(config, "source.armature_object")
    depth_axis = (args.axis or cfg(config, "source.depth_axis") or "Y").upper()
    up_axis = (args.up_axis or cfg(config, "source.up_axis") or "Z").upper()
    side_axis = (args.side_axis or cfg(config, "source.side_axis")
                 or side_axis_for(depth_axis, up_axis)).upper()
    if args.band <= 0:
        raise SystemExit("--band must be positive")

    if depth_axis == up_axis:
        raise SystemExit("depth axis and up axis must differ")

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    bpy.context.view_layer.update()

    if not mesh_name:
        raise SystemExit("no mesh name; pass --mesh or set source.mesh_object")
    if not arm_name:
        raise SystemExit("no armature name; pass --armature or set source.armature_object")

    obj = bpy.data.objects.get(mesh_name)
    arm = bpy.data.objects.get(arm_name)
    if obj is None or obj.type != "MESH":
        raise SystemExit(f"mesh not found: {mesh_name}")
    if arm is None or arm.type != "ARMATURE":
        raise SystemExit(f"armature not found: {arm_name}")

    mw = obj.matrix_world
    aw = arm.matrix_world
    di = axis_index(depth_axis)
    ui = axis_index(up_axis)
    si = axis_index(side_axis)

    mats = [slot.material.name if slot.material else "<none>" for slot in obj.material_slots]
    vmat: dict[int, int] = {}
    for poly in obj.data.polygons:
        for vi in poly.vertices:
            vmat.setdefault(vi, poly.material_index)

    chain_names = []
    if args.chain:
        chain_names = [name.strip() for name in args.chain.split(",") if name.strip()]
    else:
        configured = cfg(config, "hero.skeleton.spine_chain") or []
        chain_names = [name for name in configured if name in arm.data.bones]
    if len(chain_names) < 2:
        # Fallback: common spine/neck/head names, then any bone containing a
        # spine-like token. Use --chain when the hero uses different names.
        preferred = ["pelvis", "spine_0", "spine_1", "spine_2", "spine_3", "neck_0", "head"]
        chain_names = [name for name in preferred if name in arm.data.bones]
    if len(chain_names) < 2:
        tokens = ("spine", "neck", "head", "pelvis", "chest", "torso")
        chain_names = [b.name for b in arm.data.bones if any(t in b.name.lower() for t in tokens)]
    if len(chain_names) < 2:
        raise SystemExit("could not find a spine chain; pass --chain or set hero.skeleton.spine_chain")

    chain = []
    for name in chain_names:
        bone = arm.data.bones.get(name)
        if bone is None:
            print(f"warning: chain bone not found: {name}")
            continue
        head = aw @ bone.head_local
        chain.append((name, head[ui], head[di]))
    chain.sort(key=lambda item: item[1])
    if len(chain) < 2:
        raise SystemExit("fewer than two chain bones resolved")

    def chain_depth(height: float) -> float:
        if height <= chain[0][1]:
            return chain[0][2]
        if height >= chain[-1][1]:
            return chain[-1][2]
        for (_, h0, d0), (_, h1, d1) in zip(chain, chain[1:]):
            if h0 <= height <= h1:
                t = (height - h0) / max(h1 - h0, 1e-9)
                return d0 + (d1 - d0) * t
        return chain[-1][2]

    skip = {name.strip() for name in args.skip_materials.split(",") if name.strip()}
    side_window = args.side_window
    if side_window is None:
        # Default to a narrow central window based on the mesh's side extent.
        side_values = [(mw @ v.co)[si] for v in obj.data.vertices]
        span = max(side_values) - min(side_values) if side_values else 0.0
        side_window = span * 0.15

    min_height = args.min_height
    if min_height is None:
        min_height = -1e30

    bands: dict[float, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for i, vertex in enumerate(obj.data.vertices):
        world = mw @ vertex.co
        if abs(world[si]) > side_window:
            continue
        if world[ui] < min_height:
            continue
        material_index = vmat.get(i)
        if material_index is None:
            continue
        material = mats[material_index] if material_index < len(mats) else "?"
        if material in skip:
            continue
        band = round(world[ui] / args.band) * args.band
        bands[band][material].append(world[di])

    rows = []
    print("height   material              n     depth[min..max]      median   chain     delta")
    for band in sorted(bands):
        chain_value = chain_depth(band + args.band * 0.5)
        for material in sorted(bands[band]):
            values = sorted(bands[band][material])
            if len(values) < args.min_verts:
                continue
            median = values[len(values) // 2]
            row = {
                "height": round(band, 6),
                "material": material,
                "count": len(values),
                "depth_min": round(values[0], 6),
                "depth_max": round(values[-1], 6),
                "depth_median": round(median, 6),
                "chain_depth": round(chain_value, 6),
                "delta": round(median - chain_value, 6),
            }
            rows.append(row)
            print("%6.2f   %-20s %5d  [%7.3f .. %7.3f]  %7.3f  %7.3f  %+8.3f" % (
                band, material, len(values), values[0], values[-1], median, chain_value, median - chain_value))

    report = {
        "blend": str(Path(args.blend).resolve()),
        "mesh": mesh_name,
        "armature": arm_name,
        "axes": {"depth": depth_axis, "up": up_axis, "side": side_axis},
        "side_window": side_window,
        "band": args.band,
        "chain": [item[0] for item in chain],
        "rows": rows,
    }

    out = args.json_out or (str(Path(args.blend).with_suffix("")) + ".alignment.json")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
