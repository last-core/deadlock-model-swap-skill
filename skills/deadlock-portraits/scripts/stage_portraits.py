"""Cover-crop hero portrait artwork to the stock sizes.

    python stage_portraits.py --config project.json \
        --src-dir <art_dir> [--out-dir <content>/panorama/images/heroes] \
        [--source-pattern "{key}_{variant}.png"] \
        [--target-pattern "{key}_{variant}_psd.png"] \
        [--anchor center|top|bottom] [--jobs jobs.json]

Default jobs come from stock.portrait_sizes in project.json and the panorama
key. A job is {source, target, width, height}. Only the variants you supply are
staged; the rest stay stock and should be listed for the user.
"""
from __future__ import annotations

import argparse
import json
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


def default_jobs(config: dict, source_pattern: str, target_pattern: str) -> list[dict]:
    key = cfg(config, "hero.panorama_key") or cfg(config, "hero.model_asset") or "<hero>"
    sizes = cfg(config, "stock.portrait_sizes", {}) or {}
    jobs = []
    for variant, size in sizes.items():
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            continue
        jobs.append({
            "source": source_pattern.format(key=key, variant=variant),
            "target": target_pattern.format(key=key, variant=variant),
            "width": int(size[0]),
            "height": int(size[1]),
        })
    return jobs


def cover_crop(image: Image.Image, width: int, height: int, anchor: str) -> Image.Image:
    source_width, source_height = image.size
    target_aspect = width / height
    source_aspect = source_width / source_height
    if abs(source_aspect - target_aspect) > 1e-3:
        if source_aspect > target_aspect:  # too wide -> trim sides
            new_width = int(round(source_height * target_aspect))
            x = (source_width - new_width) // 2
            image = image.crop((x, 0, x + new_width, source_height))
        else:  # too tall -> trim top/bottom
            new_height = int(round(source_width / target_aspect))
            if anchor == "top":
                y = 0
            elif anchor == "bottom":
                y = source_height - new_height
            else:
                y = (source_height - new_height) // 2
            image = image.crop((0, y, source_width, y + new_height))
    return image.resize((width, height), Image.LANCZOS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--src-dir", required=True)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--source-pattern", default="{key}_{variant}.png")
    parser.add_argument("--target-pattern", default="{key}_{variant}_psd.png")
    parser.add_argument("--anchor", choices=("center", "top", "bottom"), default="center")
    parser.add_argument("--jobs", default=None, help="JSON list of job objects")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    if args.jobs:
        jobs = load_json(args.jobs)
    else:
        jobs = default_jobs(config, args.source_pattern, args.target_pattern)
    if not jobs:
        raise SystemExit("no jobs; pass --jobs or set stock.portrait_sizes in project.json")

    out_dir = args.out_dir
    if not out_dir:
        content = cfg(config, "game.content_addon_dir")
        if not content:
            raise SystemExit("--out-dir is required when project.json has no content addon")
        out_dir = str(Path(content) / "panorama" / "images" / "heroes")
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    staged = []
    missing = []
    for job in jobs:
        source = Path(args.src_dir) / job["source"]
        if not source.exists():
            missing.append(str(source))
            continue
        width, height = int(job["width"]), int(job["height"])
        image = Image.open(source).convert("RGBA")
        before = image.size
        image = cover_crop(image, width, height, args.anchor)
        target = out_path / job["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        staged.append({"source": str(source), "target": str(target), "from": before, "to": [width, height]})
        print("%-32s %sx%s -> %-32s %dx%d" % (source.name, before[0], before[1], target.name, width, height))

    for path in missing:
        print("MISSING", path)
    print("staged", len(staged), "of", len(jobs), "into", out_path)
    if missing:
        print("The missing variants stay stock and will visibly mismatch; list them for the user.")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
