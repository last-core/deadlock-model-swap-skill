# Validation matrix

Run these before every in-game test. A gate is pass/fail; "looks fine" is not a
pass.

| Check | Tool | Pass |
|---|---|---|
| Skeleton identity | dump compiled `.vmdl_c`, compare to `stock_skeleton.json` | every stock bone present; 0 translation/rotation/scale differences; added bones listed |
| Hitboxes | compare compiled model nodes to stock | identical hitbox sets |
| Attachments/game data/camera | compare compiled model nodes to stock | identical values |
| Material references | `check_material_refs.py` | 0 missing |
| Addon tree | list files | only `.vmdl_c`, `.vmat_c`, `.vtex_c`; no sources |
| In-pak model size/CRC | `--vpk_dir` or `check_pak.py` | matches the file just compiled |
| Pak contents | `--vpk_dir` | expected model/material/portrait counts; no stock skeleton/clips/scripts |
| Compiled mesh bounds | DMX/report | shift/scale present; vertex count unchanged |
| Weights | per-material dominant histogram | 0 unweighted; sums 1.0; ≤4 influences; no region on an absurd bone |
| Hair/cloth | stress pose or clip | bends continuously; roots stay on the anchor |
| Weapon fit | fixed-camera render vs stock | same muzzle direction; upright; bbox centre close |
| Portrait names/sizes | list compiled files | compiled name == stock name; size == stock size; mips present |
| Animations | in-game | walks/runs/turns; not A-pose |
| Camera | in-game | same height/FOV as stock; not centred in the screen |
| Health bar | in-game | floats above the head |
| Ragdoll | in-game | falls without stretching |
| LODs | in-game, far away | same silhouette; no popping to a different shape |
| Sounds | in-game | footsteps/abilities still play |

## Skeleton identity details

- Compare bone **names** and **bind transforms**.
- Helper/pivot bone names may differ between dumpers; compare the transform.
- Adding bones is allowed; the stock bone entries must still match.
- The compiled skeleton array may be longer with added bones; that is not a
  failure.

## Pak details

- The compiled output must be copied into the **game** addon tree (what gets
  packed), not the **content** tree (what gets compiled).
- Check the in-pak size and CRC against the file just compiled. A size mismatch
  means you packed the previous build.
- Pack only the staging folder. Do not pack the content tree or the CSDK
  intermediate files.
- Close the game before installing; it locks the packed VPK.

## In-game checklist

- Walk, run, turn with the camera.
- Aim down sights; compare zoom and camera height to stock.
- Use every ability; check bodygroup/part switching.
- Die once; check the ragdoll.
- Check the health bar.
- Listen for footsteps and ability sounds.
- Check hero select and shop screens.
- Walk far away; check LODs.
- Check the portrait on the HUD, kill feed and minimap.
