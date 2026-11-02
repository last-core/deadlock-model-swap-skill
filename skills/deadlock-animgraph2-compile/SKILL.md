---
name: Deadlock AnimGraph 2 Compile
description: Internal step 7 of the Deadlock model-swap pipeline. Add NmSkeletonReference and AnimGraph 2 nodes in CS2 Workshop Tools, compile the final .vmdl_c, build the staging folder, pack the VPK, and verify in-pak size/CRC. Load from deadlock-model-swap.
metadata:
  opencode/autoinvoke: false
---

# Step 7 — AnimGraph 2, final compile and pack

## Purpose

Link the model to the hero's animation skeleton and graphs, compile the final
model in CS2 Workshop Tools, and pack only the compiled files.

## Inputs

- `work.vmdl` from ModelDoc.
- Stock AnimGraph 2 paths from setup:
  - `NmSkeletonReference`
  - `DefaultAnimGraph2`
  - `AnimGraph2` (ui)
- CSDK 12 game addon tree with materials.
- CS2 Workshop Tools install.

## Outputs

- `work.vmdl_c` compiled in CS2 Workshop Tools, renamed to the stock model name.
- `staging/` folder with only compiled assets at final paths.
- `pakNN_dir.vpk`.
- `pak_report.json` — in-pak size/CRC and contents.

## Preconditions

`gates.modeldoc == pass`.

## Agent actions

- Patch the graph/skeleton references into the `.vmdl`.
- Copy the `models` tree to the CS2 Workshop Tools addon.
- Invoke the CS2 compiler CLI with
  `../deadlock-modeldoc/scripts/compile_model.py` if available.
- Verify the compiled `.vmdl_c` exists and is newer than the source.
- Build the staging folder from CSDK materials + CS2 model.
- Run `check_pak.py`; compare in-pak size/CRC to the compiled file.
- List forbidden files in the staging folder.

## User actions

- Run CS2 Workshop Tools ModelDoc if the CLI cannot compile the graph links.
- Add `NmSkeletonReference`, `DefaultAnimGraph2`, `AnimGraph2` (ui) with the
  stock paths.
- Compile and confirm the model animates.
- Close the game before installing the VPK.

## Procedure

### 1. Copy the model

- Close CSDK 12.
- Start CS2 Workshop Tools and create/use an addon with the same name.
- Copy the `models` folder from the CSDK content addon into the CS2 content
  addon, preserving the folder structure.
- Keep the DMX files and material sources; ModelDoc cannot load meshes from
  another addon.

### 2. Add the references

Use the stock paths from the Data tab / setup dump:

- `NmSkeletonReference` → stock `.vnmskel` path.
- `DefaultAnimGraph2` → stock main graph path.
- `AnimGraph2` named `ui` → stock UI graph path.

The text patch helper can add the blocks:

```text
python ../deadlock-modeldoc/scripts/vmdl_patch.py add-animgraph work.vmdl \
    --skeleton <stock.vnmskel> \
    --default-graph <stock-hero.vnmgraph+hero.vnmgraph> \
    --ui-graph <stock-hero_ui.vnmgraph+hero.vnmgraph> \
    --out work.vmdl
```

Verify the node shape against the stock Data tab; if it differs, copy the stock
block in ModelDoc.

Do not guess the paths. Kelvin/Viscous/Ivy are examples of heroes whose skeleton
names do not follow the model name; always copy from the stock Data tab.

If ModelDoc reports a bad content path for animations, disable `AnimationList`.

### 3. Compile

- Compile in CS2 Workshop Tools.
- Ignore the error and red checkerboard materials in CS2; CS2 shaders differ
  from Deadlock's.
- Confirm the `.vmdl_c` is produced.
- If the CLI works, use it; otherwise use the GUI. The wrapper is
  `../deadlock-modeldoc/scripts/compile_model.py`.

### 4. Take only the compiled model

- Copy only `work.vmdl_c` from the CS2 game addon.
- Do not take the CS2 materials or sources.
- Rename it to the stock `.vmdl_c` name.

### 5. Stage

Build a clean staging folder:

- materials/textures from the CSDK 12 **game** addon tree;
- the model from the CS2 Workshop Tools **game** addon tree;
- no CSDK build of the work model;
- no `.dmx`, `.vmdl`, `.vnmskel_c`, `.vnmclip_c`, `scripts/`, `image_compiler.vdata_c`.

### 6. Pack

- Pack the staging folder into `pakNN_dir.vpk`.
- The packer may not exit after writing; check the file timestamp/size and the
  VPK footer, then kill it.
- Do not run the compiler with a `.vpk` in the working directory; it tries to
  mount it as a game pak.
- Close the game before installing; it locks the VPK.

### 7. Verify

- Run `check_pak.py`.
- Compare the in-pak model's size/CRC to the file just compiled.
- Check the expected file counts.
- Confirm no forbidden files.

## Gates

- AnimGraph 2 references point to the stock skeleton/graphs.
- Model compiles; no A-pose.
- In-pak model size/CRC matches the compiled file.
- Staging folder contains only allowed compiled assets.
- VPK footer/version valid; file size non-zero.
- `gates.animgraph2 == pass`.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Hero stands in A-pose | Missing/wrong AnimGraph 2 refs | Copy stock paths |
| Model does not turn | UI graph missing | Add `AnimGraph2` named `ui` |
| LODs break after CS2 compile | LODs rebuilt in the wrong addon | Rebuild/verify in the CS2 copy |
| Red checkerboards in CS2 | CS2 shaders differ | Ignore; verify in Deadlock |
| Game shows stock hero | Model not at stock path/name | Rename to the stock `.vmdl_c` |
| Packed old build | Staged from content tree or old file | Check in-pak size/CRC |
| Packer "hangs" | Packer does not exit | Check file/footer, then kill |
| Compile dies on a `.vpk` | VPK in the working directory | Change cwd |

## Handoff

If portraits are being replaced, load `deadlock-portraits`. Then load
`deadlock-validate`.
