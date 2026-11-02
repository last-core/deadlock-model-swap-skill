"""Rebuild the mesh at a higher density, protecting garment seams and the face.

Replaces the old 0.42 Decimate that tore the garment seams open (see HANDOFF
§4.8).  Runs on silver_rig_06_bound.blend, which still holds the full-res MMD
mesh (235,362 v / 263,003 tri) with all 46 MMD materials.

Material merge is deterministic: build_materials.py gave each of our 11 slots
one MMD texture, so a material maps to the slot with the same texture.  めとか
is the decal sheet the old pipeline deleted.

Protection (Decimate vertex group) is applied to:
  * open boundary loops of every material EXCEPT hair -- these are the garment
    panel rims whose movement is what opens the leg gap; hair cards are left
    free because they are the bulk of the mesh and decimate harmlessly
  * the face: 顔 + the ひとみ group (eyes/lashes/brows) + the 口 group

blender -b -noaudio -P tools/rebuild_dense.py -- <src> <out> <ratio> [factor]
"""
import bpy
import sys
from collections import Counter, defaultdict

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = args[0], args[1]
RATIO = float(args[2]) if len(args) > 2 else 0.70
FACTOR = float(args[3]) if len(args) > 3 else 1.0

TEX_TO_SLOT = {
    "かお.png": "werewolf_head",
    "からだ.png": "werewolf_skin",
    "ひとみ.png": "werewolf_eye",
    "口.png": "werewolf_teeth",
    "頭++.png": "werewolf_hair",
    "服.png": "werewolf_upper",
    "服3.png": "werewolf_upper_b",
    "服2.png": "werewolf_lower",
    "銀パーツ.jpg": "werewolf_metal",
    "銀パーツ2.jpg": "werewolf_metal_b",
    "発光.jpg": "werewolf_emit",
    "めとか.png": None,          # decal sheet -> dropped
}

FACE_TEX = {"かお.png", "ひとみ.png", "口.png"}
HAIR_TEX = "頭++.png"

bpy.ops.wm.open_mainfile(filepath=SRC)

obj = None
arm = None
for o in bpy.data.objects:
    if o.type == "MESH" and len(o.data.vertices) > 100000:
        obj = o
    elif o.type == "ARMATURE" and len(o.data.bones) == 209 and arm is None:
        arm = o
print("mesh:", obj.name, len(obj.data.vertices), "verts,", len(obj.data.polygons), "polys")
print("armature:", arm.name, len(arm.data.bones), "bones")

import os
import re


def tex_of(mat):
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            return os.path.basename(n.image.filepath or n.image.name)
    return "<none>"


# ---- 1. work out which slot each old material becomes --------------------
old_to_tex = {}
for i, slot in enumerate(obj.material_slots):
    old_to_tex[i] = tex_of(slot.material) if slot.material else "<none>"
    if old_to_tex[i] not in TEX_TO_SLOT:
        print("  WARNING unmapped material %r (%s)" % (slot.material.name, old_to_tex[i]))

me = obj.data

# ---- 2. drop the decal sheet before decimating ---------------------------
decal_idx = {i for i, t in old_to_tex.items() if TEX_TO_SLOT.get(t, "x") is None}
import bmesh
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
doomed = [f for f in bm.faces if f.material_index in decal_idx]
print("dropping %d decal faces" % len(doomed))
bmesh.ops.delete(bm, geom=doomed, context="FACES")
bm.to_mesh(me)
me.update()
bm.free()
print("after decal drop:", len(me.vertices), "verts", len(me.polygons), "polys")

# ---- 3. protection vertex group -----------------------------------------
# boundary edges of the current mesh
facecount = Counter()
for p in me.polygons:
    vs = list(p.vertices)
    for k in range(len(vs)):
        a, b = vs[k], vs[(k + 1) % len(vs)]
        facecount[(a, b) if a < b else (b, a)] += 1

