"""Move the mesh back onto the skeleton.

Measured: the body bands of the stock mesh (correctly bound) are centred on
y ~ 0, ours on y ~ -0.31, and compact regions agree - the eye geometry sits
0.295 m in front of the eye bones, the teeth 0.296, the hands 0.33, the ankles
0.31.  A 0.30 m lever on every bone is what makes the head read as offset in
idle and the limbs fold oddly.

The bones must not move: their inverse bind poses are byte-identical to the
stock skeleton.  So the mesh vertices are translated instead, keeping the
object transform at identity so the DMX export path is unchanged.

blender -b -noaudio -P tools/align_mesh_to_rig.py -- <in.blend> <out.blend> [dx dy dz]
"""
import bpy
import sys
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = args[0], args[1]
OVERRIDE = [float(v) for v in args[2:5]] if len(args) >= 5 else None

bpy.ops.wm.open_mainfile(filepath=SRC)
obj = bpy.data.objects["werewolf_model"]
arm = bpy.data.objects["werewolf"]

if (abs(obj.matrix_world.translation.length) > 1e-6
        or abs(obj.matrix_world.to_scale().x - 1.0) > 1e-6):
    print("WARNING mesh object has a non-identity transform:",
          [round(v, 4) for v in obj.matrix_world.translation],
          [round(v, 4) for v in obj.matrix_world.to_scale()])

# compact regions: geometry small enough that its centroid is basically the
# bone position, so (centroid - bone head) is a clean measure of the offset
COMPACT = ["eye_0_L", "eye_0_R", "finger_index_2_L", "finger_index_2_R",
           "finger_ring_2_L", "finger_ring_2_R", "hand_L", "hand_R",
           "ankle_L", "ankle_R", "ball_L", "ball_R", "neck_0"]

gname = {g.index: g.name for g in obj.vertex_groups}
acc = {}
for v in obj.data.vertices:
    best = None
    for g in v.groups:
        if best is None or g.weight > best[1]:
            best = (g.group, g.weight)
    if not best:
        continue
    n = gname.get(best[0])
    if n not in COMPACT:
        continue
    a = acc.setdefault(n, [0, Vector((0, 0, 0))])
    a[0] += 1
    a[1] += obj.matrix_world @ v.co

print("== per-bone offset (centroid - bone head) ==")
offs = []
for n in COMPACT:
    b = arm.data.bones.get(n)
    if not b or n not in acc:
        continue
    c, s = acc[n]
    cen = s / c
    h = arm.matrix_world @ b.head_local
    d = cen - h
    offs.append((d, c, n))
    print("  %-20s n=%-4d offset (%6.3f %6.3f %6.3f)"
          % (n, c, d.x, d.y, d.z))

if OVERRIDE:
    D = Vector(OVERRIDE)
    print("\nusing override shift", [round(v, 4) for v in D])
else:
    ys = sorted(d.y for d, c, n in offs if c >= 40)
    zs = sorted(d.z for d, c, n in offs if c >= 40)
    # offset = centroid - bone, so the correction is minus that
    med_y = -ys[len(ys) // 2]
    med_z = -zs[len(zs) // 2]
    # never lift the feet off the ground: the soles define z = 0
    D = Vector((0.0, med_y, 0.0))
    print("\nmedian Y offset %.4f  median Z offset %.4f (ignored - feet are on z=0)"
          % (med_y, med_z))
    print("shift to apply (mesh vertices):", [round(v, 4) for v in D])

n_before = len(obj.data.vertices)
lo = Vector((min((obj.matrix_world @ v.co)[i] for v in obj.data.vertices)
             for i in range(3)))
hi = Vector((max((obj.matrix_world @ v.co)[i] for v in obj.data.vertices)
             for i in range(3)))
print("bounds before lo %s hi %s" % ([round(v, 3) for v in lo],
                                     [round(v, 3) for v in hi]))

for v in obj.data.vertices:
    v.co += D
obj.data.update()

lo2 = Vector((min((obj.matrix_world @ v.co)[i] for v in obj.data.vertices)
              for i in range(3)))
hi2 = Vector((max((obj.matrix_world @ v.co)[i] for v in obj.data.vertices)
              for i in range(3)))
print("bounds after  lo %s hi %s" % ([round(v, 3) for v in lo2],
                                     [round(v, 3) for v in hi2]))
assert len(obj.data.vertices) == n_before

bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("saved", OUT)
