# Material parameters

Deadlock hero materials use `pbr.vfx`. The Material Editor may start a new
material on `environment_texture_set`; always check that the shader reads
`pbr.vfx`.

## Feature flags

At minimum, every hero material needs:

- `F_USE_NPR_LIGHTING` — Deadlock's stylized rim/banded lighting.
- `F_USE_STATUS_EFFECTS_PROXY` — lets status effects draw over the mesh.

Keep stock flags where they matter:

- `F_CLOAK` — invisibility/refraction; never remove it from a stealth hero.
- `F_ALPHA_TEST` — hair cards and lace. Keep cutouts small.
- `F_RENDER_BACKFACES` — only if the stock material uses it.

Do not add `F_UNLIT`, `F_SELF_ILLUM`, `F_TRANSLUCENT`, `F_ADDITIVE_BLEND`, or
outline overrides to a hero material.

## Texture inputs

Most inputs are numbered. Un-numbered names are silently ignored.

| Input | Packed into | Notes |
|---|---|---|
| `TextureColor1` + `TextureMetalness1` (alpha) | `g_tColor` | BC7 |
| `TextureColor1` + `TextureTranslucency1` (alpha) | `g_tColor` | translucent/alpha-test only |
| `TextureNormal1` + `TextureRoughness1` | `g_tNormalRoughness` | BC7 |
| `TextureAmbientOcclusion1` | `g_tAmbientOcclusion` | BC4 |
| `TextureTintMask1` (red) + `TextureRimLightMask1` (green) | `g_tTintMaskRimLightMask` | BC5 |
| `TextureNprOutlineMask1` | `g_tNprOutlineMask` | BC4 |
| `TextureNprTramsissiveColor1` | `g_tNprTransmissiveColor` | BC7 |
| `TextureSelfIllumMask1` | `g_tSelfIllumMask` | BC4 |
| `TextureSheenColor1` + `TextureSheenRoughness1` | `g_tSheen` | BC7 |
| `TextureDetail` + `TextureDetailMask` | `g_tDetail`, `g_tMasks1` | BC7, BC4 |
| `TextureAltColor1` + `TextureAltTextureReveal` | `g_tAltColor_Reveal` | BC7 |

Two spelling traps:

- **`TextureNprTramsissiveColor1` is intentionally misspelled in the shader.**
  Do not "fix" it to `Transmissive`; the misspelled name is the one that works.
- **`TextureAltTextureReveal` is not numbered.** It is the exception to the
  numbered-input rule.

## Texture naming and sizes

The Material Editor file picker filters by suffix:

- `_color`
- `_normal`
- `_rough`
- `_metal`
- `_ao`
- `_mask`
- `_trans`
- `_sheen`
- `_detail`
- `_detailmask`
- `_blend`

Use power-of-two sizes. Keep the stock texture size where possible; hero body
textures are commonly 2048x2048, weapon textures smaller. Check the stock asset
in Source 2 Viewer.

Source images may be PNG, TGA, PSD or JPG. A source image that is not named with
the expected suffix may not appear in the picker; rename it, or switch the
picker filter to all images.

## Flat normal and roughness

Do not point normal/roughness at `materials/default/*`. The compiler merges
normal + roughness into one generated texture named after the default path with
a hash, for example:

```text
g_tNormalRoughness = materials/default/default_normal_tga_<hash>.vtex
```

That file may not exist in the game, leaving a dangling reference. Symptoms are
the checkerboard pattern over details and wildly wrong specular.

Ship your own flat maps so the merged texture is emitted under your addon path:

- flat normal: RGB `(128, 128, 255)`
- flat roughness: greyscale around `216/255` (0.85, soft matte)

`deadlock-materials/scripts/make_flat_maps.py` writes both.

## Material group

Every material name used in Blender must be added to the ModelDoc
`DefaultMaterialGroup` and mapped to a `.vmat`. A missing slot renders as a
solid red mesh or the error material.

- Material names must not end in `.001`.
- Resolve polygon material indices before clearing the Blender slot list.
- Reuse stock materials where the texture matches.
- Run `check_material_refs.py` after every material rebuild; 0 missing
  references is the gate.
