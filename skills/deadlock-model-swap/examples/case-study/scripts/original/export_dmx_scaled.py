import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
BLEND, OUT_DMX, OBJ = argv[0], argv[1], argv[2]
SCALE = float(argv[3]) if len(argv) > 3 else 39.37
COLLECTION = argv[4] if len(argv) > 4 else "werewolf_model"

bpy.ops.wm.open_mainfile(filepath=BLEND)

import addon_utils

addon_utils.enable("io_scene_valvesource2", default_set=False, persistent=True)

target = bpy.data.objects[OBJ]
arm = None
for m in target.modifiers:
    if m.type == "ARMATURE" and m.object:
        arm = m.object
        break
objs = [target] + ([arm] if arm else [])

# unparent so the scale is not applied twice through the parent matrix
bpy.ops.object.select_all(action="DESELECT")
target.select_set(True)
bpy.context.view_layer.objects.active = target
if target.parent:
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = arm if arm else target
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

for o in objs:
    o.scale = (SCALE, SCALE, SCALE)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

dg = bpy.context.evaluated_depsgraph_get()
ev = target.evaluated_get(dg)
me = ev.to_mesh()
zs = [(ev.matrix_world @ v.co).z for v in me.vertices]
print("mesh z range: %.2f .. %.2f" % (min(zs), max(zs)))
ev.to_mesh_clear()

scene = bpy.context.scene
vs = scene.vs
vs.export_path = os.path.dirname(OUT_DMX).replace("\\", "/")
vs.dmx_format = "22_modeldoc"
vs.dmx_encoding = "9"
vs.export_format = "DMX"
print("export_path", vs.export_path, "format", vs.dmx_format, vs.dmx_encoding, vs.export_format)

items = scene.vs.export_list
for it in items:
    print("export item:", it.name)

# Make sure the target collection is the exported one
coll = bpy.data.collections.get(COLLECTION)
print("collection:", COLLECTION, "found:", bool(coll))
bpy.ops.export_scene.smd(export_scene=False, collection=COLLECTION)
print("done")
