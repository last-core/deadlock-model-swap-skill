# Case study: MMD source to a Deadlock hero

This is a worked example from a real MMD-to-hero swap. It is here to show the
shape of the measurements and the mapping decisions, not to provide constants
for a new project. **No machine-specific paths are included.**

The original project used a source model with hundreds of MMD vertex groups and
a target hero skeleton with roughly 160 bones. The model was a stylised,
high-density character with hair, a long scarf/ribbon, a garment with panelled
edges, and a separate weapon mesh.

`project_config.py check` on this example intentionally reports
`stock.body_tris` because the stock hero's triangle count was not recorded. Set
that field from the stock model before using the example as a live config.

## What was measured

| Measurement | Reference value |
|---|---|
| Mesh-to-rig depth offset | body bands around `y ~ -0.31`; eyes/teeth/hands/ankles all about `0.30` in front of their bones |
| Eye geometry vs eye bone | about `0.295` |
| Teeth vs jaw/teeth bones | about `0.296` |
| Hands vs hand bones | about `0.33` |
| Ankles vs ankle bones | about `0.31` |
| Correction applied | pure depth translation of the mesh vertices, about `0.30` |
| Source full-resolution mesh | 235,362 vertices / 263,003 triangles |
| Source material count | 46 MMD materials |
| Decimation ratio | 0.70 of full resolution |
| Hair coverage | roughly 22% of the mesh, about 75k vertices |
| Hair vertical span | scalp `z ~ 2.19` to tip `z ~ 0.83` |
| Bangs vertical span | `z ~ 2.40` to `z ~ 2.17` |
| Scarf/ribbon span | `z ~ 1.99` to `z ~ 0.17` |
| Previous weight pass | 92.6% single-influence |
| New weight pass | about 70% single-influence, mean ~1.4 |
| Materials using the default normal path | 7 of 11 |
| Flat roughness | 216/255 (~0.85) |
| Stock weapon local bbox | lo `[-0.041, -0.205, -0.505]`, hi `[0.041, 0.207, 0.737]` |
| Source weapon length | 1.640 m along its own `+Y` |
| Portrait card size | 240 x 320 |
| Portrait map icon | 50 x 50 |
| Stock card file size | 411,668 bytes (RGBA8 + mips) |

These numbers are **not defaults**. Measure the new hero and write the results
to `project.json`.

## Alignment lesson

The mesh sat about `0.30` away from the skeleton in the depth axis and still
rendered correctly in the rest pose, because rest pose applies no deformation.
The failure only appeared in animation: the head read as offset, limbs folded
oddly, and cloth swung on a long lever.

The measurement that worked was:

- per-material, per-height-band profile of the **body** materials;
- a narrow side window to exclude arms;
- the **median** depth per band;
- compare with the interpolated spine centre at that height.

The measurement that lied was nearest-vertex-to-bone: hair, straps and cape
geometry sit on the bones, so every bone looked close. Eye geometry vs eye bones
was the cleanest small-feature check.

The fix translated the **mesh vertices**, never the bones. The object transform
stayed identity so the DMX export path was unchanged. Z was left alone because
the feet were on the ground; the depth error was a translation, not a
proportion error.

## Weighting lessons

- The source's own vertex groups were retargeted; surface transfer alone
  scrambled regions such as eyes onto hair bones.
- Hair and the scarf needed **graded chains**, not one bone per group.
- Hair progress was mapped monotonically by height (a good arc-length proxy
  because the strands hang vertically). The root was feathered back to the head
  so the roots could not peel off the scalp.
- The scarf cloth material carried thousands of triangles while the scarf bone
  groups carried only hundreds of vertices. Mapping by group did almost
  nothing; the cloth was rebound by **material** and forced onto the ribbon
  chain for destination vertices whose nearest source face was that material.
- Smoothing was Laplacian over mesh topology, then normalised and capped to
  four influences. Separate shells stayed independent, which was intended.
- The per-material dominant-bone histogram caught whole regions on the wrong
  bone.

## Decimation lessons

- The budget came from the stock hero's triangle count, not from file size.
- Blender's Decimate vertex group selects the vertices that **may collapse**.
  The protect mask marked the face and the open boundary loops of panelled
  garment materials; the modifier used `invert_vertex_group = True`.
