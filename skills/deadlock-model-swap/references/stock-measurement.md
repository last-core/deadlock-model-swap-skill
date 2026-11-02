# Stock measurement

Measure before you touch the mesh. Every constant in the project should come
from a measurement, not from a previous swap.

## 1. Extract the stock model

Use **Source 2 Viewer 20.0+**. Older versions decompile camera attachments
incorrectly, which puts the camera in the middle of the screen.

- Open the game's `pak01_dir.vpk`.
- Decompile the hero's `.vmdl_c` to `.vmdl` plus DMX.
- Export a glTF for Blender reference.
- Dump the model data for the skeleton, render meshes, materials, hitboxes,
  attachments, camera, game data, bodygroups, LODs, and AnimGraph paths.

Do not put the stock DMX or `.vmdl` in the final addon tree. They are reference
only.

## 2. Skeleton

Record:

- every stock bone name;
- each bone's rest transform and inverse bind matrix;
- the bone hierarchy;
- which bones are helper/pivot bones;
- the total stock bone count.

Save the names and matrices to `stock_skeleton.json` next to `project.json`.
The validation stage compares the compiled model against this file.

## 3. Render meshes

Record for each stock render mesh:

- render-mesh name;
- collection/DMX name;
- vertex and triangle counts;
- world bounds and bone-local bounds;
- material slots;
- which mesh is the body and which are weapons/accessories.

The body triangle count sets the budget. A comfortable target is 1.2–1.5x
stock; above ~2x needs profiling.

## 4. Materials

Record:

- material name and path;
- shader (`pbr.vfx` for heroes);
- feature flags;
- texture inputs and their source paths;
- which inputs are packed together;
- which materials are reused, and which are unique.

## 5. Hitboxes, attachments, camera, game data

Record the exact node trees from the stock `.vmdl`:

- hitbox sets and their shapes;
- attachments and parent bones;
- camera offsets and FOV;
- health-bar anchor and game-data blocks;
- bodygroups and choices;
- LOD groups and thresholds;
- AnimGraph 2 skeleton/graph paths.

These are copied, not invented.

## 6. Portraits

List the stock portrait files in `panorama/images/heroes/`:

- `card`
- `card_critical`
- `card_gloat`
- `mm`
- `sm`
- `vertical`
- any hero-specific extras

Record the exact compiled name, width, height, format and mip setting. Sizes
vary by hero and by image type; do not assume one size for all.

## 7. Weapon

If the hero has a weapon mesh:

- record the weapon bone name;
- record the stock weapon mesh name;
- compute the stock weapon's bounding box in the **weapon bone's local frame**;
- record the long axis, muzzle direction and grip/attachment position;
- record the stock triangle count and materials.

The bounding box is a reference frame, not a guarantee of grip alignment.

## 8. Source model

Record:

- format (MMD/PMX, FBX, glTF);
- mesh object name and armature object name;
- number of vertex groups;
- whether the source carries a real skin;
- source units and axes;
- source material names and textures;
- source triangle count;
- the mapping module for source groups, if one exists.

## 9. Write `project.json`

Use `scripts/project_config.py init` and fill every field. Run
`project_config.py check` before handing off to `deadlock-rig-align`.

A measurement that is missing is a gate failure, not a value to guess.
