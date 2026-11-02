"""Retarget source vertex groups onto a destination mesh on a game skeleton.

Run inside Blender:

    blender -b -P retarget_weights.py -- \
        --config project.json \
        --source source_fullres.blend \
        --destination decimated.blend \
        --out weighted.blend \
        --mapping-module /path/to/mmd_map2.py \
        [--source-mesh NAME] [--dest-mesh NAME] [--armature NAME] \
        [--smooth-iters 4] [--smooth-factor 0.5] \
        [--max-influences 4] [--cull 1e-3] \
        [--force-material SUBSTRING --force-chain bone_a,bone_b,... \
         --force-root-coord Z --force-tip-coord Z] \
        [--fallback-bone NAME] [--report weights_report.json]

Mapping-module contract (one of):

    def map_group(name: str, centroid) -> dict[str, float] | None
    def map_bone_weights(name: str, centroid) -> dict[str, float] | None
    def map_bone(name: str) -> str | None

The source mesh is the full-resolution mesh that still carries the artist's
groups. The destination is the decimated game-topology mesh. Both must be
aligned in world space; the script reports a warning if their bounds disagree.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

try:
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
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


def axis_index(axis: str) -> int:
    axis = (axis or "Z").upper().lstrip("+")
    if axis not in ("X", "Y", "Z"):
        raise ValueError(f"axis must be X, Y or Z, got {axis!r}")
    return "XYZ".index(axis)


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def graded(chain: list[str], t: float, head_frac: float = 0.0) -> dict[str, float]:
    """Smooth blend between adjacent chain bones."""
    if not chain:
        return {}
    if t <= head_frac:
        return {chain[0]: 1.0}
    u = (t - head_frac) / max(1.0 - head_frac, 1e-9)
    s = u * (len(chain) - 1)
    i = int(s)
    f = s - i
    b0 = chain[min(i, len(chain) - 1)]
    b1 = chain[min(i + 1, len(chain) - 1)]
    out = {b0: 1.0 - f}
    out[b1] = out.get(b1, 0.0) + f
    return {k: v for k, v in out.items() if v > 1e-4}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--source-mesh", default=None)
    parser.add_argument("--dest-mesh", default=None)
    parser.add_argument("--armature", default=None)
    parser.add_argument("--mapping-module", default=None)
    parser.add_argument("--smooth-iters", type=int, default=None)
    parser.add_argument("--smooth-factor", type=float, default=None)
    parser.add_argument("--max-influences", type=int, default=None)
    parser.add_argument("--cull", type=float, default=None)
    parser.add_argument("--force-material", default=None,
                        help="source material name substring to rebind by chain")
    parser.add_argument("--force-chain", default="",
                        help="comma-separated bone chain for the forced material")
    parser.add_argument("--force-root-coord", type=float, default=None)
    parser.add_argument("--force-tip-coord", type=float, default=None)
    parser.add_argument("--force-axis", default=None, help="height axis for the force chain")
    parser.add_argument("--fallback-bone", default=None)
    parser.add_argument("--max-p99", type=float, default=None,
                        help="warn when nearest-surface p99 exceeds this scene-unit distance")
    parser.add_argument("--report", default=None)
    return parser.parse_args(argv)


def load_mapping(path: str):
    if not path:
        raise SystemExit("--mapping-module is required")
    module_path = Path(path).resolve()
    if not module_path.exists():
        raise SystemExit(f"mapping module not found: {module_path}")
    spec = importlib.util.spec_from_file_location("deadlock_mapping_module", module_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"could not load mapping module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "map_group"):
        return module.map_group
    if hasattr(module, "map_bone_weights"):
        return module.map_bone_weights
    if hasattr(module, "map_bone"):
        return lambda name, centroid=None: (
            {module.map_bone(name): 1.0} if module.map_bone(name) else None
        )
    raise SystemExit("mapping module must expose map_group, map_bone_weights or map_bone")


def find_mesh(name: str | None, label: str):
    if name:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise SystemExit(f"{label} not found: {name}")
        return obj
    candidates = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SystemExit(f"no {label} mesh found")
    # Prefer the mesh with the most vertex groups (the source skin), otherwise
    # the largest mesh. The caller should pass an explicit name.
    return max(candidates, key=lambda o: (len(o.vertex_groups), len(o.data.vertices)))


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    mapping = load_mapping(args.mapping_module or cfg(config, "source.mapping_module"))
    smooth_iters = args.smooth_iters if args.smooth_iters is not None else int(cfg(config, "weights.smooth_iters", 4))
    smooth_factor = args.smooth_factor if args.smooth_factor is not None else float(cfg(config, "weights.smooth_factor", 0.5))
    max_inf = args.max_influences if args.max_influences is not None else int(cfg(config, "weights.max_influences", 4))
    cull = args.cull if args.cull is not None else float(cfg(config, "weights.cull", 1e-3))

    # ---------------------------------------------------------------- source --
    bpy.ops.wm.open_mainfile(filepath=args.source)
    bpy.context.view_layer.update()
    src = find_mesh(args.source_mesh or cfg(config, "source.mesh_object"), "source")
    src_name = src.name
    print("source mesh:", src.name, len(src.data.vertices), "verts,", len(src.vertex_groups), "groups")

    mw = src.matrix_world
    coords = [mw @ v.co for v in src.data.vertices]
    polys = [tuple(p.vertices) for p in src.data.polygons]

    # Centroids of groups, weighted by vertices with a dominant group weight.
    gsum: dict[int, Vector] = {}
    gcnt: dict[int, int] = {}
    for vertex in src.data.vertices:
        point = mw @ vertex.co
        for group in vertex.groups:
            if group.weight <= 0.5:
                continue
            gsum[group.group] = gsum.get(group.group, Vector((0.0, 0.0, 0.0))) + point
            gcnt[group.group] = gcnt.get(group.group, 0) + 1
    centroid = {gi: gsum[gi] / gcnt[gi] for gi in gsum}

    bone_of_group: dict[int, dict[str, float]] = {}
    unmapped = Counter()
    for group in src.vertex_groups:
        weights = mapping(group.name, centroid.get(group.index))
        if not weights:
            unmapped[group.name] += 1
            continue
        if isinstance(weights, str):
            weights = {weights: 1.0}
        bone_of_group[group.index] = {
            str(b): float(w) for b, w in weights.items() if float(w) > 1e-6
        }
    print("unmapped groups:", len(unmapped))

    # Optional force-by-material: rebind a source material to a chain by height.
    force_verts: set[int] = set()
    force_chain = [b.strip() for b in args.force_chain.split(",") if b.strip()]
    if not force_chain:
        force_chain = [str(b).strip() for b in (cfg(config, "weights.force_chain") or []) if str(b).strip()]
    force_material = args.force_material or cfg(config, "weights.force_material")
    if force_material and force_chain:
        force_axis = axis_index(args.force_axis or cfg(config, "source.up_axis", "Z"))
        root = args.force_root_coord if args.force_root_coord is not None else float(cfg(config, "weights.force_root_coord", 0.0))
        tip = args.force_tip_coord if args.force_tip_coord is not None else float(cfg(config, "weights.force_tip_coord", 1.0))
        span = root - tip
        if abs(span) < 1e-9:
            raise SystemExit("force root and tip coordinates must differ")
        material_indices = {
            i for i, slot in enumerate(src.material_slots)
            if slot.material and force_material.lower() in slot.material.name.lower()
        }
        for poly in src.data.polygons:
            if poly.material_index in material_indices:
                force_verts.update(poly.vertices)
        print("force material:", force_material, "material slots:", len(material_indices),
              "verts:", len(force_verts))
        if not material_indices:
            print("WARNING: force material matched no source material")

    src_w: list[dict[str, float]] = []
    dropped = 0
    for vertex in src.data.vertices:
        weights: dict[str, float] = {}
        for group in vertex.groups:
            if group.weight <= 1e-4:
                continue
            mapped = bone_of_group.get(group.group)
            if not mapped:
                dropped += 1
                continue
            for bone, share in mapped.items():
                weights[bone] = weights.get(bone, 0.0) + group.weight * share
        src_w.append(weights)

    for vi in force_verts:
        point = coords[vi]
        t = clamp01((root - point[force_axis]) / span)
        src_w[vi] = graded(force_chain, t)

    print("source verts with no mapped weight:", sum(1 for w in src_w if not w),
          "| dropped refs:", dropped)

    # ----------------------------------------------------------- destination --
    bpy.ops.wm.open_mainfile(filepath=args.destination)
    bpy.context.view_layer.update()
    dst = find_mesh(args.dest_mesh or cfg(config, "source.mesh_object"), "destination")
    arm_name = args.armature or cfg(config, "source.armature_object")
    arm = bpy.data.objects.get(arm_name) if arm_name else None
    if arm is None or arm.type != "ARMATURE":
        candidates = [o for o in bpy.data.objects if o.type == "ARMATURE"]
        if len(candidates) != 1:
            raise SystemExit("armature not found; pass --armature or set source.armature_object")
        arm = candidates[0]
    bones = [b.name for b in arm.data.bones]
    bone_set = set(bones)
    print("destination mesh:", dst.name, len(dst.data.vertices), "verts;", len(bones), "bones")

    # Alignment sanity: compare bounds centres/sizes.
    def bound_center(obj):
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        if not points:
            return Vector((0.0, 0.0, 0.0)), 0.0
        lo = Vector((min(p[i] for p in points) for i in range(3)))
        hi = Vector((max(p[i] for p in points) for i in range(3)))
        return (lo + hi) / 2.0, max((hi - lo).length, 1e-9)

    # `src` is no longer valid after open_mainfile; compute from stored coords.
    lo = Vector((min(p[i] for p in coords) for i in range(3)))
    hi = Vector((max(p[i] for p in coords) for i in range(3)))
    src_center = (lo + hi) / 2.0
    src_size = max((hi - lo).length, 1e-9)
    dst_center, dst_size = bound_center(dst)
    center_delta = (src_center - dst_center).length
    relative_delta = center_delta / max(src_size, dst_size, 1e-9)
    if relative_delta > 0.1:
        print("WARNING: source and destination bounds centres differ by %.4f (%.1f%% of size)" % (
            center_delta, relative_delta * 100.0))

    tree = KDTree(len(coords))
    for i, point in enumerate(coords):
        tree.insert(point, i)
    tree.balance()
    bvh = BVHTree.FromPolygons(coords, polys, all_triangles=False, epsilon=0.0)

    dsts = dst.data.vertices
    n = len(dsts)
    if n == 0:
        raise SystemExit("destination mesh has no vertices")
    dw = dst.matrix_world
    new_w: list[dict[str, float] | None] = [None] * n
    distances: list[float] = []
    missing = set()
    n_forced = 0

    def blended(point: Vector):
        location, _normal, face_index, distance = bvh.find_nearest(point)
        if face_index is None:
            _loc, vertex_index, distance = tree.find(point)
            return src_w[vertex_index], distance, None
        acc: dict[str, float] = {}
        total = 0.0
        for vi in polys[face_index]:
            d = (point - coords[vi]).length
            weight = 1.0 / (d * d + 1e-8)
            total += weight
            for bone, value in src_w[vi].items():
                acc[bone] = acc.get(bone, 0.0) + value * weight
        if total <= 0:
            _loc, vertex_index, distance = tree.find(point)
            return src_w[vertex_index], distance, None
        return {bone: value / total for bone, value in acc.items()}, distance, face_index

    force_set = force_verts
    force_chain_names = [b for b in force_chain if b in bone_set]

    for i, vertex in enumerate(dsts):
        point = dw @ vertex.co
        weights, distance, face_index = blended(point)
        distances.append(distance)
        if face_index is not None and force_set:
            hit = sum(1 for vi in polys[face_index] if vi in force_set)
            if hit >= 2 and force_chain_names:
                force_axis = axis_index(args.force_axis or cfg(config, "source.up_axis", "Z"))
                root = args.force_root_coord if args.force_root_coord is not None else float(cfg(config, "weights.force_root_coord", 0.0))
                tip = args.force_tip_coord if args.force_tip_coord is not None else float(cfg(config, "weights.force_tip_coord", 1.0))
                t = clamp01((root - point[force_axis]) / (root - tip))
                weights = graded(force_chain_names, t)
                n_forced += 1
        items = [(bone, value) for bone, value in weights.items() if bone in bone_set]
        for bone in weights:
            if bone not in bone_set:
                missing.add(bone)
        if not items:
            fallback = args.fallback_bone or cfg(config, "weights.fallback_bone")
            if fallback and fallback in bone_set:
                items = [(fallback, 1.0)]
            else:
                # Nearest bone head as a last resort, so the vertex is not left
                # unweighted. This is a fallback, not a quality mapping.
                nearest = None
                best = None
                for bone in arm.data.bones:
                    head = arm.matrix_world @ bone.head_local
                    d = (point - head).length
                    if best is None or d < best:
                        best = d
                        nearest = bone.name
                if nearest:
                    items = [(nearest, 1.0)]
        if items:
            items.sort(key=lambda item: -item[1])
            items = items[:max_inf]
            total = sum(value for _, value in items)
            if total > 0:
                new_w[i] = {bone: value / total for bone, value in items}

    distances.sort()
    if distances:
        p50 = distances[n // 2]
        p99 = distances[min(int(n * 0.99), n - 1)]
        max_dist = distances[-1]
    else:
        p50 = p99 = max_dist = 0.0
    print("nearest-surface distance: p50 %.5f p99 %.5f max %.5f" % (p50, p99, max_dist))
    max_p99 = args.max_p99 if args.max_p99 is not None else cfg(config, "weights.max_p99")
    if max_p99 is not None and p99 > float(max_p99):
        print("WARNING: p99 distance %.5f exceeds threshold %.5f; check alignment" % (p99, float(max_p99)))
    print("forced scarf/cloth verts:", n_forced)
    print("bones referenced but absent:", sorted(missing))
    print("verts with no weight:", sum(1 for w in new_w if w is None))

    # ------------------------------------------------------------- smoothing --
    index: dict[str, int] = {}
    for weights in new_w:
        if not weights:
            continue
        for bone in weights:
            index.setdefault(bone, len(index))
    bone_count = len(index)
    print("bones in use before smoothing:", bone_count)
    if bone_count == 0:
        raise SystemExit(
            "no weights were assigned; check the mapping module, source groups, "
            "and destination armature"
        )

    W = np.zeros((n, bone_count), dtype=np.float32)
    for i, weights in enumerate(new_w):
        if not weights:
            continue
        for bone, value in weights.items():
            W[i, index[bone]] = value

    edges = set()
    for poly in dst.data.polygons:
        verts = list(poly.vertices)
        for k in range(len(verts)):
            a, b = verts[k], verts[(k + 1) % len(verts)]
            edges.add((a, b) if a < b else (b, a))
    ea = np.array([e[0] for e in edges], dtype=np.int64)
    eb = np.array([e[1] for e in edges], dtype=np.int64)
    degree = np.zeros(n, dtype=np.float32)
    np.add.at(degree, ea, 1.0)
    np.add.at(degree, eb, 1.0)
    degree[degree == 0] = 1.0
    print("edges:", len(edges), "mean valence %.2f" % degree.mean())

    def normalise(matrix: np.ndarray) -> np.ndarray:
        sums = matrix.sum(axis=1, keepdims=True)
        sums[sums < 1e-8] = 1.0
        return matrix / sums

    W = normalise(W)
    for iteration in range(max(smooth_iters, 0)):
        acc = np.zeros_like(W)
        np.add.at(acc, ea, W[eb])
        np.add.at(acc, eb, W[ea])
        acc /= degree[:, None]
        W = normalise((1.0 - smooth_factor) * W + smooth_factor * acc)
        influences = (W > cull).sum(axis=1)
        print("  smooth %d: mean influences %.2f max %d" % (
            iteration + 1, influences.mean(), influences.max()))

    # ---------------------------------------------------------------- cap 4 --
    if bone_count > max_inf:
        part = np.argpartition(-W, max_inf - 1, axis=1)[:, :max_inf]
        capped = np.zeros_like(W)
        rows = np.arange(n)[:, None]
        capped[rows, part] = W[rows, part]
        W = capped
    W[W < cull] = 0.0
    W = normalise(W)

    influences = (W > 0).sum(axis=1)
    print("final influences: mean %.2f distribution %s" % (
        influences.mean(), dict(sorted(Counter(influences.tolist()).items()))))
    zero_rows = int((W.sum(axis=1) < 0.5).sum())
    print("rows summing to 0:", zero_rows)

    # --------------------------------------------------------------- assign --
    names = list(index.keys())
    used = Counter()
    for j, bone in enumerate(names):
        used[bone] = int((W[:, j] > 0).sum())

    for group in list(dst.vertex_groups):
        dst.vertex_groups.remove(group)
    groups = {bone: dst.vertex_groups.new(name=bone) for bone, count in used.items() if count}

    buckets: dict[tuple[str, float], list[int]] = {}
    for i in range(n):
        row = W[i]
        for j in np.nonzero(row)[0]:
            key = (names[j], round(float(row[j]), 4))
            if key[1] > 0:
                buckets.setdefault(key, []).append(i)
    for (bone, value), ids in buckets.items():
        if bone in groups:
            groups[bone].add(ids, value, "REPLACE")

    # Fix rounding so every vertex sums to 1.0.
    nudged = 0
    for i in range(n):
        row = W[i]
        nonzero = np.nonzero(row)[0]
        if not len(nonzero):
            continue
        total = sum(round(float(row[j]), 4) for j in nonzero)
        if abs(total - 1.0) > 1e-6:
            j = nonzero[int(np.argmax(row[nonzero]))]
            current = round(float(row[j]), 4)
            groups[names[j]].add([i], current + (1.0 - total), "REPLACE")
            nudged += 1
    print("vertices nudged for exact weight sum:", nudged)

    # -------------------------------------------------------------- validate --
    sums = []
    influence_counter = Counter()
    for vertex in dst.data.vertices:
        weights = [g.weight for g in vertex.groups if g.weight > 1e-6]
        sums.append(sum(weights))
        influence_counter[len(weights)] += 1
    sums.sort()
    print("weight sum: min %.6f p1 %.6f p50 %.6f max %.6f" % (
        sums[0], sums[len(sums) // 100], sums[len(sums) // 2], sums[-1]))
    print("influences per vertex:", sorted(influence_counter.items()))

    # Per-material dominant-bone histogram.
    mat_names = [slot.material.name if slot.material else "<none>" for slot in dst.material_slots]
    vmat: dict[int, int] = {}
    for poly in dst.data.polygons:
        for vi in poly.vertices:
            vmat.setdefault(vi, poly.material_index)
    histogram: dict[str, Counter] = {}
    for i in range(n):
        row = W[i]
        nonzero = np.nonzero(row)[0]
        if not len(nonzero):
            dominant = "<unweighted>"
        else:
            dominant = names[int(nonzero[int(np.argmax(row[nonzero]))])]
        material_index = vmat.get(i)
        material = mat_names[material_index] if material_index is not None and material_index < len(mat_names) else "<none>"
        histogram.setdefault(material, Counter())[dominant] += 1

    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    report = {
        "source": str(Path(args.source).resolve()),
        "destination": str(Path(args.destination).resolve()),
        "out": str(Path(args.out).resolve()),
        "source_mesh": src_name,
        "dest_mesh": dst.name,
        "armature": arm.name,
        "source_verts": len(coords),
        "dest_verts": n,
        "unmapped_groups": len(unmapped),
        "source_verts_no_mapped_weight": sum(1 for w in src_w if not w),
        "dropped_refs": dropped,
        "nearest_p50": p50,
        "nearest_p99": p99,
        "nearest_max": max_dist,
        "forced_verts": n_forced,
        "missing_bones": sorted(missing),
        "dest_verts_no_weight": zero_rows,
        "smooth_iters": smooth_iters,
        "smooth_factor": smooth_factor,
        "max_influences": max_inf,
        "weight_sum_min": sums[0],
        "weight_sum_max": sums[-1],
        "influences": {str(k): v for k, v in sorted(influence_counter.items())},
        "dominant_by_material": {
            material: dict(counter.most_common(12)) for material, counter in histogram.items()
        },
    }
    out = args.report or str(Path(args.out).with_suffix("")) + ".weights.json"
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("saved", args.out)
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
