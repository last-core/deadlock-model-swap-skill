---
name: Deadlock Weapon
description: Internal optional step of the Deadlock model-swap pipeline. Swap a Deadlock weapon mesh using the stock weapon's bone-local frame, fit orientation/scale/grip, and export the weapon DMX. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Optional — Weapon swap

## Purpose

Replace a hero weapon mesh without breaking grip or aim alignment. The stock
weapon's own bounding box **in the weapon bone's local frame** is the reference.

## Inputs

- Source weapon mesh.
- `project.json` with `stock.weapon` (bone, mesh name, local bbox, long axis,
  muzzle axis).
- Stock weapon blend for the fixed-camera comparison.
- Materials for the weapon.

## Outputs

- Weapon `.blend` and `.dmx`.
- `weapon_report.json` — source/stock bboxes, scale factor, muzzle match.
- Fixed-camera renders of stock and candidate.

## Preconditions

`gates.export == pass` for the body, or at least a prepared weapon source and
materials. Run before `deadlock-modeldoc` so the weapon DMX is available when
the model is built.

## Agent actions

- Measure the stock weapon in the weapon bone frame.
- Compute the source long axis and muzzle axis.
- Fit, weight, material and export.
- Render both weapons from the same camera.

## User actions

- Confirm the muzzle direction and which way the scope/sights face.
- Confirm the grip position.
- Check the weapon in game (position is only confirmable in game).
- Read `../deadlock-model-swap/references/preview-caveats.md` for the local
  weapon-preview limits.

## Procedure

### 1. Measure the stock weapon

- Find the stock weapon mesh by name from `project.json`.
- Compute its bbox in the weapon bone's local frame:

```text
local = (armature_world @ bone_matrix).inverted() @ world
```

- Record `lo`, `hi`, centre, long axis and muzzle axis.
- Record the grip/attachment point if the stock has one.

### 2. Measure the source

- Find the source weapon mesh.
- Compute its bbox, long axis and muzzle direction.
- Record the source's up axis.

### 3. Fit

- Rotate the source so its long axis maps to the stock long axis.
- Rotate so the source muzzle points the same way as the stock muzzle.
- Scale by `stock_length / source_length` along the long axis, or by an explicit
  factor from `project.json`. Do not use a magic constant.
- Centre the source on the stock centre in bone-local space.
- If the muzzle ends up reversed, apply a **180-degree rotation about the
  bone-local up axis**, not world vertical. World vertical is only correct when
  the weapon bone's up axis is world up.
- Map the fitted points back through the bone:

```text
world = armature_world @ bone_matrix @ local
```

- Do not write bone-space coordinates out as world coordinates; that drops the
  bone's rotation and produces a pitched/inverted weapon.

### 4. Bind

- Weight the weapon mesh 100% to the weapon bone.
- Parent to the armature and add an armature modifier.
- Remove any source armature or empties that would conflict.
- Map materials; do not silently fall back to a default material.

### 5. Export

- Use the export sub-skill's `export_dmx.py` with the weapon collection.
- One collection for the weapon, no armature in it.
- Keep the stock weapon render-mesh name.

### 6. Verify without the game

- Render the stock weapon and the candidate from the **same fixed camera**.
- Both sit in the same bone-local frame at rest, so identical cameras make them
  comparable.
- Match:
  - muzzle direction;
  - up direction;
  - which way the scope/sights face;
  - bbox centre and length.
- Position is only confirmable in game: at rest the weapon bone may sit at the
  origin, and clips move it through location channels.

## Gates

- Source long axis maps to stock long axis.
- Muzzle direction matches.
- Candidate is upright; no 90/180-degree error.
- Scale is derived from stock/source length, not a magic constant.
- Bbox centre close to stock.
- 100% weight to the weapon bone.
- Fixed-camera renders match.
- `gates.weapon == pass` (or `skip` if no weapon).

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Weapon pitched/inverted | Bone-space coords written as world | Map through the bone matrix |
| Weapon points backwards | Source barrel axis opposite | 180-degree flip about bone-local up |
| Weapon offset from hand | Bbox centre vs grip mismatch | Align the grip/attachment point |
| Weapon too large/small | Magic scale factor | Derive from stock/source length |
| Weapon weighted to body | Wrong vertex group | 100% weapon bone |
| Weapon material default | Unknown texture silently mapped | Fail and fix the material map |
| Weapon not visible in preview | Weapon bone at origin/rest | Verify in game; orientation only locally |

## Handoff

Load `deadlock-modeldoc` with the weapon DMX ready. If the model is already
built, load `deadlock-validate`.
