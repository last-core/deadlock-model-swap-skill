# Local preview caveats

Blender previews are useful, but only if you know what they cannot tell you.

## Hide every other mesh

A scene often contains the stock model, reference meshes and the new mesh at
the same time. Leaving them visible superimposes two characters and produces
nonsense that looks like a rigging bug. Hide everything except the mesh you are
inspecting.

## Clip replay is faithful for rotations

Render the **stock** mesh on the same armature under the same clip. If the stock
mesh looks right, your playback is right and any difference is weights. This is
the control that separates a playback bug from a skinning bug.

## Units and translation channels

Game clips are usually in inches; a Blender rig may be in metres. If the units
do not match, keeping the translation channels flings the model far away.

- Zero `pose_bone.location` for preview when the clip and rig units differ.
- Blender's pose location is an offset from rest, so zeroing it is correct for a
  unit-mismatched preview.
- Consequence: anything positioned **by** a location channel (weapons, IK
  targets, attachment helpers) will not appear where the game puts it.
- Root motion is lost when you zero translation. Do not judge root motion from
  that preview.

If a script reports a bone moving tens of metres, suspect units or translation
channels before suspecting weights.

## Side views for depth

A front view hides depth offsets. Check a side view for anything that involves
the depth axis: mesh-to-rig alignment, weapon fit, hair/cloth clearance.

## Stress poses

A hand-authored stress pose (arms up, legs bent, head turned) reveals weight
problems faster than a clip. Use it to check:

- hair roots and strand chains;
- cloth panels and rims;
- shoulders, elbows, hips and knees;
- eyes and mouth.

## Per-material flat colours

A flat-colour render per material identifies which material owns a bad region
much faster than guessing from the shaded artefact. Use a random flat colour
per material and render the stress pose.

## Weapon placement

At rest, the weapon bone may sit at the origin, and clips move the weapon into
the hands through location channels. Orientation can be compared locally with a
fixed camera; **position is only confirmable in game**.
