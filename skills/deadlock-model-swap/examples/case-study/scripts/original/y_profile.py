"""Per-material, per-height Y profile of the mesh - no hair/cape confound."""
import bpy
import sys
from collections import defaultdict

args = sys.argv[sys.argv.index("--") + 1:]
BLEND = args[0]
MESH = args[1] if len(args) > 1 else "werewolf_model"
XMAX = float(args[2]) if len(args) > 2 else 0.15

bpy.ops.wm.open_mainfile(filepath=BLEND)
obj = bpy.data.objects[MESH]
arm = bpy.data.objects["werewolf"]
mw = obj.matrix_world
aw = arm.matrix_world

mats = [s.material.name if s.material else "<none>" for s in obj.material_slots]
print("materials:", mats)

# vertex -> material (first polygon that uses it)
vmat = {}
for p in obj.data.polygons:
    for vi in p.vertices:
        vmat.setdefault(vi, p.material_index)

# reference bone Y by height (spine chain, interpolated)
CHAIN = [(b.name, (aw @ b.head_local).z, (aw @ b.head_local).y)
         for b in arm.data.bones
         if b.name in ("pelvis", "spine_0", "spine_1", "spine_2", "spine_3",
                       "neck_0", "head")]
CHAIN.sort(key=lambda t: t[1])


def bone_y(z):
    if z <= CHAIN[0][1]:
        return CHAIN[0][2]
    if z >= CHAIN[-1][1]:
        return CHAIN[-1][2]
    for (n0, z0, y0), (n1, z1, y1) in zip(CHAIN, CHAIN[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / max(z1 - z0, 1e-9)
            return y0 + (y1 - y0) * t
    return 0.0


bands = defaultdict(lambda: defaultdict(list))
for i, v in enumerate(obj.data.vertices):
    p = mw @ v.co
    if abs(p.x) > XMAX:
        continue
    mi = vmat.get(i)
    if mi is None:
        continue
    bands[round(p.z, 1)][mats[mi] if mi < len(mats) else "?"].append(p.y)

SKIP_MATS = {"werewolf_hair"}
print("\nz-band  material          n     y[min .. max]     median   spine_bone_y   delta")
for z in sorted(bands):
    if z < 1.2:
        continue
    by = bone_y(z + 0.05)
    for mat in sorted(bands[z]):
        if mat in SKIP_MATS:
            continue
        ys = sorted(bands[z][mat])
        if len(ys) < 40:
            continue
        med = ys[len(ys) // 2]
        print("%5.1f   %-16s %5d  [%6.3f .. %6.3f]  %6.3f   %6.3f   %+7.3f"
              % (z, mat, len(ys), ys[0], ys[-1], med, by, med - by))
