"""Render whatever is in a blend from a FIXED camera about the origin.

Both the stock weapon and a fitted replacement sit in the same bone-local frame
at rest, so identical cameras make the two directly comparable.

blender -b -noaudio -P tools/render_local_frame.py -- <blend> <prefix> [mesh-filter]
"""
import bpy
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
BLEND, PREFIX = args[0], args[1]
FILTER = args[2] if len(args) > 2 else None

bpy.ops.wm.open_mainfile(filepath=BLEND)

keep = []
for o in bpy.data.objects:
    if o.type != "MESH":
        o.hide_render = True
        continue
    ok = (FILTER is None) or (FILTER in o.name)
    o.hide_render = not ok
    o.hide_viewport = not ok
    if ok:
        keep.append(o)
print("rendering:", [(o.name.split("\\")[-1][:40], len(o.data.vertices)) for o in keep])

scene = bpy.context.scene
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.2          # fixed, so both renders are comparable
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "MATERIAL"
scene.display.shading.show_cavity = True
scene.render.resolution_x = 900
scene.render.resolution_y = 520
scene.view_settings.view_transform = "Standard"

ORIGIN = Vector((0.0, 0.0, 0.12))
VIEWS = {
    # name: camera direction (from origin towards camera)
    "sideX": Vector((1, 0, 0)),      # looking down -X : screen right = +Y
    "sideY": Vector((0, -1, 0)),     # looking down +Y : screen right = +X
    "top": Vector((0, 0, 1)),
}
for name, d in VIEWS.items():
    cam.location = ORIGIN + d * 3.0
    cam.rotation_euler = (ORIGIN - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = "%s_%s.png" % (PREFIX, name)
    bpy.ops.render.render(write_still=True)
print("rendered", PREFIX)
