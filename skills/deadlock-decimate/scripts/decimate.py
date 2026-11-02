"""Decimate a destination mesh to a triangle budget, protecting face/rims.

Run inside Blender:

    blender -b -P decimate.py -- \
        --config project.json \
        --blend aligned.blend --out decimated.blend \
        [--mesh NAME] [--armature NAME] \
        [--ratio 0.70] [--factor 1.0] \
        [--protect-materials mat_a,mat_b] \
        [--face-materials mat_face,mat_eyes] \
        [--material-map material_map.json] \
        [--drop-materials mat_decal] \
        [--backup aligned_source.blend] \
        [--json-out decimate_report.json]

`material_map.json` is {texture_or_material_name: output_material_or_null}.
If it is omitted, the script decimates but does not merge material slots.

Important: Blender's Decimate vertex group selects the vertices that MAY
collapse. A protect mask must be inverted (`invert_vertex_group = True`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

try:
    import bpy
    import bmesh
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


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mesh", default=None)
    parser.add_argument("--armature", default=None)
    parser.add_argument("--ratio", type=float, default=None)
    parser.add_argument("--factor", type=float, default=1.0)
    parser.add_argument("--protect-materials", default="",
                        help="comma-separated garment/material names for boundary rims")
    parser.add_argument("--face-materials", default="",
                        help="comma-separated face/eye/mouth material names")
    parser.add_argument("--material-map", default=None,
                        help="JSON {texture_or_material: output_material_or_null}")
    parser.add_argument("--drop-materials", default="",
                        help="comma-separated materials to delete before decimating")
    parser.add_argument("--backup", default=None,
                        help="copy the input blend here before decimating (full-res source)")
    parser.add_argument("--weld-check", type=float, default=0.0,
                        help="weld a copy by this distance before counting boundary edges")
    parser.add_argument("--json-out", default=None)
    return parser.parse_args(argv)


def tex_of(material) -> str:
    if not material or not material.use_nodes:
        return "<none>"
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            return os.path.basename(node.image.filepath or node.image.name)
    return "<none>"


def count_boundary_edges(mesh, weld_dist: float = 0.0) -> int:
    if weld_dist <= 0:
        counts = Counter()
        for poly in mesh.polygons:
            verts = list(poly.vertices)
            for i in range(len(verts)):
                a, b = verts[i], verts[(i + 1) % len(verts)]
                counts[(a, b) if a < b else (b, a)] += 1
        return sum(1 for value in counts.values() if value == 1)

    copy = mesh.copy()
    bm = bmesh.new()
    bm.from_mesh(copy)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld_dist)
    bm.edges.ensure_lookup_table()
    boundary = sum(1 for edge in bm.edges if edge.is_boundary)
    bm.free()
    bpy.data.meshes.remove(copy)
    return boundary


def find_object(name: str | None, kind: str, label: str):
    if name:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != kind:
            raise SystemExit(f"{label} not found: {name}")
        return obj
    candidates = [o for o in bpy.data.objects if o.type == kind]
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit(f"multiple {label}s; pass --{label} or set it in project.json")


def main() -> int:
    args = parse_args()
    config = load_json(args.config)

    if args.backup:
        backup = Path(args.backup)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.blend, backup)
        print("backup:", backup)

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    bpy.context.view_layer.update()

    mesh_name = args.mesh or cfg(config, "source.mesh_object")
    arm_name = args.armature or cfg(config, "source.armature_object")
    obj = find_object(mesh_name, "MESH", "mesh")
    arm = find_object(arm_name, "ARMATURE", "armature") if arm_name else None

    me = obj.data
    old_materials = [slot.material for slot in obj.material_slots]
    old_tex = [tex_of(mat) for mat in old_materials]
    print("mesh:", obj.name, "verts:", len(me.vertices), "polys:", len(me.polygons))
    if arm:
        print("armature:", arm.name, "bones:", len(arm.data.bones))

    # ---- drop decal/FX faces before decimating --------------------------------
    drop = {name.strip() for name in args.drop_materials.split(",") if name.strip()}
    if drop:
        drop_indices = {
            i for i, (mat, tex) in enumerate(zip(old_materials, old_tex))
            if (mat and mat.name in drop) or tex in drop
        }
        if drop_indices:
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            doomed = [face for face in bm.faces if face.material_index in drop_indices]
            print("dropping", len(doomed), "faces from", len(drop_indices), "material(s)")
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
            bm.to_mesh(me)
            me.update()
            bm.free()

    # ---- protection mask ------------------------------------------------------
    face_mats = {name.strip() for name in args.face_materials.split(",") if name.strip()}
    protect_mats = {name.strip() for name in args.protect_materials.split(",") if name.strip()}
    face_indices = {
        i for i, (mat, tex) in enumerate(zip(old_materials, old_tex))
        if (mat and mat.name in face_mats) or tex in face_mats
    }
    protect_indices = {
        i for i, (mat, tex) in enumerate(zip(old_materials, old_tex))
        if (mat and mat.name in protect_mats) or tex in protect_mats
    }

    vmat: dict[int, int] = {}
    for poly in me.polygons:
        for vi in poly.vertices:
            vmat.setdefault(vi, poly.material_index)

    protect: set[int] = set()
    if face_indices:
        protect.update(vi for vi, mi in vmat.items() if mi in face_indices)

    boundary_count_before = count_boundary_edges(me)
    if protect_indices:
        counts = Counter()
        for poly in me.polygons:
            verts = list(poly.vertices)
            for i in range(len(verts)):
                a, b = verts[i], verts[(i + 1) % len(verts)]
                counts[(a, b) if a < b else (b, a)] += 1
        for (a, b), value in counts.items():
            if value != 1:
                continue
            mi = vmat.get(a, -1)
            if mi not in protect_indices:
                continue
            protect.add(a)
            protect.add(b)

    if protect:
        group = obj.vertex_groups.get("protect_mask") or obj.vertex_groups.new(name="protect_mask")
        group.add(list(protect), 1.0, "REPLACE")
    else:
        group = None

    print("boundary edges before:", boundary_count_before)
    print("protect: %d verts (face %d, rim materials %d)" % (
        len(protect), len(face_indices), len(protect_indices)))

    # ---- decimate -------------------------------------------------------------
    tris_before = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
    ratio = args.ratio
    if ratio is None:
        budget = cfg(config, "stock.tri_budget") or 0
        ratio = (float(budget) / tris_before) if budget and tris_before else 0.7
    ratio = max(0.01, min(1.0, float(ratio)))
    print("decimate ratio: %.4f" % ratio)

    # Temporarily disable armature deform so decimate applies to the rest mesh.
    armature_state = []
    for modifier in obj.modifiers:
        if modifier.type == "ARMATURE":
            armature_state.append((modifier, modifier.show_viewport, modifier.show_render))
            modifier.show_viewport = False
            modifier.show_render = False

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    modifier = obj.modifiers.new(name="Decimate", type="DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    if group is not None:
        modifier.vertex_group = group.name
        modifier.vertex_group_factor = args.factor
        modifier.invert_vertex_group = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    for modifier, viewport, render in armature_state:
        modifier.show_viewport = viewport
        modifier.show_render = render

    me = obj.data
    tris_after = sum(max(len(p.vertices) - 2, 0) for p in me.polygons)
    boundary_after = count_boundary_edges(me, args.weld_check)
    print("tris: %d -> %d (%.3f of source)" % (tris_before, tris_after, tris_after / max(tris_before, 1)))
    print("boundary edges after:", boundary_after,
          ("(welded by %.6f)" % args.weld_check) if args.weld_check > 0 else "")

    # ---- material merge (optional) -------------------------------------------
    material_map = load_json(args.material_map) if args.material_map else {}
    slots_wanted: list[str] = []
    remap: dict[int, int] = {}
    dropped: list[int] = []
    if material_map:
        for i, (mat, tex) in enumerate(zip(old_materials, old_tex)):
            key = tex if tex in material_map else (mat.name if mat and mat.name in material_map else None)
            if key is None:
                # Keep unmapped materials rather than silently collapsing them.
                target = mat.name if mat else f"slot_{i}"
            else:
                target = material_map[key]
            if target is None:
                dropped.append(i)
                continue
            if target not in slots_wanted:
                slots_wanted.append(target)
            remap[i] = slots_wanted.index(target)

        if dropped:
            # Remove faces whose material has no output slot before clearing the
            # slot list; otherwise their indices point at the wrong material.
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            doomed = [face for face in bm.faces if face.material_index in dropped]
            print("dropping", len(doomed), "face(s) with no output material")
            bmesh.ops.delete(bm, geom=doomed, context="FACES")
            bm.to_mesh(me)
            me.update()
            bm.free()

        poly_new = [(poly, remap.get(poly.material_index, 0)) for poly in me.polygons]

        me.materials.clear()
        for name in slots_wanted:
            material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
            me.materials.append(material)
        for poly, index in poly_new:
            poly.material_index = index
        me.update()

        if dropped:
            print("dropping", len(dropped), "material slot(s) with no output")
        print("material slots:", [(i, slot.material.name if slot.material else None)
                                  for i, slot in enumerate(obj.material_slots)])
        counts = Counter(poly.material_index for poly in me.polygons)
        for i, slot in enumerate(obj.material_slots):
            print("  %-24s %6d polys" % (slot.material.name if slot.material else "<none>",
                                          counts.get(i, 0)))

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    report = {
        "blend": str(Path(args.blend).resolve()),
        "out": str(Path(args.out).resolve()),
        "mesh": obj.name,
        "armature": arm.name if arm else None,
        "ratio": ratio,
        "tris_before": tris_before,
        "tris_after": tris_after,
        "boundary_before": boundary_count_before,
        "boundary_after": boundary_after,
        "weld_check": args.weld_check,
        "protect_verts": len(protect),
        "face_materials": sorted(face_mats),
        "protect_materials": sorted(protect_mats),
        "material_slots": [slot.material.name if slot.material else None for slot in obj.material_slots],
    }
    out = args.json_out or (str(Path(args.out).with_suffix("")) + ".decimate.json")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("wrote", args.out, "and", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
