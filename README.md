# Deadlock Model Swap — OpenCode Skill Pack

An [OpenCode](https://opencode.ai) skill pack for turning a rigged third-party
model (MMD/PMX, FBX, glTF) into a playable Deadlock hero model swap. It covers
the full path from stock measurement through rig alignment, weights, materials,
DMX export, ModelDoc, AnimGraph 2, VPK packing, weapon swaps, portraits, and
validation.

The pack is built around a **hub-and-spoke** design:

- **`deadlock-model-swap`** is the user-facing hub. It owns the hard
  constraints, the pipeline, the gates, and the diagnosis routing.
- The **11 step sub-skills** are hidden from OpenCode's automatic skill list.
  The hub loads them by exact ID, one stage at a time, so each stage gets a
  focused context and a measurable gate.

## Requirements

| Tool | Why |
|---|---|
| [OpenCode](https://opencode.ai) V2 | Skill host |
| Blender | Mesh, rig, weights, DMX export |
| Valve DMX addon (`io_scene_valvesource2` or `bl_ext.user_default.io_scene_valvesource2`) | DMX import/export |
| Source 2 Viewer **20.0+** | Stock extraction; older versions decompile camera attachments wrong |
| CSDK 12 | Materials and ModelDoc |
| CS2 Workshop Tools | Final AnimGraph 2 compile |
| Python 3.10+ | Helper scripts |
| Pillow | Flat maps and portrait staging |
| A VPK packer | Packaging the mod |

## Install

### Global (all projects)

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\opencode\skills" | Out-Null
Copy-Item -Recurse -Force .\skills\* "$env:USERPROFILE\.config\opencode\skills\"
```

macOS / Linux:

```bash
mkdir -p ~/.config/opencode/skills
cp -R skills/* ~/.config/opencode/skills/
```

### Project-local

```bash
mkdir -p .opencode/skills
cp -R skills/* .opencode/skills/
```

Reload OpenCode (or run `/reload`) if the skill list does not update
immediately.

## Use

Invoke the hub:

```text
@deadlock-model-swap
```

The hub loads the sub-skills in order. You can also jump directly to one stage,
for example:

```text
@deadlock-weights
```

The sub-skills are registered with `metadata.opencode/autoinvoke: false`, so
they are intentionally absent from the model's automatic skill list. This keeps
the list clean and makes the hub the single entry point. They are still
loadable by exact ID.

## Pipeline

| Stage | Sub-skill | Artifact |
|---|---|---|
| 0 | `deadlock-swap-setup` | `project.json`, stock measurements |
| 1 | `deadlock-rig-align` | aligned `.blend` |
| 2 | `deadlock-decimate` | final destination topology |
| 3 | `deadlock-weights` | weighted `.blend` |
| 4 | `deadlock-materials` | `.vmat`, `.vmat_c`, `.vtex_c` |
| 5 | `deadlock-export-dmx` | `.dmx` per render mesh |
| 5b | `deadlock-weapon` (optional) | weapon `.dmx` |
| 6 | `deadlock-modeldoc` | `.vmdl` + CSDK compile |
| 7 | `deadlock-animgraph2-compile` | final `.vmdl_c` + VPK |
| 7b | `deadlock-portraits` (optional) | portrait `.vtex_c` |
| 8 | `deadlock-validate` | pass/fail report |

**Decimate before weights.** Decimation changes topology; retarget weights onto
the final mesh, not onto geometry that is about to change. Keep the
full-resolution source mesh for the weights stage.

## The `project.json` contract

Every stage reads and updates one `project.json`:

- hero/model/panorama keys;
- source format, mesh/armature names, axes and units;
- stock skeleton, meshes, materials, hitboxes, attachments, camera, bodygroups,
  LODs and AnimGraph 2 paths;
- triangle budget, portrait sizes and weapon bounding box;
- tool paths and versions;
- per-stage gate status.

No stage hardcodes a hero name, bone name, material name, measurement or machine
path. That is what keeps the workflow reusable across heroes.

The shared helper is `skills/deadlock-model-swap/scripts/project_config.py`:

```text
python project_config.py init project.json
python project_config.py check project.json
python project_config.py get project.json hero.model_asset
python project_config.py set project.json gates.rig_align pass
```

## What is covered

- Mesh-to-rig alignment using per-material/per-height profiles and compact
  features, not nearest-vertex guesses.
- Source-group weight retargeting, graded hair/cloth chains, Laplacian smoothing
  and a four-influence cap.
- Budgeted decimation with face and garment-rim protection.
- Deadlock `pbr.vfx` materials, feature flags, packed texture inputs, flat
  normal/roughness maps and texture-reference checks.
- Unit conversion, collection organisation and DMX export.
- ModelDoc cleanup: removing AnimGraph 2/Skeleton nodes, render meshes,
  bodygroups, ragdoll, LODs, `DefaultMaterialGroup`, attachments, camera and
  hitboxes.
- AnimGraph 2 references, CS2 Workshop Tools final compile, staging and VPK
  packing.
- Weapon fitting in the weapon bone's local frame.
- Portraits through both the canonical `image_compiler.vdata` route and a
  `.vtex` descriptor, with a rename to the stock compiled name.
- Cross-cutting validation: skeleton identity, material references, weights,
  bounds, weapon fit, portrait names and in-pak size/CRC.

## What is not covered

- Making a character from scratch or rigging a mesh manually.
- Replacing animations.
- Changing hitboxes or camera values.
- Gameplay modifications.
- Props, maps or texture-only reskins.

## Repository layout

```text
skills/
├── deadlock-model-swap/          # hub + references + case study
│   ├── SKILL.md
│   ├── references/
│   ├── scripts/project_config.py
│   └── examples/case-study/
├── deadlock-swap-setup/
├── deadlock-rig-align/
├── deadlock-decimate/
├── deadlock-weights/
├── deadlock-materials/
├── deadlock-export-dmx/
├── deadlock-modeldoc/
├── deadlock-animgraph2-compile/
├── deadlock-weapon/
├── deadlock-portraits/
└── deadlock-validate/
```

The case study in `skills/deadlock-model-swap/examples/case-study/` is a
sanitized record of a real MMD-to-hero swap. It keeps measurements and mapping
decisions, but no machine-specific paths. Its original one-off scripts are under
`scripts/original/` for provenance; the maintained versions are the generic
scripts in the step skills.

## Notes and limitations

- ModelDoc and CS2 Workshop Tools are GUI-first. The skill automates safe text
  edits and CLI compiles, then gives an exact GUI fallback for the rest. The
  agent cannot click for you.
- The example `project.json` intentionally has `stock.body_tris: 0` because the
  stock count was not recorded. `project_config.py check` reports that until you
  measure it.
- `compare_skeleton.py` needs the compiled skeleton dump converted to the
  `stock_skeleton.json` shape produced by `measure_stock.py`.
- No game assets, models, textures or VPKs are included. The repository is
  instructions and tooling only.

## Contributing

Issues and pull requests are welcome. Please keep the hub/sub-skill split:

- hub-level rules and routing go in `deadlock-model-swap/SKILL.md`;
- stage-specific procedure goes in the matching sub-skill;
- shared conventions go in `deadlock-model-swap/references/`;
- reusable scripts take `--config project.json` and have no hero-specific
  defaults.

## License

MIT — see [LICENSE](LICENSE).

The skill text and scripts are original work; game assets are not included.
Deadlock is a trademark of Valve Corporation; this project is not affiliated
with Valve.

## Disclaimer

Fan models are usually licensed for local use only. Do not distribute ripped or
unlicensed assets. Follow the game's modding rules for visibility, silhouette,
glow, transparency and size.
