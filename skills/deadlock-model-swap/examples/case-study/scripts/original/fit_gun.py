"""Fit the Red Hood gun onto the weapon bone.

Target frame is the stock weapon's own placement in the `weapon` bone's local
space, so grip/aim alignment matches what the game already expects:

    lo=[-0.041,-0.205,-0.505] hi=[0.041,0.207,0.737]  (long axis = local Z)

The gun arrives 1.640 m long along its own +Y; it is rotated so its length maps
to local +Z, scaled to SCALE of full size, and centred on the stock centre.

blender -b -noaudio -P tools/fit_gun.py -- <rifle_blend> <gun_src.blend> <out.blend> [scale]
"""
import bpy
import math
import sys
from mathutils import Vector, Matrix

args = sys.argv[sys.argv.index("--") + 1:]
RIFLE, GUNSRC, OUT = args[0], args[1], args[2]
SCALE = float(args[3]) if len(args) > 3 else 0.85

TEX_TO_MAT = {
    "銃1.jpg": "werewolf_gun_1",
    "銃2.jpg": "werewolf_gun_2",
    "銃3.jpg": "werewolf_gun_3",
    "銃4.jpg": "werewolf_gun_4",
    "銃5.jpg": "werewolf_gun_5",
    "銀パーツ.jpg": "werewolf_metal",
    "銀パーツ2.jpg": "werewolf_metal_b",
    "服3.png": "werewolf_upper_b",
    "発光.jpg": "werewolf_emit",
    "めとか.png": None,          # FX atlas, drop
}

bpy.ops.wm.open_mainfile(filepath=RIFLE)

arm = bpy.data.objects["werewolf"]
stock = [o for o in bpy.data.objects
         if o.type == "MESH" and "primary_weapon" in o.name][0]

wb = arm.data.bones["weapon"]
mw_bone = arm.matrix_world @ wb.matrix_local
inv_bone = mw_bone.inverted()

# stock reference in the weapon bone frame
pts = [inv_bone @ (stock.matrix_world @ v.co) for v in stock.data.vertices]
slo = Vector((min(p[i] for p in pts) for i in range(3)))
shi = Vector((max(p[i] for p in pts) for i in range(3)))
scentre = (slo + shi) / 2
print("stock local bbox lo=%s hi=%s centre=%s"
      % ([round(v, 3) for v in slo], [round(v, 3) for v in shi],
         [round(v, 3) for v in scentre]))

# ---- bring in the gun mesh ----------------------------------------------
with bpy.data.libraries.load(GUNSRC, link=False) as (src, dst):
    names = [n for n in src.objects if n.endswith("_mesh")]
    print("appending:", names)
    dst.objects = names
gun = [o for o in dst.objects if o][0]
bpy.context.scene.collection.objects.link(gun)

# drop t ool objects from the appended file
for ob in list(bpy.data.objects):
    if ob is not gun and ob.type in ("ARMATURE", "EMPTY") and "ウルフスベイン" in ob.name:
        bpy.data.objects.remove(ob, do_unlink=True)

me = gun.data
print("gun verts:", len(me.vertices), "tris:",
      sum(len(p.vertices) - 2 for p in me.polygons))

# ---- materials by texture name -----------------------------------------
import os
def tex_of(mat):
    if not mat or not mat.use_nodes:
        return "<none>"
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            return os.path.basename(n.image.filepath or n.image.name)
    return "<none>"

mapping = {}
for i, slot in enumerate(gun.material_slots):
    t = tex_of(slot.material)
    mapping[i] = TEX_TO_MAT.get(t, "werewolf_gun_1")
    print("  slot %d %-10s %-22s -> %s" % (i, slot.material.name[:10], t, mapping[i]))

# ---- transform: centre, reorient, scale --------------------------------
glo = Vector((min(v.co[i] for v in me.vertices) for i in range(3)))
ghi = Vector((max(v.co[i] for v in me.vertices) for i in range(3)))
gcentre = (glo + ghi) / 2
print("gun bbox lo=%s hi=%s centre=%s size=%s"
      % ([round(v, 3) for v in glo], [round(v, 3) for v in ghi],
         [round(v, 3) for v in gcentre],
         [round(ghi[i] - glo[i], 3) for i in range(3)]))

