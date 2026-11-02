# Glossary

**Hero key** — the panorama/UI key for a hero. It is not always the model asset
name. List `panorama/images/heroes/` and confirm.

**Model asset** — the internal name used by the model path, skeleton and
materials, for example `models/heroes_wip/<asset>/<asset>.vmdl`.

**Panorama key** — the prefix used by portrait files, for example
`<key>_card_psd.vtex_c`.

**Render mesh** — one visible mesh inside a `.vmdl`. A hero usually has a body
and one or more weapon/accessory meshes. Each render mesh is exported as its own
DMX and named to match the stock render mesh.

**Bodygroup** — a switchable set of meshes with named choices. Rebuild it with
the stock names; bodygroups are referenced by game events.

**LOD** — a simplified mesh shown at distance. Rebuild the LOD group and keep
the stock switch thresholds where possible.

**Hitbox set** — the collision shapes used for hit detection. Copy exactly; do
not rebuild.

**Attachment** — a named point or bone parent used by the game for weapons,
muzzle effects, camera, health bar, etc. Copy from stock.

**Game data** — model-level blocks such as health-bar anchors, camera values
and hero-specific data. Copy from stock.

**AnimGraph 2** — Deadlock's animation graph system. The model references a
skeleton (`.vnmskel`) and graph files (`.vnmgraph`). CSDK 12 cannot compile
these links; the final compile uses CS2 Workshop Tools.

**NmSkeleton** — the animation skeleton file referenced by the model. Do not
ship the stock hero's `.vnmskel_c`.

**NmClip** — an animation clip. Do not ship stock `.vnmclip_c` files in a model
swap.

**DMX** — the mesh/skeleton exchange format used by ModelDoc. Export
`22_modeldoc` with binary encoding 9.

**ModelDoc** — CSDK 12's node-based model editor. It builds the `.vmdl` and
compiles the model.

**pbr.vfx** — Deadlock's hero shader.

**NPR** — non-photorealistic rendering; Deadlock's stylized lighting/outline.

**VMAT / VMAT_C** — material source / compiled material.

**VTEX / VTEX_C** — texture compile descriptor / compiled texture.

**DefaultMaterialGroup** — the ModelDoc node that maps Blender material names
to `.vmat` paths. Every material name must have a slot.

**VPK** — the packed mod archive. `pakNN_dir.vpk` is the index.

**Content tree** — `content/citadel_addons/<addon>/`; source files that the
tools compile.

**Game tree** — `game/citadel_addons/<addon>/`; compiled files that get packed.

**Staging folder** — a clean copy of only the compiled files, at their final
game paths, used as the VPK input.
