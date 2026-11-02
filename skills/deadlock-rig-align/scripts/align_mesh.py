"""Translate mesh vertices onto the skeleton without moving any bone.

Run inside Blender:

    blender -b -P align_mesh.py -- \
        --config project.json --blend aligned.blend --out aligned_fixed.blend \
        [--mesh NAME] [--armature NAME] \
        [--compact-groups eye_0_L,eye_0_R,hand_L,hand_R] \
        [--axes depth|all|X,Y,Z] [--override DX DY DZ] [--apply]

Default is a dry run: it computes and prints the offset but does not modify or
save anything. Add --apply to shift the vertices and save --out.

The offset is computed in world space and converted into the mesh object's local
space before it is added to the vertices. Shape-key blocks are shifted by the
same local offset.
"""
from __future__ import annotations

import argparse
import json
import sys
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


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mesh", default=None)
    parser.add_argument("--armature", default=None)
    parser.add_argument("--compact-groups", default=None,
                        help="comma-separated source group names")
    parser.add_argument("--axes", default=None,
                        help="depth (default), all, or a comma list of X,Y,Z")
    parser.add_argument("--override", nargs=3, type=float, default=None,
                        metavar=("DX", "DY", "DZ"))
    parser.add_argument("--apply", action="store_true",
                        help="shift vertices and save --out")
    parser.add_argument("--max-samples", type=int, default=0,
                        help="limit vertices per group for speed; 0 = all")
    parser.add_argument("--json-out", default=None)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    config = load_json(args.config)

    mesh_name = args.mesh or cfg(config, "source.mesh_object")
    arm_name = args.armature or cfg(config, "source.armature_object")
    if not mesh_name or not arm_name:
        raise SystemExit("mesh/armature names missing; pass --mesh/--armature or set source.*")

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    bpy.context.view_layer.update()

    obj = bpy.data.objects.get(mesh_name)
    arm = bpy.data.objects.get(arm_name)
    if obj is None or obj.type != "MESH":
        raise SystemExit(f"mesh not found: {mesh_name}")
    if arm is None or arm.type != "ARMATURE":
        raise SystemExit(f"armature not found: {arm_name}")

    mw = obj.matrix_world
    aw = arm.matrix_world

    if (abs(mw.translation.length) > 1e-6
            or any(abs(s - 1.0) > 1e-6 for s in mw.to_scale())):
        print("WARNING mesh object has a non-identity transform:",
              [round(v, 4) for v in mw.translation],
              [round(v, 4) for v in mw.to_scale()])

    group_names = []
    if args.compact_groups:
        group_names = [name.strip() for name in args.compact_groups.split(",") if name.strip()]
    else:
        configured = cfg(config, "source.compact_groups") or []
        group_names = [name for name in configured if name in obj.vertex_groups]
    if not group_names:
        raise SystemExit(
            "no compact groups; pass --compact-groups or set source.compact_groups "
            "(use small rigid features such as eyes, teeth, hands, ankles)"
        )

    group_index = {g.name: g.index for g in obj.vertex_groups}
    wanted = {group_index[name]: name for name in group_names if name in group_index}
    if not wanted:
        raise SystemExit("none of the compact groups exist on the mesh")

    sums: dict[int, list] = {}
    for vertex in obj.data.vertices:
        best = None
        for group in vertex.groups:
            if best is None or group.weight > best[1]:
                best = (group.group, group.weight)
        if not best or best[0] not in wanted:
            continue
        item = sums.setdefault(best[0], [0, Vector((0.0, 0.0, 0.0))])
        item[0] += 1
        item[1] += mw @ vertex.co

    print("== compact-feature offsets (centroid - bone head) ==")
    offsets = []
    for group_index_value, name in wanted.items():
        if group_index_value not in sums:
            continue
        count, total = sums[group_index_value]
        if count < 10:
            continue
        centroid = total / count
        bone = arm.data.bones.get(name)
        if bone is None:
            print(f"  {name:24s} no matching bone; skipped")
            continue
        head = aw @ bone.head_local
        delta = centroid - head
        offsets.append((name, delta, count))
        print("  %-24s n=%-5d offset (%7.3f %7.3f %7.3f)" % (
            name, count, delta.x, delta.y, delta.z))

    if not offsets:
        raise SystemExit("no usable compact-feature offsets; check the group names and bone names")

    axes_mode = (args.axes or cfg(config, "source.align_axes") or "depth").lower()
    if axes_mode == "depth":
        depth_axis = (cfg(config, "source.depth_axis") or "Y").upper()
        axes = [axis_index(depth_axis)]
    elif axes_mode == "all":
        axes = [0, 1, 2]
    else:
        axes = [axis_index(part.strip()) for part in axes_mode.split(",") if part.strip()]

    medians = {}
    for axis in axes:
        values = sorted(delta[axis] for _, delta, _ in offsets)
        medians[axis] = values[len(values) // 2]
    # offset = centroid - bone, so the correction is minus the median.
    world_shift = Vector((0.0, 0.0, 0.0))
    for axis, value in medians.items():
        world_shift[axis] = -value

    if args.override:
        world_shift = Vector(args.override)
        print("using override shift", [round(v, 4) for v in world_shift])
    else:
        print("median correction (world):", [round(v, 5) for v in world_shift])
        print("axes used:", [("XYZ"[i]) for i in axes])

    # Convert the world-space vector into the mesh object's local space.
    local_shift = mw.inverted().to_3x3() @ world_shift
    print("local correction:", [round(v, 5) for v in local_shift])

    def bounds() -> tuple[Vector, Vector]:
        points = [mw @ v.co for v in obj.data.vertices]
        lo = Vector((min(p[i] for p in points) for i in range(3)))
        hi = Vector((max(p[i] for p in points) for i in range(3)))
        return lo, hi

    lo_before, hi_before = bounds()
    print("bounds before lo", [round(v, 3) for v in lo_before],
          "hi", [round(v, 3) for v in hi_before])

    if not args.apply:
        print("dry run: no vertices changed; re-run with --apply to save", args.out)
        return 0

    count = 0
    for vertex in obj.data.vertices:
        vertex.co += local_shift
        count += 1
        if args.max_samples and count >= args.max_samples:
            break

    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            for vertex in key.data:
                vertex.co += local_shift

    obj.data.update()
    lo_after, hi_after = bounds()
    print("bounds after  lo", [round(v, 3) for v in lo_after],
          "hi", [round(v, 3) for v in hi_after])
    print("shifted", count, "vertices")

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    report = {
        "blend": str(Path(args.blend).resolve()),
        "out": str(Path(args.out).resolve()),
        "mesh": mesh_name,
        "armature": arm_name,
        "compact_groups": [name for name, _, _ in offsets],
        "world_shift": [round(v, 8) for v in world_shift],
        "local_shift": [round(v, 8) for v in local_shift],
        "bounds_before": {"lo": [round(v, 6) for v in lo_before], "hi": [round(v, 6) for v in hi_before]},
        "bounds_after": {"lo": [round(v, 6) for v in lo_after], "hi": [round(v, 6) for v in hi_after]},
    }
    out = args.json_out or (str(Path(args.out).with_suffix("")) + ".align.json")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("wrote", args.out, "and", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
