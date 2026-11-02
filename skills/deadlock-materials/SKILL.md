---
name: Deadlock Materials
description: Internal step 4 of the Deadlock model-swap pipeline. Build Deadlock pbr.vfx materials, feature flags, flat normal/roughness maps, compile them, and verify every texture reference. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 4 — Materials

## Purpose

Build materials that compile and resolve in game. A single dangling texture
reference is invisible until the model is loaded.

## Inputs

- `weighted.blend` from step 3.
- Material names and textures from `project.json`.
- Stock material dumps for reuse.
- Compiler paths from `project.json`.

## Outputs

- `.vmat` sources.
- Compiled `.vmat_c` and `.vtex_c` in the game addon tree.
- `material_refs_report.json` — 0 missing references.

## Preconditions

`gates.weights == pass`.

## Agent actions

- Create or edit `.vmat` files.
- Generate flat normal/roughness maps.
- Compile with CSDK 12 via
  `../deadlock-modeldoc/scripts/compile_model.py` (it accepts `.vmat` too).
- Run `check_material_refs.py` after every rebuild.
- List every material name for the ModelDoc `DefaultMaterialGroup` handoff.

## User actions

- Confirm the material looks right in the Material Editor / Source 2 Viewer.
- Check the stock material if reusing one.

## Procedure

### 1. Shader and flags

- Set `"shader" "pbr.vfx"`.
- Add `F_USE_NPR_LIGHTING` and `F_USE_STATUS_EFFECTS_PROXY`.
- Keep `F_CLOAK` if the stock hero uses it.
- Use `F_ALPHA_TEST` for hair cards/lace; keep cutouts small.
- Do not add `F_UNLIT`, `F_SELF_ILLUM`, `F_TRANSLUCENT`, `F_ADDITIVE_BLEND`,
  or outline overrides.

A new material may default to `environment_texture_set`; check the shader every
time.

### 2. Texture inputs

- Use numbered inputs: `TextureColor1`, `TextureNormal1`, `TextureRoughness1`,
  `TextureMetalness1`, `TextureAmbientOcclusion1`, `TextureTintMask1`, etc.
- `TextureNprTramsissiveColor1` is intentionally misspelled in the shader; do
  not correct it.
- `TextureAltTextureReveal` is the un-numbered exception.
- Un-numbered names are silently ignored and your albedo becomes a flat
  constant.

### 3. Texture naming and sizes

- Use suffixes the Material Editor expects: `_color`, `_normal`, `_rough`,
  `_metal`, `_ao`, `_mask`, `_trans`, `_sheen`, `_detail`.
- Power-of-two sizes; keep the stock size where possible.
- Source images may be PNG, TGA, PSD or JPG.

### 4. Flat maps

Do not point normal/roughness at `materials/default/*`. The compiler merges
normal + roughness into a generated texture under the default path; that file
may not exist and the reference dangles.

Run `make_flat_maps.py` to write:

- flat normal RGB `(128, 128, 255)`;
- flat roughness greyscale ~`216/255` (0.85, soft matte).

Ship both so the merged texture is emitted under your addon path.

### 5. Compile

```text
python ../deadlock-modeldoc/scripts/compile_model.py --input material.vmat \
    --compiler <CSDK_RESOURCECOMPILER> --output material.vmat_c
```

- Compile the `.vmat` with CSDK 12.
- Run `check_material_refs.py` with the addon materials directory and the game
  directory.
- Decompile each `.vmat_c`, collect `g_t*` paths, and check every one resolves
  to your packed files or the game.
- Do not accept "it will resolve at runtime" for a missing texture.

### 6. Handoff to ModelDoc

List every material name exactly as it appears in Blender. The ModelDoc
`DefaultMaterialGroup` needs one slot per name.

- No `.001` suffixes.
- Resolve polygon indices before clearing the Blender slot list.
- Reuse stock materials where the texture matches.

## Gates

- Shader is `pbr.vfx`.
- `F_USE_NPR_LIGHTING` and `F_USE_STATUS_EFFECTS_PROXY` set.
- 0 missing texture references.
- Every material name has a slot plan for `DefaultMaterialGroup`.
- No `.001` material names.
- No flat albedo caused by an un-numbered input.
- `gates.materials == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Everything shiny/metallic | Dangling normal/roughness default path | Ship flat maps under your path |
| Checkerboard detail | Missing texture | Fix path or add the texture |
| Flat albedo | Un-numbered shader input | Use `TextureColor1` etc. |
| Material ignored | Not in `DefaultMaterialGroup` | Add the slot |
| Solid red mesh | Missing material group/slot | Add `DefaultMaterialGroup` |
| Everything one material | Slot list cleared before resolving indices | Resolve first |
| Glow/transparency | Wrong flags | Remove unlit/self-illum/translucent |
| Texture not in picker | Wrong suffix | Rename with `_color`, `_normal`, etc. |

## Handoff

Load `deadlock-export-dmx`.
