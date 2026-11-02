---
name: Deadlock Rig Align
description: Internal step 1 of the Deadlock model-swap pipeline. Import a rigged source model against the Deadlock hero skeleton, measure the mesh-to-rig offset, and translate the mesh into alignment. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 1 — Import and align the mesh

## Purpose

Put the source mesh on the stock skeleton and prove the mesh and bones occupy
the same space. A rest pose hides a depth offset because no deformation is
applied; every animation then rotates geometry about pivots that are not inside
it.

## Inputs

- `project.json` (setup gate passed).
- Source mesh and source armature.
- Stock skeleton (`.vmdl`/DMX or glTF import).
- Stock body mesh for comparison.

## Outputs

- `aligned.blend` — full-resolution source mesh + stock armature, aligned.
- `alignment_report.json` — per-band profile and compact-feature offsets.
- A full-resolution backup for the decimate and weights stages.

## Preconditions

`gates.setup == pass`.

## Agent actions

- Run `measure_alignment.py` to produce the per-material/per-height profile and
  the compact-feature report.
- Run `align_mesh.py` in dry-run mode; review the offset.
- Apply the offset and re-measure.
- Render a side view for visual confirmation.

## User actions

- Confirm the source import orientation and the model's front/side.
- Review the side-view render.
- Confirm feet stay on the ground.
- Read `../deadlock-model-swap/references/preview-caveats.md` for the limits of
  rest-pose and clip previews.

## Procedure

### 1. Import

- Import the stock skeleton and the source mesh into one Blender file.
- Keep the source mesh object and armature names from `project.json`.
- Use one armature only.
- Do not move, rename or delete stock bones.
- Put the armature in rest pose.
- Apply source object transforms; record if that is impossible.

### 2. Check units and axes

- Confirm `units.source`, `units.target`, `units.scale`.
- Confirm `source.up_axis`, `source.forward_axis`, `source.depth_axis`.
- If the source is rotated, measure the axes; do not assume Z-up/Y-forward.

### 3. Measure the body profile

Use `measure_alignment.py`:

- per material;
- per height band;
- a narrow side window to exclude arms;
- median depth per band;
- compare with the interpolated spine centre at that height.

The output should show a systematic offset if the mesh is displaced.

### 4. Measure compact features

Use small rigid regions whose centroid is effectively the bone position:

- eyes vs eye bones;
- teeth vs jaw/teeth bones;
- hands vs hand bones;
- ankles vs ankle bones;
- a small neck/head feature.

An eyeball is a few centimetres across, so an offset is unambiguous. Do not use
nearest-vertex-to-bone as the main measurement: hair, straps and capes sit on
the bones and make every bone look close.

### 5. Fix

- Translate the **mesh vertices**, never the bones.
- Compute the offset in world space, then convert it into the mesh object's
  local space before adding it to `v.co`.
- If the mesh has shape keys, translate every key block by the same local
  offset.
- Leave Z alone unless the feet say otherwise. A Z shift usually lifts the feet
  off the ground; a proportion/scale problem needs a different fix.
- Do not apply a correction just because one axis looks off. Check all axes.

### 6. Re-measure

- Run the profile again: body medians should straddle the spine.
- Compact features should land within a few centimetres of their bones.
- Feet on `z = 0` or the stock ground plane.
- Render a **side** view with the armature drawn as rods. A front view hides a
  depth offset.

### 7. Preserve the source

Keep a copy of the full-resolution aligned source mesh. The decimate stage
changes the destination topology; the weights stage needs the full-resolution
source groups.

## Gates

- All compact features within tolerance (use a small threshold from the report,
  for example a few centimetres for eyes).
- Body-material medians straddle the spine chain.
- Feet on the ground.
- Side view confirms the offset is gone.
- No stock bone moved, renamed or deleted.
- Full-resolution source backup exists.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Rest pose perfect, animation offset | Mesh displaced from skeleton | Translate mesh vertices |
| Every bone reports close | Nearest-vertex measurement hit hair/cape | Use body profile + compact features |
| Front view looks right, game wrong | Depth offset hidden by the front view | Check a side view |
| Feet float after fix | Z was shifted | Revert Z; check foot contact |
| Offset applied twice | World offset added to local coords, or re-applied | Recompute from the unmodified backup |
| Shape keys break | Only the basis moved | Shift every key block by the same local offset |
| Model collapses | Mesh or armature scaled separately | Scale both together |

## Handoff

Load `deadlock-decimate`.
