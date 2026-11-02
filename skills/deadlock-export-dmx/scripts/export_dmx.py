"""Scale, organise and export a Deadlock render mesh to DMX.

Run inside Blender:

    blender -b -P export_dmx.py -- \
        --config project.json --blend weighted.blend --out-dir <addon>/dmx \
        [--mesh NAME] [--armature NAME] [--collection NAME] \
        [--scale 39.37] [--unparent] [--repair-collection] [--check-only]

Defaults:
  - scale comes from units.scale in project.json (39.37 for metres -> inches);
  - the mesh stays parented to the armature;
  - the collection must already exist and contain the mesh; the armature must be
    in the body collection.

The generic exporter writes <collection>.dmx. Verify the file name matches the
stock render-mesh name.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import bpy
    import addon_utils
except ImportError as exc:  # pragma: no cover
    raise SystemExit("This script must be run with Blender's Python") from exc


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def cfg(data: dict, dotted: str, default=None):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--mesh", default=None)
    parser.add_argument("--armature", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--scale", type=float, default=None)
    parser.add_argument("--unparent", action="store_true",
                        help="clear parent keep transform before scaling; default keeps the parent")
    parser.add_argument("--repair-collection", action="store_true",
                        help="move the mesh (and armature for the body) into the collection")
    parser.add_argument("--body", action="store_true",
                        help="this is the body collection; require the armature to be in it")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--json-out", default=None)
    return parser.parse_args(argv)


def enable_dmx_addon() -> str:
    for name in ("io_scene_valvesource2", "bl_ext.user_default.io_scene_valvesource2"):
        try:
            addon_utils.enable(name, default_set=False, persistent=True)
            return name
        except Exception:
            continue
    raise SystemExit(
        "could not enable io_scene_valvesource2; install the Valve DMX addon "
        "or enable it in Blender preferences"
    )


def find_object(name: str | None, kind: str, label: str):
    if name:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != kind:
            raise SystemExit(f"{label} not found: {name}")
        return obj
    candidates = [o for o in bpy.data.objects if o.type == kind]
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit(f"multiple {label}s; pass --{label} or set it in project.json")


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    mesh_name = args.mesh or cfg(config, "source.mesh_object")
    arm_name = args.armature or cfg(config, "source.armature_object")
    scale = args.scale if args.scale is not None else float(cfg(config, "units.scale", 39.37))
    if scale <= 0:
        raise SystemExit("scale must be positive; check units.scale")
    collection_name = args.collection or mesh_name or cfg(config, "hero.model_asset")
    if not collection_name:
        raise SystemExit("no collection name; pass --collection")

    bpy.ops.wm.open_mainfile(filepath=args.blend)
    bpy.context.view_layer.update()
    enable_dmx_addon()

    target = find_object(mesh_name, "MESH", "mesh")
    arm = find_object(arm_name, "ARMATURE", "armature") if arm_name else None
    if arm is None:
        for modifier in target.modifiers:
            if modifier.type == "ARMATURE" and modifier.object:
                arm = modifier.object
                break
    if arm is None:
        raise SystemExit("armature not found; pass --armature or set source.armature_object")
    if arm.type != "ARMATURE":
        raise SystemExit(f"object is not an armature: {arm.name}")

    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        if not args.repair_collection:
            raise SystemExit(f"collection not found: {collection_name} (use --repair-collection to create it)")
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    is_body = args.body or collection_name == cfg(config, "hero.model_asset", "") or "body" in collection_name.lower()
    if args.repair_collection:
        if target.name not in collection.objects:
            for coll in list(target.users_collection):
                coll.objects.unlink(target)
            collection.objects.link(target)
        if is_body and arm.name not in collection.objects:
            for coll in list(arm.users_collection):
                coll.objects.unlink(arm)
            collection.objects.link(arm)

    if target.name not in collection.objects:
        raise SystemExit(f"mesh {target.name} is not in collection {collection_name}")
    if is_body and arm and arm.name not in collection.objects:
        raise SystemExit(
            f"armature {arm.name} is not in body collection {collection_name}; "
            "the body collection must contain the armature"
        )

    if args.check_only:
        print("collection:", collection_name, "objects:", [o.name for o in collection.objects])
        print("mesh:", target.name, "verts:", len(target.data.vertices))
        return 0

    bpy.ops.object.select_all(action="DESELECT")
    for obj in [target, arm]:
        if obj:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = arm if arm else target

    if args.unparent and target.parent:
        target.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

    # Apply existing scale first so setting SCALE does not overwrite a
    # meaningful object scale.
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for obj in [target, arm]:
        if obj:
            obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = target.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    if points:
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
    else:
        lo = hi = [0.0, 0.0, 0.0]
    zs = [p.z for p in points] if points else [0.0]
    vert_count = len(mesh.vertices)
    print("mesh z range: %.2f .. %.2f" % (min(zs), max(zs)))
    print("bounds: lo", [round(v, 3) for v in lo], "hi", [round(v, 3) for v in hi])
    print("verts:", vert_count, "scale:", scale)
    evaluated.to_mesh_clear()

    scene = bpy.context.scene
    if not hasattr(scene, "vs"):
        raise SystemExit("scene.vs not found; the Valve DMX addon is not active")
    vs = scene.vs
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vs.export_path = str(out_dir).replace("\\", "/")
    vs.dmx_format = "22_modeldoc"
    vs.dmx_encoding = "9"
    vs.export_format = "DMX"
    print("export_path", vs.export_path, "format", vs.dmx_format,
          "encoding", vs.dmx_encoding, "export_format", vs.export_format)

    bpy.ops.export_scene.smd(export_scene=False, collection=collection_name)
    dmx_path = out_dir / f"{collection_name}.dmx"
    if not dmx_path.exists():
        raise SystemExit(f"export did not produce {dmx_path}")
    print("wrote", dmx_path)

    report = {
        "blend": str(Path(args.blend).resolve()),
        "collection": collection_name,
        "mesh": target.name,
        "armature": arm.name if arm else None,
        "scale": scale,
        "verts": vert_count,
        "bounds": {"lo": [round(v, 6) for v in lo], "hi": [round(v, 6) for v in hi]},
        "dmx": str(dmx_path.resolve()),
        "bytes": dmx_path.stat().st_size,
    }
    out = args.json_out or str(out_dir / f"{collection_name}.export.json")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