vmat = {}
for p in me.polygons:
    for vi in p.vertices:
        vmat.setdefault(vi, p.material_index)

protect = set()
hair_idx = {i for i, t in old_to_tex.items() if t == HAIR_TEX}
# Only the panelled garment materials: their rims are what open the leg gap.
# Skin/eye/teeth boundaries are mostly UV-seam splits and are cheap to collapse;
# hair is left free because it is half the mesh.
GARMENT_TEX = {"服.png", "服3.png", "服2.png", "銀パーツ.jpg", "銀パーツ2.jpg"}
garment_idx = {i for i, t in old_to_tex.items() if t in GARMENT_TEX}
for (a, b), c in facecount.items():
    if c != 1:
        continue
    mi = vmat.get(a, -1)
    if mi not in garment_idx:
        continue
    protect.add(a)
    protect.add(b)

face_idx = {i for i, t in old_to_tex.items() if t in FACE_TEX}
n_face = 0
for i, mi in vmat.items():
    if mi in face_idx:
        protect.add(i)
        n_face += 1
print("protect: %d boundary verts (non-hair) + %d face verts -> %d total (of %d)"
      % (len(protect) - n_face, n_face, len(protect), len(me.vertices)))

vg = obj.vertex_groups.new(name="protect_mask")
vg.add(list(protect), 1.0, "REPLACE")

# ---- 4. decimate ---------------------------------------------------------
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

tris_before = sum(len(p.vertices) - 2 for p in me.polygons)
mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
mod.decimate_type = "COLLAPSE"
mod.ratio = RATIO
mod.vertex_group = "protect_mask"
mod.vertex_group_factor = FACTOR
# Blender's group selects the verts that MAY collapse, so invert it: the mask
# marks what we want to keep (garment rims + face), everything else collapses.
mod.invert_vertex_group = True
mod.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=mod.name)
me = obj.data
tris_after = sum(len(p.vertices) - 2 for p in me.polygons)
print("decimate ratio %.2f factor %.2f: %d -> %d tris (%.3f of source)"
      % (RATIO, FACTOR, tris_before, tris_after, tris_after / 263003.0))
print("verts:", len(me.vertices))

# boundary check after
fc2 = Counter()
for p in me.polygons:
    vs = list(p.vertices)
    for k in range(len(vs)):
        a, b = vs[k], vs[(k + 1) % len(vs)]
        fc2[(a, b) if a < b else (b, a)] += 1
print("boundary edges now:", sum(1 for c in fc2.values() if c == 1))

# ---- 5. remap materials to our 11 slots ---------------------------------
slots_wanted = []
for t, s in TEX_TO_SLOT.items():
    if s and s not in slots_wanted:
        slots_wanted.append(s)
slots_wanted.sort()
new_index = {name: i for i, name in enumerate(slots_wanted)}

remap = {}
for old_i, t in old_to_tex.items():
    s = TEX_TO_SLOT.get(t)
    if s is None:
        continue
    remap[old_i] = new_index[s]

# resolve every polygon's new index BEFORE touching the slot list, because
# clearing materials invalidates the current indices
poly_new = [remap.get(p.material_index, 0) for p in me.polygons]

me.materials.clear()
for name in slots_wanted:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    me.materials.append(m)

for p, mi in zip(me.polygons, poly_new):
    p.material_index = mi
me.update()

print("material slots:", [(i, s.name) for i, s in enumerate(obj.material_slots)])
cnt = Counter(p.material_index for p in me.polygons)
for i, s in enumerate(obj.material_slots):
    print("  %-18s %6d polys" % (s.material.name, cnt.get(i, 0)))

# ---- 6. normalise object names so retarget_weights2 can find them -------
obj.name = "werewolf_model"
me.name = "werewolf_model"
arm.name = "werewolf"
arm.data.name = "werewolf"
for m in obj.modifiers:
    if m.type == "ARMATURE":
        m.object = arm

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
