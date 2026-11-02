# Hard constraints

These are not style preferences. Each one maps to a failure that is expensive to
diagnose after packing.

## 1. Stock skeleton

- Every stock bone keeps its **name** and its **bind transform**.
- Never move, rename or delete a stock bone.
- Added bones are allowed for cloth, hair, tails or accessories. They are extra
  entries; they do not replace or renumber stock bones.
- The compiled model's stock-bone inverse bind matrices must match the stock
  model. Added bones will make the skeleton array longer; that is fine.
- Helper/pivot bone names may differ between dumps. Compare the bind transforms,
  not only the names.

Why: the game plays its animation clips on those exact bones. A moved bone
changes every animation that touches it, even if the rest pose looks fine.

## 2. Hitboxes

- Keep every hitbox set exactly as stock.
- Do not rebuild, rescale, retarget or "fix" hitboxes.
- A mesh swap changes the silhouette, not the hit detection contract.

Why: hitboxes are gameplay. Changing them is not cosmetic.

## 3. Attachments, game data and camera

- Copy every attachment and game-data block from the stock model.
- Copy camera offsets and FOV exactly. Never widen, raise or "improve" the
  camera.
- Copy the health-bar anchor, muzzle/aim attachments, and any hero-specific
  game data.
- Keep the stock bodygroups and their names.

Why: attachments and camera values are gameplay. A changed camera gives a
different view from other players.

## 4. Silhouette and fair play

- Match the stock height, width and major proportions.
- Do not make the model smaller, thinner, taller, or harder to see.
- Do not add glow, self-illumination, transparency, or very dark materials.
- Do not remove or thicken the outline.
- Keep alpha-test cutouts small, like hair strands.

Why: visibility and silhouette are part of the fairness rules. A smaller or
brighter model is an advantage mod.

## 5. Shipping

Ship only the compiled assets you changed:

- `.vmdl_c` — the final model
- `.vmat_c` — materials
- `.vtex_c` — textures and portraits

Never ship:

- `.dmx`, `.vmdl`, `.fbx`, `.gltf` source files
- the stock hero's `.vnmskel_c` or `.vnmclip_c`
- `scripts/` or any `.vdata_c`
- `gameinfo.gi`
- `image_compiler.vdata_c` or `.vpdi` source lists
- compiled files you did not change

Why: shipping stock animation/skeleton files overrides other mods and breaks
after updates. Shipping sources bloats the VPK and can confuse the compiler.

## 6. Addon tree

- The model folder contains one final `.vmdl_c` plus the `.vmat_c`/`.vtex_c`
  files it uses.
- Portrait textures live under `panorama/images/...`, not in the model folder.
- Use a separate staging folder before packing. Do not pack the content tree.
- Check the in-pak model's size and CRC against the file you just compiled.

Why: packing the wrong tree silently ships the previous build.

## 7. Licensing

- Fan models are usually licensed for local use only.
- Do not distribute ripped models, textures or animation data.
- Check the source model's license before publishing.
- Follow the game's modding rules for visibility, glow, transparency and size.

## 8. Gates

- A failed gate blocks the next stage.
- Do not "come back to it after the model is in game". Stage-1 and stage-2
  failures are much cheaper to fix in Blender than in a packed VPK.
- Record each gate result in `project.json` under `gates`.
