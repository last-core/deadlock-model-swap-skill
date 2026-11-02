"""Example: graded MMD hair and ribbon mappings.

`mmd_map.py` sends all hair to `head` and the scarf ribbon to a single spine
bone. That makes a large part of the mesh one rigid plank. This module keeps the
body mapping from `mmd_map` but gives hair and the scarf real chains.

Progress is measured down the strand by Z. In this source model the hair grows
from the scalp at z ~2.19 and hangs to z ~0.83, so Z is a good arc-length proxy
and produces a mapping that is monotonic along every strand. For a different
model, replace the Z constants with a projection onto the strand chain or
another monotonic parameter.

Chains in this case study:

  後ろ髪 (back hair)  root -> head, then hair_back_{a,b,c,d}_0 .. _end
  前髪   (bangs)      root -> head, then bangs_{0,1,2,end}_{l,r}
  レッドフード (scarf ribbon) -> neck_0 / spine_3 / tail_* by height

The scarf uses the tail chain in this hero because the scarf is a long
tail-like ribbon. For a hero without a tail chain, use the spine chain instead
and update ``RIBBON_CHAIN``.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd_map as M  # noqa: E402


BACK_CHAINS = {
    "a": ["hair_back_a_0", "hair_back_a_1", "hair_back_a_2", "hair_back_a_3",
          "hair_back_a_end"],
    "b": ["hair_back_b_0", "hair_back_b_1", "hair_back_b_2", "hair_back_b_3",
          "hair_back_b_4", "hair_back_b_end"],
    "c": ["hair_back_c_0", "hair_back_c_1", "hair_back_c_2", "hair_back_c_3",
          "hair_back_c_4", "hair_back_c_end"],
    "d": ["hair_back_d_0", "hair_back_d_1", "hair_back_d_2", "hair_back_d_3",
          "hair_back_d_end"],
}

BANGS_CHAINS = {
    "l": ["bangs_0_l", "bangs_1_l", "bangs_2_l", "bangs_end_l"],
    "r": ["bangs_0_r", "bangs_1_r", "bangs_2_r", "bangs_end_r"],
}

RIBBON_CHAIN = ["neck_0", "spine_3", "tail_0", "tail_1", "tail_2", "tail_3",
                "tail_4", "tail_5", "tail_end"]

# Z of the scalp and of the longest hair tip in the source mesh (metres).
HAIR_ROOT_Z, HAIR_TIP_Z = 2.19, 0.85
BANGS_ROOT_Z, BANGS_TIP_Z = 2.40, 2.17
RIBBON_ROOT_Z, RIBBON_TIP_Z = 1.99, 0.17


def _clamp01(t):
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def graded(chain, t, head_frac, head_blend=0.0):
    """Weights as a smooth blend between adjacent chain bones.

    A single bone per strand segment makes hair piecewise rigid: each segment
    snaps to the next bone instead of bending through it. Interpolating between
    bone i and i+1 gives a continuous falloff along the strand. ``head_blend``
    feathers the root back into ``head``.
    """
    if t <= head_frac:
        return {"head": 1.0}
    u = (t - head_frac) / (1.0 - head_frac)
    s = u * (len(chain) - 1)
    i = int(s)
    f = s - i
    b0 = chain[min(i, len(chain) - 1)]
    b1 = chain[min(i + 1, len(chain) - 1)]
    out = {}
    out[b0] = out.get(b0, 0.0) + (1.0 - f)
    out[b1] = out.get(b1, 0.0) + f
    if head_blend > 0.0 and u < head_blend:
        w = 1.0 - (u / head_blend)          # 1 at the root, 0 at head_blend
        out = {k: v * (1.0 - w) for k, v in out.items()}
        out["head"] = out.get("head", 0.0) + w
    return {k: v for k, v in out.items() if v > 1e-4}


def map_bone_weights(name, centroid=None):
    """Return {bone: weight} for a source group, or None if it must be dropped."""
    n = M.normalise(name)
    stem, side = M.side_of(n)
    x, z = (centroid[0], centroid[2]) if centroid else (0.0, 0.0)

    if stem in ("両目", "両眼"):
        return {"eye_0_L": 0.5, "eye_0_R": 0.5}

    if stem.startswith("後ろ髪"):
        if centroid is None:
            return {"head": 1.0}
        chain_key = "a" if x > 0.12 else ("b" if x > 0.0 else
                                          ("c" if x > -0.12 else "d"))
        t = _clamp01((HAIR_ROOT_Z - z) / (HAIR_ROOT_Z - HAIR_TIP_Z))
        return graded(BACK_CHAINS[chain_key], t, 0.10, head_blend=0.28)

    if stem.startswith("前髪"):
        if centroid is None:
            return {"head": 1.0}
        s = side if side in ("l", "r") else ("l" if x >= 0 else "r")
        t = _clamp01((BANGS_ROOT_Z - z) / (BANGS_ROOT_Z - BANGS_TIP_Z))
        return graded(BANGS_CHAINS[s], t, 0.12, head_blend=0.30)

    if stem.startswith("レッドフード"):
        if centroid is None:
            return {"spine_2": 1.0}
        t = _clamp01((RIBBON_ROOT_Z - z) / (RIBBON_ROOT_Z - RIBBON_TIP_Z))
        return graded(RIBBON_CHAIN, t, 0.0)

    b = M.map_bone(name)
    return {b: 1.0} if b else None


def map_group(name, centroid=None):
    """Preferred interface for the generic retarget script."""
    return map_bone_weights(name, centroid)


def map_bone(name, centroid=None):
    """Back-compat: the dominant bone for this group."""
    weights = map_bone_weights(name, centroid)
    if not weights:
        return None
    return max(weights.items(), key=lambda kv: kv[1])[0]
