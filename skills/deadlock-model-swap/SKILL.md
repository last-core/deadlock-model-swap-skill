---
name: Deadlock Model Swap
description: End-to-end Deadlock hero model swap for rigged MMD/PMX, FBX, or glTF sources. Orchestrates hidden sub-skills for setup, rig alignment, decimation, weights, pbr.vfx materials, DMX export, ModelDoc, AnimGraph 2 compile, weapon swap, portraits, and validation. Use for a full hero swap, a weapon-only swap, portrait replacement, or diagnosing an existing Deadlock swap.
---

# Deadlock Model Swap

This is the **hub** for a Deadlock hero model swap. The detailed procedures live
in hidden step sub-skills; this file owns the constraints, the pipeline, the
gates, and the routing.

Do not do the whole swap from this file alone. Load one sub-skill at a time,
finish its gate, then load the next one by its exact ID.

Install this folder together with the `deadlock-*` sibling sub-skill
directories; the hub loads them by ID. The sub-skills are intentionally hidden
from the model's automatic list, not missing.

## When to use

- Replace a hero's base model with a rigged source (MMD/PMX, FBX, glTF) while
  keeping the game's skeleton, animations, hitboxes and attachments.
- Swap a hero's weapon mesh.
- Replace hero portraits or icons.
- Diagnose an existing swap that "looks wrong".

## When not to use

- Props, maps, or texture-only reskins.
- A source model that is not rigged. This workflow retargets an existing skin;
  it does not rig from scratch.
- Animation replacement, gameplay changes, or anything that is not cosmetic.

## Quick start

Load the sub-skills in this order. Each one hands off to the next.

```text
0  deadlock-swap-setup          project.json + stock measurements
1  deadlock-rig-align           aligned .blend
2  deadlock-decimate            final destination topology
3  deadlock-weights             weighted .blend
4  deadlock-materials           .vmat / .vmat_c / .vtex_c
5  deadlock-export-dmx          .dmx per render mesh
   deadlock-weapon              optional: weapon .dmx (before modeldoc)
6  deadlock-modeldoc            .vmdl + CSDK compile
7  deadlock-animgraph2-compile  final .vmdl_c + VPK
   deadlock-portraits           optional: portrait .vtex_c
8  deadlock-validate            pass/fail report
```

Why **decimate before weights**: decimation changes topology. Retarget weights
onto the final mesh, not onto geometry that is about to change. Keep a copy of
the full-resolution source mesh; the weights step needs it.

## Hard constraints

Never break these. They are the difference between a cosmetic swap and a mod
that is unfair, unstable, or broken after an update.

1. **Keep the stock skeleton.** Never move, rename or delete an existing bone.
   Added cloth/hair bones are allowed, but every stock bone's name and bind
   transform must match stock. "Added bones" means extra entries, not changed
   stock entries.
2. **Keep the hitboxes.** Leave every hitbox set exactly as stock. Do not
   rescale, retarget or rebuild hitboxes.
3. **Copy attachments, game data and camera.** Camera offsets and FOV are
   gameplay values. Copy them exactly; never "improve" the camera.
4. **Match silhouette and size.** A smaller, thinner, taller, glowing,
   transparent or very dark model changes how easy the hero is to see and aim
   at. Keep proportions close to stock.
5. **Ship only compiled assets you changed.** Ship `.vmdl_c`, `.vmat_c`,
   `.vtex_c`. Never ship `.dmx`, `.vmdl`, `.vmdl_c` from a work file, the
   stock hero's `.vnmskel_c` or `.vnmclip_c`, `scripts/`, `gameinfo.gi`, or
   `image_compiler.vdata_c`.
6. **Keep the addon tree clean.** In the model folder: one final `.vmdl_c`
   plus the materials and textures it uses. Portrait textures live under
   `panorama/`. Anything else gets packed and may break the model.
7. **Respect licenses.** Fan models are usually local-use only. Do not
   distribute ripped or unlicensed assets.
8. **Do not skip gates.** A failed gate gets fixed before the next stage. Most
   expensive bugs are a stage-1 or stage-2 failure discovered in game.

## Pipeline

| Stage | Sub-skill | When | Artifact | Gate |
|---|---|---|---|---|
| 0 | `deadlock-swap-setup` | first | `project.json`, stock dumps | all facts measured; tools resolve |
| 1 | `deadlock-rig-align` | after setup | aligned `.blend` | compact features; body profile; feet; side view |
| 2 | `deadlock-decimate` | after align | optimized `.blend` | stock tri budget; no new holes; slots |
| 3 | `deadlock-weights` | after decimate | weighted `.blend` | 0 unweighted; sums 1; ≤4; histogram |
| 4 | `deadlock-materials` | after weights | `.vmat`, `.vmat_c`, `.vtex_c` | 0 missing refs; shader/flags |
| 5 | `deadlock-export-dmx` | after materials | `.dmx` per render mesh | bounds/scale; collections |
| 5b | `deadlock-weapon` | optional, before modeldoc | weapon `.dmx` | fixed-camera render; bbox; 100% bone |
| 6 | `deadlock-modeldoc` | after export (+ weapon) | `.vmdl` + CSDK compile | compiles; bindings intact |
| 7 | `deadlock-animgraph2-compile` | after modeldoc | `.vmdl_c`, VPK | animations play; in-pak size/CRC |
| 7b | `deadlock-portraits` | optional, any time after setup | portrait `.vtex_c` | compiled name/size match |
| 8 | `deadlock-validate` | after any gate / before game | report | all checks pass |

