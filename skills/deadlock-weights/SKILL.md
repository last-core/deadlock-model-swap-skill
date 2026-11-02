---
name: Deadlock Weights
description: Internal step 3 of the Deadlock model-swap pipeline. Retarget source vertex groups to the Deadlock skeleton, build graded hair/cloth chains, smooth, and cap to four influences. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 3 — Retarget weights

## Purpose

Give the final destination mesh a clean skin on the stock skeleton. Prefer the
source's own groups; surface transfer alone has no semantics and scrambles
regions.

## Inputs

- `decimated.blend` (destination topology).
- Full-resolution aligned source mesh with vertex groups.
- `project.json` with source group count and mapping module.
- `stock_skeleton.json` for bone names.

## Outputs

- `weighted.blend`.
- `weights_report.json` — unweighted count, weight sums, influence histogram,
  per-material dominant-bone histogram, missing bones, nearest-surface
  distances.

## Preconditions

`gates.decimate == pass`.

## Agent actions

- Inspect source groups and centroids.
- Load or write a mapping module with
  `map_group(name, centroid) -> {bone: weight} | None`.
- Run `retarget_weights.py`.
- Review the report; fix wrong-region mappings and re-run.

## User actions

- Review a hand-authored stress pose or a clip replay.
- Check hair roots, cloth panels, eyes, fingers and the face.
- Read `../deadlock-model-swap/references/preview-caveats.md` for unit/clip
  preview traps.

## Procedure

### 1. Inspect the source

- List groups, vertex counts and centroids.
- Note groups whose name alone is ambiguous (which side, how far down a strand).
- Note rigid parts (armour, buttons, accessories) that should be single-bone.

### 2. Map groups

Use a mapping module with this interface:

```python
def map_group(name: str, centroid) -> dict[str, float] | None:
    ...
```

- Body groups: map to one bone.
- Rigid parts: map to one bone. Do **not** force a graded chain onto a rigid
  plate.
- Hair/cape/scarf: map progress monotonically down the strand to a chain.
  Interpolate between adjacent bones; do not map one group to one bone.
- Root: keep the first part of the strand on the anchor bone (head for hair,
  neck/chest for a scarf) so roots cannot peel off.
- Use height as an arc-length proxy only when the strand hangs vertically.
  Otherwise project onto the chain or use the source group order.

### 3. Handle cloth by material

If the cloth geometry is not covered by the bone groups (for example, a scarf
with a large cloth material but few ribbon groups):

- identify the source material;
- rebind its vertices to the chosen chain by height/arc length;
- when transferring to the destination, force the chain for destination
  vertices whose nearest source face is that material. The inverse-distance
  blend otherwise dilutes the chain into the torso.

### 4. Transfer

- Build a BVH over the source mesh and a KD-tree fallback.
- For each destination vertex, find the nearest source face and blend the source
  weights by inverse distance.
- Filter bones that do not exist on the target skeleton.
- If a vertex ends up with no valid bone, fall back to the nearest target bone
  or a configured fallback bone; report it. Do not silently leave it unweighted.

### 5. Smooth

- Run a few Laplacian iterations over destination topology (weighted average of
  neighbour weights).
- Normalise after each pass.
- Cap to four influences and renormalise.
- Smoothing only crosses connected geometry; separate shells stay independent,
  which is usually intended.

### 6. Validate

Print:

- vertices with no weight;
- weight sum min/median/max;
- influences per vertex;
- dominant-bone histogram **per material**;
- bones referenced but absent;
- nearest-surface distance p50/p99/max.

## Gates

- 0 vertices with no weight.
- Weight sums 1.0 (±1e-6) after normalisation.
- ≤4 influences per vertex.
- No region bound to an absurd bone (per-material histogram).
- Hair/cloth bends continuously; roots stay on the anchor.
- Source/destination alignment p99 is within a sane threshold; if not, go back
  to `deadlock-rig-align`.
- `gates.weights == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Eyes on hair bones | Surface transfer has no semantics | Retarget source groups |
| Hair stiff, snaps | One bone per strand segment | Graded chain weights |
| Cloth tears/slits | Hard weight steps | Graded weights + smooth; protect rims |
| Scarf does not move | Bone groups cover few cloth verts | Rebind by material |
| Whole region on wrong bone | Name-only mapping | Use centroid/position too |
| Unweighted vertices | Missing target bones or no source face | Fallback bone + report; fix mapping |
| Model explodes | Source and destination not aligned | Re-run alignment |
| Too many influences | No cap | Cap to 4 and normalise |

## Handoff

Load `deadlock-materials`.
