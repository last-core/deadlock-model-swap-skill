"""Fit a source weapon mesh into a stock weapon's bone-local frame.

Run inside Blender:

    blender -b -P fit_weapon.py -- \
        --config project.json \
        --rifle-blend stock_weapon.blend \
        --gun-blend source_weapon.blend \
        --out fitted_weapon.blend \
        [--weapon-bone weapon] [--stock-mesh NAME] [--source-object NAME] \
        [--scale 1.0] [--material-map material_map.json] [--dry-run]

The stock bbox is measured in the weapon bone's local frame. The fitted points
are mapped back through the bone:

    world = armature_world @ bone_matrix @ local

This avoids the two classic bugs: bone-space coordinates written as world
coordinates (weapon pitched/inverted), and the source barrel pointing the other
way (weapon backwards). The flip is about the bone-local up axis, not world
vertical.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Matrix, Vector
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


def axis_vector(name: str) -> Vector:
    name = (name or "").upper().strip()
    sign = -1.0 if name.startswith("-") else 1.0
    name = name.lstrip("+-")
    if name not in ("X", "Y", "Z"):
        raise ValueError(f"axis must be X, Y or Z, got {name!r}")
    vec = Vector((0.0, 0.0, 0.0))
    vec["XYZ".index(name)] = sign
    return vec


def bbox(points: list[Vector]) -> tuple[Vector, Vector, Vector, Vector]:
    if not points:
        raise SystemExit("empty point set")
    lo = Vector((min(p[i] for p in points) for i in range(3)))
    hi = Vector((max(p[i] for p in points) for i in range(3)))
    return lo, hi, (lo + hi) / 2.0, hi - lo


def longest_axis(size: Vector) -> str:
    index = max(range(3), key=lambda i: size[i])
    return "XYZ"[index]


def align_axis(vec: Vector, target: Vector) -> Matrix:
    a = vec.normalized()
    b = target.normalized()
    if a.length < 1e-9 or b.length < 1e-9:
        return Matrix.Identity(4)
    return a.rotation_difference(b).to_matrix().to_4x4()


def signed_angle(a: Vector, b: Vector, axis: Vector) -> float:
    """Signed angle from a to b around axis (all projected onto axis plane)."""
    axis = axis.normalized()
    a = (a - axis * a.dot(axis))
    b = (b - axis * b.dot(axis))
    if a.length < 1e-9 or b.length < 1e-9:
        return 0.0
    a.normalize()
    b.normalize()
    return math.atan2(a.cross(b).dot(axis), a.dot(b))


def tex_of(material) -> str:
    if not material or not material.use_nodes:
        return "<none>"
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            return Path(node.image.filepath or node.image.name).name
    return "<none>"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--rifle-blend", required=True)
    parser.add_argument("--gun-blend", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--weapon-bone", default=None)
    parser.add_argument("--stock-mesh", default=None)
    parser.add_argument("--source-object", default=None)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--stock-long-axis", default=None)
    parser.add_argument("--source-long-axis", default=None)
    parser.add_argument("--stock-up-axis", default=None)
    parser.add_argument("--source-up-axis", default=None)
    parser.add_argument("--stock-muzzle-axis", default=None)
    parser.add_argument("--source-muzzle-axis", default=None)
    parser.add_argument("--material-map", default=None,
                        help="JSON {texture_or_material: output_material}")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    weapon_bone = args.weapon_bone or cfg(config, "stock.weapon.bone")
    stock_mesh_name = args.stock_mesh or cfg(config, "stock.weapon.mesh_name")
    if not weapon_bone:
        raise SystemExit("weapon bone missing; pass --weapon-bone or set stock.weapon.bone")

    bpy.ops.wm.open_mainfile(filepath=args.rifle_blend)
    bpy.context.view_layer.update()

    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        raise SystemExit("no armature in the rifle blend")
    arm = armatures[0]
    bone = arm.data.bones.get(weapon_bone)
    if bone is None:
        raise SystemExit(f"weapon bone not found: {weapon_bone}")

    stock = None
    if stock_mesh_name:
        stock = bpy.data.objects.get(stock_mesh_name)
    if stock is None or stock.type != "MESH":
        candidates = [o for o in bpy.data.objects if o.type == "MESH"]
        if not candidates:
            raise SystemExit("no stock weapon mesh found")
        stock = max(candidates, key=lambda o: len(o.data.vertices))
        print("WARNING: stock mesh name not found; using largest mesh:", stock.name)

    bone_matrix = arm.matrix_world @ bone.matrix_local
    inv_bone = bone_matrix.inverted()

    stock_pts = [inv_bone @ (stock.matrix_world @ v.co) for v in stock.data.vertices]
    s_lo, s_hi, s_center, s_size = bbox(stock_pts)
    print("stock local bbox lo=%s hi=%s centre=%s size=%s" % (
        [round(v, 4) for v in s_lo], [round(v, 4) for v in s_hi],
        [round(v, 4) for v in s_center], [round(v, 4) for v in s_size]))

    # Append the source weapon.
    with bpy.data.libraries.load(args.gun_blend, link=False) as (src, dst):
        names = [n for n in src.objects if n]
        dst.objects = names
    objects = [o for o in dst.objects if o is not None]
    if args.source_object:
        gun = next((o for o in objects if o.name == args.source_object), None)
    else:
        meshes = [o for o in objects if o.type == "MESH"]
        gun = max(meshes, key=lambda o: len(o.data.vertices)) if meshes else None
    if gun is None or gun.type != "MESH":
        raise SystemExit("source weapon mesh not found")
    gun_world = gun.matrix_world.copy()
    bpy.context.scene.collection.objects.link(gun)
    # The source file often brings its own armature/empties. Remove them; this
    # script binds the mesh to the stock weapon bone. Preserve the mesh's world
    # transform while clearing the parent.
    for obj in list(objects):
        if obj is not gun and obj.type in ("ARMATURE", "EMPTY"):
            bpy.data.objects.remove(obj, do_unlink=True)
    gun.parent = None
    gun.matrix_world = gun_world
    print("source mesh:", gun.name, len(gun.data.vertices), "verts")

    src_pts = [inv_bone @ (gun.matrix_world @ v.co) for v in gun.data.vertices]
    g_lo, g_hi, g_center, g_size = bbox(src_pts)
    print("source local bbox lo=%s hi=%s centre=%s size=%s" % (
        [round(v, 4) for v in g_lo], [round(v, 4) for v in g_hi],
        [round(v, 4) for v in g_center], [round(v, 4) for v in g_size]))

    stock_long = args.stock_long_axis or cfg(config, "stock.weapon.long_axis") or longest_axis(s_size)
    source_long = args.source_long_axis or cfg(config, "source.long_axis") or longest_axis(g_size)
    # A source/source-long axis may have a sign. If only a bare axis is given,
    # use the positive direction.
    # Source axes are expressed in the source object's local space. Transform
    # them into the weapon bone's frame before fitting.
    gun_linear = inv_bone.to_3x3() @ gun.matrix_world.to_3x3()
    src_long_vec = (gun_linear @ axis_vector(source_long)).normalized()
    stock_long_vec = axis_vector(stock_long)

    stock_up = args.stock_up_axis or cfg(config, "stock.weapon.up_axis")
    source_up = args.source_up_axis or cfg(config, "source.up_axis")
    if not stock_up:
        # Pick the stock bbox axis with the smallest extent as up if it is not
        # the long axis; otherwise use Z.
        candidates = [axis for axis in ("X", "Y", "Z") if axis != stock_long.lstrip("+-")]
        stock_up = min(candidates, key=lambda a: s_size["XYZ".index(a)]) if candidates else "Z"
    if not source_up:
        candidates = [axis for axis in ("X", "Y", "Z") if axis != source_long.lstrip("+-")]
        source_up = min(candidates, key=lambda a: g_size["XYZ".index(a)]) if candidates else "Z"

    # 1) Align the long axis.
    R1 = align_axis(src_long_vec, stock_long_vec)

    # Work around the source centre: rotate every point around the source centre.
    pts = [R1 @ (p - g_center) for p in src_pts]
    lo1, hi1, c1, size1 = bbox(pts)

    # 2) Align the up axis around the stock long axis.
    up_src = (gun_linear @ axis_vector(source_up)).normalized()
    up_stock = axis_vector(stock_up)
    # Transform the source up vector through R1, then project/align.
    up_src_world = (R1.to_3x3() @ up_src)
    long_axis = stock_long_vec.normalized()
    angle = signed_angle(up_src_world, up_stock, long_axis)
    R2 = Matrix.Rotation(angle, 4, long_axis)
    pts = [R2 @ p for p in pts]
    lo2, hi2, c2, size2 = bbox(pts)

    # 3) Muzzle direction: compare the source and stock muzzle signs along the
    # long axis. A 180-degree flip about the bone-local up axis reverses the
    # long axis while keeping the weapon upright.
    stock_muzzle = args.stock_muzzle_axis or cfg(config, "stock.weapon.muzzle_axis") or stock_long
    source_muzzle = args.source_muzzle_axis or cfg(config, "source.muzzle_axis") or source_long
    stock_muzzle_vec = axis_vector(stock_muzzle)
    source_muzzle_vec = R1.to_3x3() @ (gun_linear @ axis_vector(source_muzzle)).normalized()
    # The component of the muzzle along the stock long axis decides the sign.
    sign = stock_muzzle_vec.normalized().dot(stock_long_vec.normalized())
    src_sign = source_muzzle_vec.normalized().dot(stock_long_vec.normalized())
    flipped = False
    if sign * src_sign < 0:
        flip_axis = axis_vector(stock_up).normalized()
        R3 = Matrix.Rotation(math.pi, 4, flip_axis)
        pts = [R3 @ p for p in pts]
        lo3, hi3, c3, size3 = bbox(pts)
        flipped = True
    else:
        lo3, hi3, c3, size3 = lo2, hi2, c2, size2

    # 4) Scale by the stock/source long-axis extent, unless overridden.
    source_extent = max(size3)
    stock_extent = max(s_size)
    scale = args.scale if args.scale is not None else (stock_extent / max(source_extent, 1e-9))
    print("scale:", round(scale, 6), " (stock extent %.4f / source extent %.4f)" % (
        stock_extent, source_extent))

    # 5) Centre on the stock centre.
    fitted = [p * scale + s_center for p in pts]
    f_lo, f_hi, f_center, f_size = bbox(fitted)
    print("fitted local bbox lo=%s hi=%s centre=%s size=%s" % (
        [round(v, 4) for v in f_lo], [round(v, 4) for v in f_hi],
        [round(v, 4) for v in f_center], [round(v, 4) for v in f_size]))
    print("centre delta:", [round(f_center[i] - s_center[i], 4) for i in range(3)])

    if args.dry_run:
        print("dry run: no scene changes saved")
        return 0

    # Bake the fitted local coordinates back into world coordinates.
    gun.matrix_world = Matrix.Identity(4)
    me = gun.data
    for vertex, local in zip(me.vertices, fitted):
        vertex.co = bone_matrix @ local
    me.update()

    # Materials: map by texture or material name; fail on unknown.
    material_map = load_json(args.material_map) if args.material_map else {}
    new_materials: list[str] = []
    mapping: dict[int, str] = {}
    for i, slot in enumerate(gun.material_slots):
        mat = slot.material
        key = tex_of(mat) if mat else "<none>"
        if key not in material_map and (not mat or mat.name not in material_map):
            raise SystemExit(f"no material mapping for slot {i} ({key}); add it to --material-map")
        target = material_map.get(key, material_map.get(mat.name if mat else "", None))
        if target is None:
            raise SystemExit(f"material mapping for {key} is null; remove the slot or map it")
        mapping[i] = target
        if target not in new_materials:
            new_materials.append(target)
    if not new_materials:
        raise SystemExit("source weapon has no mapped materials; add a material map")

    poly_new = [mapping.get(p.material_index, 0) for p in me.polygons]
    me.materials.clear()
    for name in new_materials:
        material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        me.materials.append(material)
    for poly, index in zip(me.polygons, poly_new):
        poly.material_index = index
    me.update()

    # Rigid bind to the weapon bone.
    for group in list(gun.vertex_groups):
        gun.vertex_groups.remove(group)
    group = gun.vertex_groups.new(name=weapon_bone)
    group.add(list(range(len(me.vertices))), 1.0, "REPLACE")

    gun.parent = arm
    gun.matrix_parent_inverse = arm.matrix_world.inverted()
    for modifier in list(gun.modifiers):
        gun.modifiers.remove(modifier)
    modifier = gun.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = arm

    # Remove other weapon meshes so the ModelDoc has one weapon render mesh.
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj is not gun and stock_mesh_name and obj.name == stock_mesh_name:
            bpy.data.objects.remove(obj, do_unlink=True)

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    print("saved", args.out)
    print("flipped 180 about bone-local up:", flipped)
    print("materials:", [slot.material.name for slot in gun.material_slots])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
