---
name: Deadlock Swap Setup
description: Internal step 0 of the Deadlock model-swap pipeline. Verify tools, extract stock hero assets, measure skeleton/mesh/materials/portraits/weapon, and write project.json. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 0 — Swap setup

## Purpose

Establish every fact the later stages need. No mesh edits, no material edits, no
packing. The output is a measured `project.json` plus stock reference dumps.

## Inputs

- Hero key / display name.
- Source model path and format.
- Game install and addon paths.
- Tool paths: Blender, Source 2 Viewer CLI, CSDK 12 resource compiler, VPK tool,
  CS2 Workshop Tools.
- Game build number.

## Outputs

- `project.json` — filled from the shared template.
- `stock_skeleton.json` — stock bone names and bind transforms.
- `stock/` — decompiled `.vmdl`, reference glTF/DMX, material dumps, portrait
  list, hitbox/attachment/camera/bodygroup/LOD/AnimGraph dumps.
- `measurements.md` — a short human-readable record.

## Preconditions

None. This is the first stage.

## Agent actions

1. Run `python ../deadlock-model-swap/scripts/project_config.py init project.json`.
2. Run `measure_stock.py` (Blender) against the stock reference import to record
   bounds, vertex/triangle counts, material slots and bone names:

   ```text
   blender -b -P scripts/measure_stock.py -- \
       --blend stock_reference.blend \
       --out stock_measurements.json \
       --skeleton-out stock_skeleton.json
   ```

3. Run `inspect_vmdl.py` against the decompiled stock `.vmdl` to list nodes:
   `RenderMeshList`, `MaterialGroupList`, `BodyGroupList`, `PhysicsShapeList`,
   `LODGroupList`, `HitboxSetList`, `AttachmentList`, `GameDataList`,
   `NmSkeletonList`, `AnimGraph2List`.
4. Fill the config. Run `project_config.py check project.json` until it passes.
5. Record tool versions and the game build.

## User actions

- Provide the source model and the hero key.
- Confirm the game install and addon paths.
- Confirm the stock model opens in Source 2 Viewer.
- Confirm the portrait list in `panorama/images/heroes/`.

## Procedure

### 1. Confirm tools

- Source 2 Viewer **20.0+**. Older versions decompile camera attachments wrong.
- Blender with the Valve DMX addon (`io_scene_valvesource2` or
  `bl_ext.user_default.io_scene_valvesource2`).
- CSDK 12 for materials and ModelDoc.
- CS2 Workshop Tools for AnimGraph 2.
- A VPK packer and Source 2 Viewer CLI.
- Record the game build; behavior changes between builds.

### 2. Extract the stock hero

- Open the game's `pak01_dir.vpk`.
- Decompile the hero's `.vmdl_c` to `.vmdl` plus DMX.
- Export a glTF for Blender reference.
- Do **not** put the stock DMX or `.vmdl` in the final addon tree.

### 3. Measure the stock skeleton

- Record every bone name and rest/bind transform.
- Save names and matrices to `stock_skeleton.json`.
- Record helper/pivot bones; names may differ between dumpers.
- Record the stock bone count. Added bones are allowed later; stock entries must
  not change.

### 4. Measure the stock meshes

- Render-mesh names and collection/DMX names.
- Vertex and triangle counts.
- World bounds and bone-local bounds.
- Material slots.
- Which mesh is the body and which are weapons/accessories.
- The body triangle count sets `stock.body_tris`; choose `stock.tri_budget`
  around 1.2–1.5x stock.

### 5. Measure materials

- Names, paths, shader, flags, texture inputs.
- Which inputs are packed together (see `material-parameters.md`).
- Which stock materials can be reused.

### 6. Measure bindings

- Hitbox sets, attachments, camera offsets/FOV, health-bar/game data,
  bodygroups, LOD groups, AnimGraph skeleton/graph paths.
- These are copied, never invented.

### 7. Measure portraits

- List `panorama/images/heroes/`.
- Record the exact compiled name, size, format and mips for every portrait the
  mod will replace.
- Sizes vary by hero and image type. Do not assume.

### 8. Measure the source

- Format, mesh object, armature object, vertex-group count.
- Source units and axes.
- Source materials and textures.
- Source triangle count.
- Whether the source has a real skin or needs surface transfer.
- The mapping module for source groups, if one exists.

### 9. Measure the weapon (if any)

- Weapon bone name.
- Stock weapon mesh name.
- Stock weapon bbox in the **weapon bone local frame**.
- Long axis, muzzle direction, grip/attachment point.
- Stock triangle count and materials.

### 10. Write and check the config

```text
python ../deadlock-model-swap/scripts/project_config.py init project.json
# fill the fields
python ../deadlock-model-swap/scripts/project_config.py check project.json
```

## Gates

- `game`, `hero`, `source`, `units`, `stock`, `paths`, `tool_versions` and
  `gates` present.
- Stock skeleton has names and bind transforms.
- Stock render-mesh names and triangle counts recorded.
- Stock materials recorded.
- Portrait names/sizes recorded.
- Weapon bbox recorded if the swap includes a weapon.
- Source mesh/armature names, units and axes recorded.
- Tools resolve; game build recorded.
- No files edited.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Camera wrong later | Source 2 Viewer older than 20.0 | Re-export with 20.0+ |
| Portrait change has no effect | Wrong panorama key | List the directory and confirm |
| Mesh tiny/huge later | Units or axes misrecorded | Measure the stock bounds and set `units.scale` |
| Weapon fit wrong | Bbox measured in world, not bone-local | Re-measure in the weapon bone frame |
| Skeleton mismatch later | Helper bones renamed by the dumper | Compare bind transforms, not names |
| Material slots missing later | Stock materials not recorded | Dump the material group |

## Handoff

Load `deadlock-rig-align`.