R = Matrix.Rotation(math.radians(180), 4, "Z") @ Matrix.Rotation(math.radians(90), 4, "X")
S = Matrix.Scale(SCALE, 4)

# object transform stays identity; bake everything into vertex coords.
# IMPORTANT: scentre/slo/shi are in the WEAPON BONE's space, so the fitted
# coords must be mapped back through the bone matrix. Writing bone-space coords
# straight out as world coords drops the bone's rotation, which is what made the
# first attempt 60 deg pitched and upside down.
gun.matrix_world = Matrix.Identity(4)
for v in me.vertices:
    local = (R @ S @ (v.co - gcentre)) + scentre
    v.co = mw_bone @ local
me.update()

# The MMD gun's barrel runs along -Y in its own space, opposite to the stock
# weapon's muzzle, so the first fit came out mirrored (gun pointing backwards).
# Flip 180 deg about the WORLD vertical through the stock centre: keeps it
# upright and centred, reverses the barrel.
wpts = [stock.matrix_world @ v.co for v in stock.data.vertices]
wlo = Vector((min(p[i] for p in wpts) for i in range(3)))
whi = Vector((max(p[i] for p in wpts) for i in range(3)))
wc = (wlo + whi) / 2
FLIP = Matrix.Rotation(math.radians(180), 4, "Z")
for v in me.vertices:
    v.co = wc + (FLIP @ (v.co - wc))
me.update()

# what the stock weapon occupies in WORLD space, for comparison
print("stock WORLD bbox lo=%s hi=%s size=%s"
      % ([round(v, 3) for v in wlo], [round(v, 3) for v in whi],
         [round(whi[i] - wlo[i], 3) for i in range(3)]))

nlo = Vector((min(v.co[i] for v in me.vertices) for i in range(3)))
nhi = Vector((max(v.co[i] for v in me.vertices) for i in range(3)))
print("fitted WORLD bbox lo=%s hi=%s size=%s"
      % ([round(v, 3) for v in nlo], [round(v, 3) for v in nhi],
         [round(nhi[i] - nlo[i], 3) for i in range(3)]))
print("bbox delta vs stock:",
      [round((nlo[i] + nhi[i]) / 2 - (wlo[i] + whi[i]) / 2, 3) for i in range(3)])

# ---- materials, then rigid bind to the weapon bone ---------------------
new_mats = []
for i, slot in enumerate(gun.material_slots):
    name = mapping[i]
    if name and name not in new_mats:
        new_mats.append(name)
idx = {n: i for i, n in enumerate(new_mats)}
# resolve indices before clearing the slot list
poly_new = [idx.get(mapping.get(p.material_index), 0) for p in me.polygons]
me.materials.clear()
for name in new_mats:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    me.materials.append(m)
for p, mi in zip(me.polygons, poly_new):
    p.material_index = mi
me.update()

for g in list(gun.vertex_groups):
    gun.vertex_groups.remove(g)
vg = gun.vertex_groups.new(name="weapon")
vg.add(list(range(len(me.vertices))), 1.0, "REPLACE")

gun.name = "primary_weapon_only"
me.name = "primary_weapon_only"
gun.parent = arm
gun.matrix_parent_inverse = arm.matrix_world.inverted()
for m in list(gun.modifiers):
    gun.modifiers.remove(m)
md = gun.modifiers.new(name="Armature", type="ARMATURE")
md.object = arm

coll = bpy.data.collections.get("primary_weapon_only")
if coll is None:
    coll = bpy.data.collections.new("primary_weapon_only")
    bpy.context.scene.collection.children.link(coll)
for c in list(gun.users_collection):
    c.objects.unlink(gun)
coll.objects.link(gun)
for ob in bpy.data.objects:
    if ob.type == "MESH" and "primary_weapon" in ob.name and ob is not gun:
        bpy.data.objects.remove(ob, do_unlink=True)

print("materials:", [s.material.name for s in gun.material_slots])
print("collection:", [o.name for o in coll.objects])

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
