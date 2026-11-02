---
name: Deadlock Validate
description: Internal cross-cutting step of the Deadlock model-swap pipeline. Validate skeleton identity, material refs, weights, bounds, weapon fit, portrait names, and in-pak size/CRC. Load from deadlock-model-swap after any gate or before in-game testing.
metadata:
  opencode/autoinvoke: false
---

# Validation

## Purpose

Turn "looks fine" into pass/fail. Run this after any gate and always before an
in-game test.

## Inputs

- Any stage artifact.
- `project.json`.
- `stock_skeleton.json`.
- Stage reports (`alignment_report.json`, `decimate_report.json`,
  `weights_report.json`, etc.).
- The compiled model, materials, portraits and VPK.

## Outputs

- `validation_report.json` — one entry per check.
- A short pass/fail summary.
- A list of the exact next sub-skill for each failure.

## Preconditions

The stage being validated has produced its artifact.

## Agent actions

- Run `validate.py` with the checks that apply.
- Run `check_material_refs.py`.
- Run `check_pak.py`.
- Run `compare_skeleton.py` against `stock_skeleton.json` and a compiled
  skeleton dump in the same JSON shape.
- Read the stage reports for weights/bounds/weapon.
- Produce the failure routing list.

## User actions

- Perform the in-game checklist.
- Confirm camera, health bar, sounds, LODs, hero select and portraits.

## Procedure

### 1. Skeleton identity

- Dump the compiled `.vmdl_c` with Source 2 Viewer.
- Convert the dump to the `stock_skeleton.json` shape and run
  `compare_skeleton.py --stock stock_skeleton.json --compiled compiled_skeleton.json`.
- Every stock bone must be present with the same bind matrix.
- Added bones are allowed; stock entries must match.
- Helper/pivot bone names may differ; compare transforms.

### 2. Hitboxes, attachments, camera, game data

- Compare the compiled model's nodes to the stock dump.
- Hitboxes identical.
- Attachments/game data/camera values identical.

### 3. Materials

- Run `check_material_refs.py`.
- 0 missing references.
- Shader `pbr.vfx`; feature flags correct.
- Every material name has a `DefaultMaterialGroup` slot.

### 4. Weights

- Read `weights_report.json`.
- 0 unweighted; sums 1.0; ≤4 influences.
- Per-material dominant-bone histogram has no absurd region.
- Hair/cloth roots anchored; chains monotonic.

### 5. Bounds and export

- Read `export_report.json`.
- Bounds/scale vs stock; shift present; vertex count unchanged.
- Collections/names correct.

### 6. Weapon

- Read `weapon_report.json`.
- Fixed-camera renders: same muzzle/up/bbox.
- 100% weight to the weapon bone.

### 7. Portraits

- List compiled files.
- Name == stock name; size == stock size; mips/format correct.

### 8. Pak

- Run `check_pak.py`.
- In-pak model size/CRC matches the file just compiled.
- Expected model/material/portrait counts.
- No sources, stock skeleton/clips/scripts.
- VPK footer/version valid.

### 9. In-game checklist

- Walk, run, turn.
- Aim down sights; compare camera height/zoom.
- Use every ability; check bodygroups.
- Die once; check the ragdoll.
- Check the health bar.
- Listen for footsteps/abilities.
- Check hero select/shop.
- Walk far away; check LODs.
- Check the portrait on the HUD, kill feed and minimap.

## Gates

All applicable checks pass. `gates.validate == pass`.

## Failure routing

| Failure | Load |
|---|---|
| Skeleton mismatch | `deadlock-rig-align` / `deadlock-modeldoc` |
| Hitbox/camera/attachment mismatch | `deadlock-modeldoc` |
| Material ref missing | `deadlock-materials` |
| Weight/histogram failure | `deadlock-weights` |
| Bounds/scale failure | `deadlock-export-dmx` |
| Weapon fit failure | `deadlock-weapon` |
| Portrait name/size failure | `deadlock-portraits` |
| In-pak size/CRC mismatch | `deadlock-animgraph2-compile` |
| A-pose | `deadlock-animgraph2-compile` |
| Camera centred / health bar at feet | `deadlock-modeldoc` |

## Handoff

If everything passes, the swap is ready to test in game. If a check fails, load
the sub-skill in the failure routing table, fix it, and re-run validation.
