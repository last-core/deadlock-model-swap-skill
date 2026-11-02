# Conventions

## Units

Source 2 models are in **inches**. A meter-based Blender scene needs a factor of
**39.37**.

- If the scene is already in inches, do not scale again.
- Scale the armature and every mesh **together**.
- Apply all transforms after scaling.
- Record `units.source`, `units.target` and `units.scale` in `project.json`.
- Check the final bounds against stock. A model that is 39.37x too small or too
  large is a units bug, not a weighting bug.

## Axes

Do not assume Blender's Z-up/Y-forward convention survives the import. Many
source formats face a different direction.

Record in `project.json`:

```json
"source": {
  "up_axis": "Z",
  "forward_axis": "Y",
  "depth_axis": "Y"
}
```

Use those axes in measurement scripts. If the model faces +X, the depth axis is
X, not Y. A front view hides a depth offset; always check a side view.

## Naming

- **Bones**: stock names are the contract. Do not rename.
- **Render meshes**: keep the stock render-mesh names. ModelDoc finds meshes by
  name; bodygroups, attachments and game events reference them.
- **Collections**: one collection per render mesh. The collection name becomes
  the DMX file name. The body collection contains the armature; a weapon
  collection contains only the weapon mesh.
- **Materials**: short, plain names. No `.001` suffixes. ModelDoc matches
  material names from Blender to `DefaultMaterialGroup` slots.
- **Textures**: use the suffixes the Material Editor expects, such as `_color`,
  `_normal`, `_rough`, `_metal`, `_ao`, `_mask`. Power-of-two sizes.
- **Portraits**: the compiled file name must equal the stock file name exactly.
  Stock names often end in `_psd` even when the source image is a PNG.

## Folder layout

```text
content/citadel_addons/<addon>/
  models/heroes_wip/<hero>/
    <hero>.vmdl
    dmx/
      <render_mesh>.dmx
    materials/
      <material>.vmat
      <texture>_color.png
      ...
  panorama/
    image_compiler.vdata
    images/heroes/<portrait>.png

game/citadel_addons/<addon>/
  models/heroes_wip/<hero>/
    <hero>.vmdl_c
    materials/
      <material>.vmat_c
      <texture>_<hash>.vtex_c
  panorama/images/heroes/<portrait>.vtex_c
```

The **content** tree is compiled. The **game** tree is packed. A separate
`staging/` folder is used before packing.

## `project.json`

Every stage reads and updates the same file. The setup sub-skill writes it; the
validation sub-skill checks it.

Top-level keys:

- `schema_version`
- `game` — build, install dir, content/game addon dirs, staging dir
- `hero` — display name, model asset, panorama key, model path, skeleton,
  hitboxes, attachments, camera, bodygroups, LODs
- `source` — format, mesh/armature object names, vertex groups, mapping module,
  axes
- `units` — source/target/scale
- `stock` — tri counts, budget, materials, portrait sizes, weapon bbox
- `paths` — Blender, compilers, Source 2 Viewer, VPK tool
- `tool_versions` — Blender, DMX addon, CSDK, Source 2 Viewer
- `gates` — `pending`, `pass`, `fail` or `skip` per stage

Use `scripts/project_config.py`:

```text
python project_config.py init project.json
python project_config.py check project.json
python project_config.py get project.json hero.model_asset
python project_config.py set project.json gates.rig_align pass
```

## Scripts

- Every script takes `--config <project.json>`.
- Explicit flags override individual config values for debugging.
- No script has a default user path, hero name, bone name or material name.
- Fail loudly when a required field is missing; do not silently substitute a
  default hero value.
- Write a JSON report next to the output so `deadlock-validate` can read it.
- Commands in the sub-skills are shown relative to the sub-skill's base
  directory. When running from your project directory, use the full script path
  or run from the skill directory.

## Blender

- Prefer `blender -b -P script.py -- ...` for measured or batched work. It is
  reproducible and does not disturb a live session.
- Use MCP/viewport only for looking: screenshots, bone display, side views.
- Blender 4.2+ extensions load as `bl_ext.user_default.<name>`.
  `wm.read_factory_settings` unloads them: factory reset first, then enable the
  addon, and do not call `read_homefile` afterwards.
- Apply all transforms; keep exactly one armature; keep the armature in rest
  pose for export.
- If the mesh has shape keys, translate every key block by the same offset as
  the basis, not only the basis.
- Decimate with the armature modifier temporarily disabled, then re-enable it.

## Material slots

Clearing `mesh.materials` invalidates `polygon.material_index`. Resolve every
polygon's new index into a list **before** clearing the slot list, then assign
the indices afterwards. Doing it in place silently collapses the mesh onto one
material.