- Hair was left free because it was the bulk of the mesh and decimated
  harmlessly. Protect hair if the silhouette or alpha cards thin out.
- A dense mesh reports many boundary edges because UV seams duplicate vertices.
  Welding a copy by a small scene-unit threshold separates fake seams from real
  holes.
- Material indices were resolved into a list **before** clearing the material
  slots. Clearing first collapsed everything onto one slot.

## Material lessons

- Seven of eleven materials pointed normal/roughness at `materials/default/*`.
  The compiler emitted a merged `g_tNormalRoughness` under the default path and
  the reference dangled. Symptoms were checkerboard detail and broken specular.
- Shipping flat normal/roughness maps put the merged texture under the addon
  path.
- The shader inputs are numbered. Un-numbered names are silently ignored.
- `TextureNprTramsissiveColor1` is intentionally misspelled in the shader.
- `TextureAltTextureReveal` is the un-numbered exception.

## Weapon lessons

- The stock weapon's bounding box was measured in the weapon bone's local
  frame. The fitted points had to be mapped back through the bone:
  `world = armature_world @ bone_matrix @ local`.
- Writing bone-space coordinates out as world coordinates dropped the bone's
  rotation and produced a pitched, inverted weapon.
- The source barrel pointed the opposite way from the stock muzzle. The
  original fix was a 180-degree flip about world vertical; the generic
  `fit_weapon.py` instead flips about the **bone-local up axis**, which is
  correct even when the weapon bone is rotated.
- The stock bounding box is a reference frame, not a guarantee of grip
  alignment. Measure the grip/attachment point as well.

## Portrait lessons

- Portrait sizes are per image type; the card and map icon are not universal.
- The stock names often end in `_psd` even when the source image is a PNG.
- The canonical CSDK route is `image_compiler.vdata` plus a rename to the stock
  compiled name. A `.vtex` descriptor named after the stock asset is an
  alternative.
- `resourcecompiler` does accept PNG source images; the issue is standalone UI
  texture naming/compilation, not the PNG format.

## Script map

The original one-off scripts are represented by the generic sub-skill scripts:

| Original idea | Generic script |
|---|---|
| `y_profile.py` | `deadlock-rig-align/scripts/measure_alignment.py` |
| `align_mesh_to_rig.py` | `deadlock-rig-align/scripts/align_mesh.py` |
| `rebuild_dense.py` | `deadlock-decimate/scripts/decimate.py` |
| `retarget_weights2.py` | `deadlock-weights/scripts/retarget_weights.py` |
| `make_flat_maps.py` | `deadlock-materials/scripts/make_flat_maps.py` |
| `check_material_refs.py` | `deadlock-materials/scripts/check_material_refs.py` |
| `export_dmx_scaled.py` | `deadlock-export-dmx/scripts/export_dmx.py` |
| `fit_gun.py` | `deadlock-weapon/scripts/fit_weapon.py` |
| `render_local_frame.py` | `deadlock-weapon/scripts/render_local_frame.py` |
| `stage_portraits.py` | `deadlock-portraits/scripts/stage_portraits.py` |
| `make_portrait_vtex.py` | `deadlock-portraits/scripts/make_portrait_vtex.py` |
| `mmd_map.py`, `mmd_map2.py` | kept here as MMD mapping examples |

## Known bugs in the original scripts

These were fixed in the generic versions:

- `check_material_refs.py` used an undefined variable `base` where it meant
  `path`; every run raised `NameError`.
- `align_mesh_to_rig.py` computed a world-space offset but added it to local
  vertex coordinates; it also only shifted the depth axis.
- `fit_gun.py` flipped the weapon about world vertical, which is only correct
  when the weapon bone's up axis is world up.
- `rebuild_dense.py` printed a ratio against a hardcoded `263003.0`.
- `rebuild_dense.py` selected the mesh by vertex count and the armature by a
  hardcoded bone count.
- `retarget_weights2.py` printed unweighted vertices but did not fix or fail on
  them, and selected the source mesh by a `>500` vertex-group threshold.
