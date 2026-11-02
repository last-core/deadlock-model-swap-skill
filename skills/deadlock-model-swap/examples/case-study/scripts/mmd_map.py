"""Example: map MMD bone/group names onto a Deadlock hero skeleton.

This is a case-study mapping, not a universal MMD map. It shows the shape of the
API and the kind of name/position logic a source-group retarget needs.

Names are normalised first with NFKC, so fullwidth digits, fullwidth spaces and
fullwidth punctuation become ASCII. Side suffixes (`.L`, `.R`, `_L`, `_R`) and
leading `左` / `右` are recognised.
"""
import unicodedata


def normalise(name):
    return unicodedata.normalize("NFKC", name).replace("\u3000", " ").strip()


def side_of(name):
    """Return (stem, side) for names like '足.L', '左足' or '前髪 A 2.R'."""
    n = normalise(name)
    for suffix in (".L", ".R", "_L", "_R", " L", " R"):
        if n.endswith(suffix):
            return n[: -len(suffix)].strip(), suffix.strip("._ ")[-1]
    if n.startswith("左"):
        return n[1:].strip(), "L"
    if n.startswith("右"):
        return n[1:].strip(), "R"
    return n, None


# Ordered: first match wins. These are Japanese MMD names, not Deadlock names.
PREFIX_RULES = [
    # head
    ("口ボーン", "head"),
    ("あご", "head"),
    ("あほげ", "head"),
    ("前髪", "head"),
    ("後ろ髪", "head"),
    ("目", "eye_0_{s}"),
    ("AH1", "spine_3"),
    # fingers before the generic arm/hand rules
    ("親指0", "finger_thumb_0_{s}"),
    ("親指1", "finger_thumb_1_{s}"),
    ("親指2", "finger_thumb_2_{s}"),
    ("人指1", "finger_index_0_{s}"),
    ("人指2", "finger_index_1_{s}"),
    ("人指3", "finger_index_2_{s}"),
    ("中指1", "finger_middle_0_{s}"),
    ("中指2", "finger_middle_1_{s}"),
    ("中指3", "finger_middle_2_{s}"),
    ("薬指1", "finger_ring_0_{s}"),
    ("薬指2", "finger_ring_1_{s}"),
    ("薬指3", "finger_ring_2_{s}"),
    ("小指1", "finger_pinky_0_{s}"),
    ("小指2", "finger_pinky_1_{s}"),
    ("小指3", "finger_pinky_2_{s}"),
    # arms: twists before the plain names
    ("腕捩2", "arm_upper_{s}_TWIST1"),
    ("腕捩3", "arm_upper_{s}_TWIST1"),
    ("腕捩1", "arm_upper_{s}_TWIST"),
    ("腕捩", "arm_upper_{s}_TWIST"),
    ("ひじ", "arm_lower_{s}"),
    ("手捩2", "arm_lower_{s}_TWIST1"),
    ("手捩3", "arm_lower_{s}_TWIST1"),
    ("手捩1", "arm_lower_{s}_TWIST"),
    ("手捩", "arm_lower_{s}_TWIST"),
    ("手首", "hand_{s}"),
    ("手先", "hand_{s}"),
    ("肩", "clavicle_{s}"),
    ("腕", "arm_upper_{s}"),
    # legs: longest first
    ("足首", "ankle_{s}"),
    ("ひざD2", "leg_lower_{s}"),
    ("ひざD", "leg_lower_{s}"),
    ("ひざ", "leg_lower_{s}"),
    ("足D", "leg_upper_{s}"),
    ("足", "leg_upper_{s}"),
    ("つま先", "ball_{s}"),
]

# Standard MMD spine names, plus the extra torso names common in MMD models.
EXACT = {
    "頭": "head",
    "首": "neck_0",
    "上半身": "spine_1",
    "上半身2": "spine_2",
    "上半身3": "spine_3",
    "上半身_ウエイト": "spine_1",
    "上半身2_ウエイト": "spine_2",
    "上半身3_ウエイト": "spine_3",
    "上半身3ひだい": "spine_3",
    "上半身3みぎ": "spine_3",
    "上半身3+": "spine_3",
    "上半身3+_": "spine_3",
    "下半身": "pelvis",
    "下半身2": "pelvis",
    "下半身_ウエイト": "pelvis",
    "下半身_ウエイト2": "pelvis",
    "センター": "pelvis",
    "腰": "pelvis",
    "あご": "head",
    "あほげ": "head",
    "後ろ釣りバンド": "spine_3",
    "釣りバンド下": "spine_3",
    # the breasts: ride with the chest so they do not shear against the jacket
    "AH1": "spine_3",
    # garment
    "うわぎ": "spine_2",
    "レッドフード": "spine_2",
}


def map_bone(name):
    """Return a single target bone, or None if the group must be dropped.

    This is the back-compat single-bone API. For graded hair/cloth chains use
    ``map_bone_weights`` in the companion module.
    """
    n = normalise(name)
    if n.startswith("mmd_") or n.startswith("_"):
        return None
    if n in EXACT:
        return EXACT[n]
    stem, side = side_of(n)
    if stem in EXACT:
        target = EXACT[stem]
        if "{s}" not in target:
            return target
    for prefix, target in PREFIX_RULES:
        if stem.startswith(prefix):
            if "{s}" in target:
                if side is None:
                    return None
                return target.format(s=side)
            return target
    # garment families that arrive with numeric suffixes
    if stem.startswith("うわぎ") or stem.startswith("レッドフード"):
        return "spine_2"
    if stem.startswith("釣りバンド"):
        return "spine_3"
    return None
