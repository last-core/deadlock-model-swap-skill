---
name: Deadlock ModelDoc
description: Internal step 6 of the Deadlock model-swap pipeline. Build the Deadlock ModelDoc: remove AnimGraph 2 nodes, swap render meshes, rebuild bodygroups/ragdoll/LODs, set DefaultMaterialGroup, and preserve attachments/camera/hitboxes. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 6 — ModelDoc

## Purpose

Build the `.vmdl` that ModelDoc/CSDK 12 can compile, with the new meshes but the
stock skeleton, hitboxes, attachments, camera and game data.

## Inputs

- DMX files from step 5 (and the weapon DMX if applicable).
- Decompiled stock `.vmdl` from setup.
- `project.json` with stock node data and material names.
- Source 2 Viewer 20.0+ dumps.

## Outputs

- `work.vmdl` — the editable model.
- `work.vmdl_c` — CSDK 12 compile.
- `modeldoc_report.json` — node checks and compile result.

## Preconditions

`gates.export == pass`; `gates.weapon == pass` if a weapon is being swapped.

## Agent actions

- Remove `AnimGraph2List` and `NmSkeletonList` before opening in CSDK 12.
- Patch render-mesh paths/names.
- Add/repair `DefaultMaterialGroup`.
- Record the stock AnimGraph 2 paths for the next stage.
- Run `vmdl_patch.py check`.
- Try `compile_model.py` with the CSDK 12 compiler; inspect the result.
- Prepare the exact GUI click list for anything that cannot be safely patched.

## User actions

- Open the work `.vmdl` in ModelDoc when the GUI fallback is needed.
- Rebuild bodygroups/ragdoll/LODs if the text patch is insufficient.
- Confirm the model compiles and looks right.

## Procedure

### 1. Decompile and clean the stock model

- Decompile the stock `.vmdl_c` to `.vmdl`.
- **Remove `AnimGraph2List` and `NmSkeletonList`** before opening in CSDK 12.
  CSDK 12 cannot read them and may crash or refuse to open the model.
- Keep a backup of the original `.vmdl`.
- Make a work copy, for example `work.vmdl`:

  ```text
  python scripts/vmdl_patch.py remove-animgraph stock.vmdl --out work.vmdl
  ```

### 2. Render meshes

- Remove LOD meshes whose names contain `_lod`.
- Disable/delete old body meshes.
- Add the new DMX meshes.
- Rename each new mesh to the stock render-mesh name.
- Map both the mesh name and its `m_fileName` path, for example
  `body=new_body,models/<hero>/body.dmx=models/<hero>/new_body.dmx`:

  ```text
  python scripts/vmdl_patch.py set-render-meshes work.vmdl \
      --map body=new_body,models/<hero>/body.dmx=models/<hero>/new_body.dmx \
      --out work.vmdl
  ```

- Delete the original mesh before renaming, or ModelDoc reports a name clash.
- If the mesh is tiny or turned, fix it in Blender and re-export. Do not fix it
  with ModelDoc import scale.

### 3. Bodygroups

- Rebuild bodygroups with the exact stock names and choices.
- Decompiled bodygroups may not work; rebuild them.
- A choice that ends in `#default` becomes `default` (drop the prefix).
- Leave a choice empty if the stock shows nothing in that state.

### 4. Materials

- Add `DefaultMaterialGroup`.
- Add one slot per Blender material name.
- Fill each slot with a stock material path (reuse) or your `.vmat`.
- A missing slot renders the mesh solid red.
- If a slot is missing, the material likely ends in `.001` in Blender; rename
  and re-export.

### 5. Ragdoll

- Rebuild the ragdoll (Biped Ragdoll is the usual choice).
- Set the surface property to `flesh`.
- Simulate all physics; watch the body fall.
- If it falls wrong, rebuild the ragdoll and adjust the shapes.

### 6. LODs

- Rebuild the LOD group with all new meshes as LOD 0.
- Add simplified LODs with the stock thresholds where possible.
- Typical automatic thresholds are 14 and 35, with target percentages around
  0.5 and 0.2. Use the stock values if they are known.
- Check far-away silhouette.

### 7. Bindings

Copy from stock, do not invent:

- hitbox sets — exactly as stock;
- attachments and parent bones;
- camera offsets and FOV;
- health-bar/game-data blocks;
- bodygroup names;
- any hero-specific game data.

### 8. Compile

```text
python scripts/compile_model.py --input work.vmdl \
    --compiler <CSDK_RESOURCECOMPILER> --output work.vmdl_c
```

- Compile in CSDK 12. If the CLI fails, open ModelDoc and compile there.
- Read every error and fix it.
- "Mesh referencing missing material" warnings are only normal if every name is
  remapped in `DefaultMaterialGroup`. Otherwise fix the slot.
- Do not test in game yet; AnimGraph 2 is still missing.

## Gates

- `AnimGraph2List` and `NmSkeletonList` removed before CSDK 12.
- Work `.vmdl` opens and compiles.
- Render meshes present and named as stock.
- Bodygroups match stock names/choices.
- `DefaultMaterialGroup` has every material.
- Ragdoll simulates.
- LODs present.
- Hitboxes/attachments/camera/game data unchanged.
- `gates.modeldoc == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| ModelDoc crashes on open | AnimGraph 2/Skeleton nodes still present | Remove both blocks |
| Mesh solid red | Missing `DefaultMaterialGroup` or slot | Add/fill slots |
| ModelDoc refuses rename | Original mesh still has that name | Delete the original first |
| Mesh tiny/turned | Blender scale/axes | Fix in Blender; do not use import scale |
| Camera in the middle | Old Source 2 Viewer dump | Re-export with 20.0+ |
| Health bar at feet | Missing game data/attachment | Copy stock blocks |
| Ragdoll stretches | Ragdoll not rebuilt | Rebuild Biped Ragdoll |
| LOD pops to a different shape | LOD group missing/wrong | Rebuild LOD 0 and simplified LODs |

## Handoff

Load `deadlock-animgraph2-compile`.