## How to load sub-skills

Every sub-skill is registered with `metadata.opencode/autoinvoke: false`, so it
does not clutter the model's available list. It is still loadable by exact ID:

```text
skill tool -> { "id": "deadlock-rig-align" }
```

The user can also jump directly with `@deadlock-weights`. The main skill remains
the user-facing entry point.

Load **one** sub-skill at a time. Do not load the whole set at once; each
sub-skill is written to be read immediately before its stage.

## Sub-skill contract

Every sub-skill follows the same shape:

- **Purpose** — one stage only.
- **Inputs / outputs** — files and fields in `project.json`.
- **Preconditions** — previous gate passed.
- **Agent actions** — file edits, scripts, CLI checks.
- **User actions** — GUI steps that cannot be automated.
- **Procedure** — ordered steps.
- **Gates** — measurable pass criteria.
- **Failure modes** — symptom, cause, fix.
- **Handoff** — exact next sub-skill ID.

The shared contract is `project.json`. The setup sub-skill writes it; every
later sub-skill reads it and updates its gate. No hero name, bone name, path or
measurement may be hardcoded outside `examples/`.

After a gate passes, record it:

```text
python scripts/project_config.py set project.json gates.<stage> pass
```

Use `fail` when a gate fails and `skip` only for an optional branch that is not
being done.

## Diagnosis routing

| Symptom | Load |
|---|---|
| Rest pose perfect, motion wrong; head offset | `deadlock-rig-align` |
| Hair stiff, snaps between segments | `deadlock-weights` |
| Cloth tears or opens into slits | `deadlock-decimate` (holes/rims), then `deadlock-weights` (deformation gaps) |
| Everything shiny / metallic / glossy | `deadlock-materials` |
| Checkerboard patches or solid red mesh | `deadlock-materials`, then `deadlock-modeldoc` |
| Model invisible | `deadlock-modeldoc` (material group) |
| Hair or face destroyed after decimation | `deadlock-decimate` |
| Weapon pitched, inverted or pointing backwards | `deadlock-weapon` |
| Hero stands in A-pose or does not turn | `deadlock-animgraph2-compile` |
| Camera sits in the middle of the screen | `deadlock-modeldoc` (attachments/camera); confirm Source 2 Viewer 20.0+ |
| Health bar at the feet | `deadlock-modeldoc` (attachments/game data) |
| Portrait change has no effect | `deadlock-portraits` |
| Packed model is the previous build | `deadlock-animgraph2-compile` (staging/in-pak CRC) |
| Compile dies with a `.vpk` in the working directory | `deadlock-animgraph2-compile` |
| Game still shows the stock hero | `deadlock-validate` (path, pak, staging) |

## Shared references

Read these from the main skill directory when a sub-skill points to them:

- `references/hard-constraints.md` — the rules above with rationale.
- `references/conventions.md` — units, axes, naming, folder layout, `project.json`.
- `references/stock-measurement.md` — what to measure before touching the mesh.
- `references/material-parameters.md` — `pbr.vfx` inputs, flags, packing, typos.
- `references/preview-caveats.md` — what Blender previews can and cannot tell you.
- `references/validation-matrix.md` — every check and its pass condition.
- `references/glossary.md` — hero key, model asset, panorama key, bodygroup, LOD, AnimGraph 2, staging.
- `scripts/project_config.py` — load, validate, query and initialize `project.json`.

Sub-skills use relative paths such as
`../deadlock-model-swap/references/conventions.md`; keep the sibling directories
together.

## Example case study

`examples/case-study/` is a worked MMD-to-hero swap. It keeps the project's
measurements and mapping decisions as a reference, but **no machine-specific
paths**. Read it when you need a concrete example of:

- a per-material/per-height alignment measurement;
- graded hair and cloth chains;
- material merging and boundary protection;
- a weapon fit in a bone-local frame.

Do not copy its constants into a new project. Measure the new hero.

## Version drift

Deadlock updates move paths, change compiler behavior and occasionally change
shader parameters. Record these in `project.json`:

- game build number;
- Blender and DMX addon versions;
- CSDK 12 version;
- Source 2 Viewer version (20.0+ for correct camera attachments);
- CS2 Workshop Tools presence.

After an update, re-run `deadlock-validate` before assuming the model is broken.

## Scope and limits

This skill covers the full pipeline from a rigged source to a packed VPK,
including ModelDoc and AnimGraph 2. ModelDoc and CS2 Workshop Tools are
GUI-first; the sub-skills automate what is safe to automate and give exact GUI
fallbacks for the rest. The agent cannot click for the user.

It does **not** cover making a character from scratch, rigging a mesh manually,
replacing animations, changing hitboxes, or gameplay modifications.
