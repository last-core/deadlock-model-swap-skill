---
name: Deadlock Portraits
description: Internal optional step of the Deadlock model-swap pipeline. Replace Deadlock hero portraits/icons at the stock sizes using image_compiler.vdata or a .vtex descriptor, renaming to the stock compiled names. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Optional — Portraits and icons

## Purpose

Replace hero portraits at the exact stock names and sizes. The game only loads a
file with the exact stock compiled name.

## Inputs

- Artwork for the variants being replaced.
- `project.json` with `stock.portrait_sizes` and the panorama key.
- Stock portrait list from `panorama/images/heroes/`.

## Outputs

- Portrait `.vtex_c` files at the stock paths/names.
- `portrait_report.json` — compiled name, size, format, mips.

## Preconditions

`gates.setup == pass` (stock sizes/names measured). Can run any time after that.

## Agent actions

- List stock portrait names and sizes.
- Cover-crop and resize the artwork.
- Generate the `image_compiler.vdata` list or `.vtex` descriptors.
- Compile and rename to the stock names.
- Verify the compiled files.

## User actions

- Provide the artwork.
- Confirm the crop/framing.
- Check the portrait in game.

## Procedure

### 1. Measure the stock assets

List `panorama/images/heroes/` and record for each variant:

- exact compiled name;
- width and height;
- format and mips.

Common variants:

```text
<key>_card_psd.vtex_c
<key>_card_critical_psd.vtex_c
<key>_card_gloat_psd.vtex_c
<key>_mm_psd.vtex_c
<key>_sm_psd.vtex_c
<key>_vertical_psd.vtex_c
```

Sizes vary by hero and by image type. Do not assume one size for all.

Only replace the variants you have artwork for. The others stay stock and will
visibly mismatch; list them for the user.

### 2. Stage the artwork

- Use a **cover crop** to the target aspect, not a plain resize; a plain resize
  stretches faces.
- Keep the face in frame; centre-cropping a tall portrait can cut the top of the
  head. Adjust the crop origin if needed.
- Preserve alpha; the card portraits need it.
- Export PNG at the exact target size.

### 3. Route A — `image_compiler.vdata` (canonical CSDK route)

1. Put the PNGs in `content/<addon>/panorama/images/heroes/`.
2. Add one line per image to `panorama/image_compiler.vdata`:

```text
panorama:"file://{images}/heroes/<name>.png"
```

3. Compile the `image_compiler` asset in the Asset Browser (Full recompile).
4. The compiler may output `<name>_png.vtex_c`. Rename a copy to the stock
   compiled name, for example `<name>_png.vtex_c` -> `<key>_card_psd.vtex_c`.
5. Do not ship `image_compiler.vdata_c`.

### 4. Route B — `.vtex` descriptor

1. Create a `CDmeVtex` descriptor named after the **stock compiled asset**:
   `<key>_card_psd.vtex` -> `<key>_card_psd.vtex_c`.
2. Set:
   - `m_outputFormat = "RGBA8888"`
   - `m_colorSpace = "srgb"`
   - mips on (`m_bNoLod = 0`)
3. `m_fileName` must point at the PNG relative to the addon content root.
   Keyvalues2 strings escape backslashes; use doubled backslashes or forward
   slashes.
4. Compile with `resourcecompiler`.
5. Verify the compiled name matches the stock asset.

PNG is a valid source image. The issue with standalone UI textures is naming and
compilation, not the PNG format.

### 5. Verify

- Compiled name equals the stock name exactly.
- Width/height equal the stock size.
- Format/mips match the stock asset.
- The file is in the staging folder at the final path.
- The game is not showing a cached older image.

## Gates

- Every replaced variant has the exact stock compiled name.
- Every replaced variant has the exact stock size.
- Alpha is preserved.
- Mips/format match.
- Files are in the staging folder.
- `gates.portraits == pass` (or `skip` if no portraits).

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Portrait unchanged | Compiled name != stock name | Rename to the stock `_psd` name |
| Face stretched | Plain resize | Cover-crop to target aspect |
| Head cut off | Centre crop on a tall image | Adjust crop origin |
| `Failed to find compiler for file` | Standalone image not in a compile list/descriptor | Use `image_compiler.vdata` or a `.vtex` descriptor |
| `Error reading texture "panorama"` | Keyvalues2 backslashes not escaped | Double them or use forward slashes |
| Old image in game | Cache/wrong pak | Recheck the pak and restart |
| Some variants mismatch | Only some variants replaced | Replace the rest or document the mismatch |

## Handoff

Load `deadlock-validate`.
