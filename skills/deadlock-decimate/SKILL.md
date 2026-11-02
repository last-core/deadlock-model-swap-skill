---
name: Deadlock Decimate
description: Internal step 2 of the Deadlock model-swap pipeline. Decimate the destination mesh to the stock triangle budget while protecting the face and garment boundaries, then merge materials. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 2 — Decimate to budget

## Purpose

Finalize the destination topology **before** weights. Decimation changes vertex
count and connectivity; retargeting onto the final mesh avoids re-weighting
collapsed vertices.

## Inputs

- `aligned.blend` from step 1.
- `project.json` with `stock.body_tris` and `stock.tri_budget`.
- Material mapping: texture name → output slot, or "keep existing".

## Outputs

- `decimated.blend` — final destination topology.
- `decimate_report.json` — before/after counts, boundary edges, per-material
  polygons.
- Keep the full-resolution aligned source for the weights stage.

## Preconditions

`gates.rig_align == pass`.

## Agent actions

- Copy the aligned blend to a full-resolution backup before decimating.
- Run `decimate.py` with a protect mask.
- Inspect the report: triangle count, boundary edges, per-material counts.
- Re-run with a different ratio or protect set if the face/hair/silhouette
  suffers.

## User actions

- Review close-ups of the face, hair cards, garment rims and hands.
- Confirm the silhouette still matches the stock hero.

## Procedure

### 1. Set the budget

- Use `stock.body_tris` from `project.json`.
- `stock.tri_budget` should be roughly 1.2–1.5x stock.
- Above ~2x needs profiling; triangle count is not the only cost (vertex buffer,
  skinning, shadows, overdraw).

### 2. Build the protect mask

Blender's Decimate **vertex group selects the vertices that may collapse**. To
protect a region, put it in the group and set `invert_vertex_group = True`.

Protect:

- open boundary loops of panelled garment materials — these rims tear or open
  into visible slits when their vertices move independently;
- the face: face skin, eyes/lashes/brows, mouth/teeth;
- hands if the source has fine fingers;
- hair only if the silhouette or alpha cards thin out.

Leave hair free when it is the bulk of the mesh and decimates harmlessly.

### 3. Decimate

- Disable the armature modifier temporarily so the decimate is applied to the
  rest mesh.
- Add a Decimate modifier, Collapse mode.
- Set the ratio from the budget.
- Assign the protect vertex group and `invert_vertex_group = True`.
- Apply the modifier.
- Re-enable the armature modifier.

### 4. Merge materials

- Map each old material/texture to the chosen output material.
- Resolve every polygon's new material index into a list **before** clearing the
  material slot list.
- Clear and append the new slots.
- Assign the resolved indices.
- Count polygons per slot and print the table.

### 5. Check holes correctly

A dense mesh reports many boundary edges because **UV seams duplicate
vertices**. Welding a copy by a small scene-unit threshold and recounting
separates fake seams from real holes. Do this before believing a hole count.

If a gap survives a much denser rebuild, decimation was not the cause.

### 6. Save and report

- Save `decimated.blend`.
- Keep the full-resolution aligned source as a separate file for weights.
- Write `decimate_report.json`.

## Gates

- Triangle count within budget.
- Face intact at close range.
- No new real holes in garment panels.
- Hair/silhouette acceptable.
- Material slots and per-polygon assignment correct.
- Full-resolution source backup exists.
- `gates.decimate == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Protected region destroyed | Vertex group not inverted | `invert_vertex_group = True` |
| Garment slits open | Boundary rims not protected | Add boundary loops to protect mask |
| Face smeared | Face materials not protected | Protect face/eyes/mouth |
| Everything one material | Slot list cleared before resolving indices | Resolve indices first |
| Hair disappears | Hair cards decimated too far | Protect hair or lower the ratio |
| Fake hole count | UV seams counted as boundaries | Weld a copy and recount |
| Mesh deformed during decimate | Armature modifier applied | Disable armature while decimating |

## Handoff

Load `deadlock-weights`.
