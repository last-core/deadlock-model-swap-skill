"""Measure a stock/reference Blender scene for project.json.

Run inside Blender:

    blender -b -P measure_stock.py -- \
        --blend stock_reference.blend \
        --out stock_measurements.json \
        [--mesh NAME] [--armature NAME]

It records mesh bounds, vertex/triangle counts, materials, collections, and
armature bone rest data. It does not modify the scene.

The stock skeleton dump is what `deadlock-validate` compares against; keep the
JSON with the project.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:  # pragma: no cover - only runs inside Blender
    raise SystemExit("This script must be run with Blender's Python") from exc


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mesh", default=None, help="measure only this mesh")
    parser.add_argument("--armature", default=None, help="measure only this armature")
    parser.add_argument("--skeleton-out", default=None,
                        help="also write a compact stock_skeleton.json")
    return parser.parse_args(argv)


def world_bounds(obj) -> dict:
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not points:
        return {"lo": [0.0, 0.0, 0.0], "hi": [0.0, 0.0, 0.0], "size": [0.0, 0.0, 0.0]}
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return {
        "lo": [round(v, 6) for v in lo],
        "hi": [round(v, 6) for v in hi],
        "size": [round(hi[i] - lo[i], 6) for i in range(3)],
    }


def measure_mesh(obj) -> dict:
    me = obj.data
    tris = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
    materials = []
    for slot in obj.material_slots:
        materials.append(slot.material.name if slot.material else None)
    groups = [g.name for g in obj.vertex_groups]
    return {
        "name": obj.name,
        "data_name": me.name,
        "type": obj.type,
        "parent": obj.parent.name if obj.parent else None,
        "collections": [c.name for c in obj.users_collection],
        "matrix_world": [[round(v, 8) for v in row] for row in obj.matrix_world],
        "verts": len(me.vertices),
        "polys": len(me.polygons),
        "tris": tris,
        "bounds_world": world_bounds(obj),
        "materials": materials,
        "vertex_groups": groups,
        "shape_keys": [k.name for k in me.shape_keys.key_blocks] if me.shape_keys else [],
    }


def measure_armature(arm) -> dict:
    bones = []
    for bone in arm.data.bones:
        bones.append({
            "name": bone.name,
            "parent": bone.parent.name if bone.parent else None,
            "head_local": [round(v, 8) for v in bone.head_local],
            "tail_local": [round(v, 8) for v in bone.tail_local],
            "matrix_local": [[round(v, 8) for v in row] for row in bone.matrix_local],
            "use_deform": bone.use_deform,
        })
    return {
        "name": arm.name,
        "data_name": arm.data.name,
        "bone_count": len(bones),
        "bones": bones,
        "matrix_world": [[round(v, 8) for v in row] for row in arm.matrix_world],
    }


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.blend)
    bpy.context.view_layer.update()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]

    if args.mesh:
        meshes = [o for o in meshes if o.name == args.mesh]
    if args.armature:
        armatures = [o for o in armatures if o.name == args.armature]

    if not meshes:
        raise SystemExit("no mesh objects found (or the --mesh name did not match)")

    data = {
        "blend": str(Path(args.blend).resolve()),
        "scene": {
            "unit_system": bpy.context.scene.unit_settings.system,
            "unit_scale": bpy.context.scene.unit_settings.scale_length,
        },
        "meshes": [measure_mesh(o) for o in meshes],
        "armatures": [measure_armature(o) for o in armatures],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    for mesh in data["meshes"]:
        print("%-24s %6d verts %6d tris  bounds %s" % (
            mesh["name"], mesh["verts"], mesh["tris"], mesh["bounds_world"]["size"]))
    for arm in data["armatures"]:
        print("%-24s %6d bones" % (arm["name"], arm["bone_count"]))

    if args.skeleton_out:
        skeleton_path = Path(args.skeleton_out)
        skeleton_path.parent.mkdir(parents=True, exist_ok=True)
        with open(skeleton_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"armatures": data["armatures"]}, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", skeleton_path)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
