# Original case-study scripts

These are the original one-off scripts from the case study. They are kept for
provenance and for the mapping/decimation/weapon logic, **not** as recommended
tools.

Known issues, fixed in the generic sub-skill scripts:

- `align_mesh_to_rig.py` adds a world-space offset to local vertex coordinates
  and only shifts the depth axis.
- `fit_gun.py` flips the weapon about world vertical, which is only correct
  when the weapon bone's up axis is world up.
- `rebuild_dense.py` prints a ratio against a hardcoded source triangle count
  and selects objects by vertex/bone count.
- `y_profile.py` hardcodes the hero armature and a hair material name.
- `export_dmx_scaled.py` defaults to a hero-specific collection name.
- `render_local_frame.py` hardcodes the camera scale and origin.

Use the current scripts in the step sub-skills instead:

- `deadlock-rig-align/scripts/`
- `deadlock-decimate/scripts/`
- `deadlock-weapon/scripts/`
- `deadlock-export-dmx/scripts/`
