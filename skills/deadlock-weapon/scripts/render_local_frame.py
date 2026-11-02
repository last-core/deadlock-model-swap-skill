"""Render meshes from fixed cameras for side-by-side weapon comparison.

Run inside Blender:

    blender -b -P render_local_frame.py -- \
        --blend weapon.blend --prefix compare \
        [--filter weapon] [--views sideX,sideY,top] \
        [--ortho-scale 2.0] [--origin X,Y,Z]

The camera framing is derived from the visible mesh bounds unless overridden, so
the stock and candidate renders are directly comparable. The script hides all
non-mesh objects and all meshes that do not match --filter.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Vector
except ImportError as exc:  # pragma: no cover
    raise SystemExit("This script must be run with Blender's Python") from exc


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--filter", default=None, help="substring of mesh name to render")
    parser.add_argument("--views", default="sideX,sideY,top")
    parser.add_argument("--ortho-scale", type=float, default=None)
    parser.add_argument("--origin", default=None, help="X,Y,Z; default = visible bbox centre")
    parser.add_argument("--resolution-x", type=int, default=900)
    parser.add_argument("--resolution-y", type=int, default=520)
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.blend)

    keep = []
    points = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            obj.hide_render = True
            continue
        ok = (args.filter is None) or (args.filter.lower() in obj.name.lower())
        obj.hide_render = not ok
        obj.hide_viewport = not ok
        if ok:
            keep.append(obj)
            points.extend(obj.matrix_world @ v.co for v in obj.data.vertices)

    if not keep:
        raise SystemExit("no meshes to render")
    if not points:
        raise SystemExit("visible meshes have no vertices")
    print("rendering:", [(obj.name, len(obj.data.vertices)) for obj in keep])

    if args.origin:
        origin = Vector(tuple(float(v) for v in args.origin.split(",")))
    else:
        lo = Vector((min(p[i] for p in points) for i in range(3)))
        hi = Vector((max(p[i] for p in points) for i in range(3)))
        origin = (lo + hi) / 2.0
    if args.ortho_scale is None:
        lo = Vector((min(p[i] for p in points) for i in range(3)))
        hi = Vector((max(p[i] for p in points) for i in range(3)))
        ortho_scale = max((hi - lo).length, 1e-6) * 1.2
    else:
        ortho_scale = args.ortho_scale

    scene = bpy.context.scene
    camera_data = bpy.data.cameras.new("cam")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new("cam", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = args.resolution_x
    scene.render.resolution_y = args.resolution_y
    scene.view_settings.view_transform = "Standard"

    directions = {
        "sideX": Vector((1, 0, 0)),
        "sideY": Vector((0, -1, 0)),
        "top": Vector((0, 0, 1)),
    }
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    for name in views:
        if name not in directions:
            raise SystemExit(f"unknown view {name!r}; choose {sorted(directions)}")
        direction = directions[name]
        camera.location = origin + direction * (ortho_scale * 2.0)
        camera.rotation_euler = (origin - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{args.prefix}_{name}.png"
        bpy.ops.render.render(write_still=True)
        print("wrote", scene.render.filepath)

    print("origin:", [round(v, 4) for v in origin], "ortho_scale:", round(ortho_scale, 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
