"""Generate flat normal and roughness maps for Deadlock pbr.vfx materials.

    python make_flat_maps.py --out <materials_dir> [--size 256] [--rough 216]
    python make_flat_maps.py --config project.json

Why: pointing normal/roughness at materials/default/* lets the compiler emit a
merged g_tNormalRoughness under the default path, which may not exist in the
game. Shipping our own flat maps puts the merged texture under the addon path.

Needs Pillow.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required: pip install Pillow") from exc


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", default=None,
                        help="materials directory; defaults to the addon model materials dir")
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--rough", type=int, default=216,
                        help="roughness value 0-255 (216 = 0.85, soft matte)")
    parser.add_argument("--normal-name", default="flat_normal.png")
    parser.add_argument("--rough-name", default="flat_rough.png")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    out = args.out
    if not out:
        content = cfg(config, "game.content_addon_dir")
        asset = cfg(config, "hero.model_asset")
        if content and asset:
            out = str(Path(content) / "models" / "heroes_wip" / asset / "materials")
        else:
            raise SystemExit("--out is required when project.json has no content addon/model asset")
    if not (0 <= args.size <= 8192) or args.size < 2:
        raise SystemExit("--size must be between 2 and 8192")
    if not (0 <= args.rough <= 255):
        raise SystemExit("--rough must be between 0 and 255")

    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)

    normal = Image.new("RGB", (args.size, args.size), (128, 128, 255))
    roughness = Image.new("L", (args.size, args.size), args.rough)
    normal_path = directory / args.normal_name
    rough_path = directory / args.rough_name
    normal.save(normal_path)
    roughness.save(rough_path)
    print("wrote", normal_path)
    print("wrote", rough_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
