# Shared scripts

This folder holds only cross-stage tooling.

- `project_config.py` — initialise, validate, query and update `project.json`.

Step-specific scripts live beside their sub-skill:

- `deadlock-swap-setup/scripts/`
- `deadlock-rig-align/scripts/`
- `deadlock-decimate/scripts/`
- `deadlock-weights/scripts/`
- `deadlock-materials/scripts/`
- `deadlock-export-dmx/scripts/`
- `deadlock-modeldoc/scripts/`
- `deadlock-animgraph2-compile/scripts/`
- `deadlock-weapon/scripts/`
- `deadlock-portraits/scripts/`
- `deadlock-validate/scripts/`

The original case-study scripts are in
`../examples/case-study/scripts/original/` for provenance only.

## Config quick reference

```text
python project_config.py init project.json
python project_config.py check project.json
python project_config.py get project.json hero.model_asset
python project_config.py set project.json gates.rig_align pass
```
