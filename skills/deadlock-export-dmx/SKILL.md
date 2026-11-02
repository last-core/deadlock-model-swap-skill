---
name: Deadlock Export DMX
description: Internal step 5 of the Deadlock model-swap pipeline. Convert units to inches, organise one collection per render mesh, and export DMX files for ModelDoc. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 5 — Export DMX

## Purpose

Turn the Blender scene into the DMX files ModelDoc expects: correct units,
correct collections, correct render-mesh names.

## Inputs

- `weighted.blend` with materials.
- `project.json` with units, axes and render-mesh names.
- Stock bounds for comparison.

## Outputs

- One `.dmx` per render mesh in `dmx/`.
- `export_report.json` — file names, bounds, vertex counts, scale.

## Preconditions

`gates.materials == pass`.

## Agent actions

- Run `export_dmx.py` with `--config`.
- Check the report: scale, bounds, collection contents, file names.
- Compare the body bounds against stock.

## User actions

- Confirm the exported mesh names match the stock render meshes.
- Confirm the armature is in rest pose and all transforms are applied.

## Procedure

### 1. Units

- Source 2 uses inches. From a meter scene, scale by **39.37**.
- Scale the **mesh and armature together**.
- Apply all transforms.
- If the scene is already in inches, do not scale again. Double-scaling is the
  classic "mesh collapses to a point" or "model is tiny in ModelDoc" bug.
- Check the bounds after scaling.

### 2. Collections

- One collection per render mesh.
- The body collection contains the mesh **and** the armature. Pass `--body` to
  `export_dmx.py` when exporting it.
- A weapon/accessory collection contains only that mesh.
- Collection names become DMX file names, so match the stock render-mesh names.
- Keep the armature in exactly one collection.
- No lights, reference objects or stock meshes in the export collections.

### 3. DMX settings

- Format: `22_modeldoc`.
- Encoding: `9` (binary).
- Export format: `DMX`.
- Export path: the addon's `dmx/` folder.
- Export by collection name; renaming the object is not enough.

### 4. Parenting

The stock pipeline expects every mesh parented to the armature. Keep the
armature modifier and the parent relationship.

If your exporter double-applies the parent transform and the bounds come out
wrong, unparent with `CLEAR_KEEP_TRANSFORM`, export, and verify the armature
modifier still works. Do not unparent by default.

### 5. Sanity checks

- Bounds: compare to stock; the shift/scale must be present.
- Vertex count: unchanged from the weighted mesh.
- Z range: feet on the ground; head at the expected height.
- File names: exactly the stock render-mesh names.
- No source files in the game addon tree.

### 6. Handoff to ModelDoc

Tell the next stage:

- the DMX file names;
- the collection each mesh came from;
- the body triangle count;
- any mesh that is a weapon/accessory.

## Gates

- Units/scale correct; no double scale.
- Mesh and armature scaled together.
- One collection per render mesh; armature only in the body collection.
- DMX files written and non-empty.
- Bounds and vertex count match the report.
- `gates.export == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Mesh collapses to a point | Only one of mesh/armature scaled | Scale both |
| Model tiny/huge in ModelDoc | Double scale or wrong units | Recheck `units.scale`; apply once |
| DMX writes nothing | Collection missing or empty | Create the collection; put mesh + armature in it |
| Wrong file name | Collection name differs | Rename the collection to the stock render-mesh name |
| Mesh deformed at rest | Armature not in rest pose | Set rest pose before export |
| Weapon offset | Weapon in the body collection | Separate weapon collection |
| Non-uniform scale warning | Object scale not applied | Apply all transforms |

## Handoff

If the swap includes a weapon, load `deadlock-weapon` **before**
`deadlock-modeldoc`. Otherwise load `deadlock-modeldoc`.
