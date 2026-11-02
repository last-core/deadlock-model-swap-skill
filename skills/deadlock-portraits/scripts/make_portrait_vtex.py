"""Compile Deadlock portraits through image_compiler.vdata or .vtex descriptors.

    python make_portrait_vtex.py --config project.json --route image-compiler \
        [--content <content addon>] [--compile]

    python make_portrait_vtex.py --config project.json --route vtex \
        [--content <content addon>] [--compiler resourcecompiler] [--compile]

Both routes are supported. The canonical CSDK route is image_compiler.vdata plus
a rename to the stock compiled name. The .vtex descriptor route names the
descriptor after the stock compiled asset, which makes the compiled name match.

Portrait sizes and the panorama key come from project.json. PNG is a valid
source image; the issue with standalone UI textures is naming/compilation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = '''<!-- dmx encoding keyvalues2_noids 1 format vtex 1 -->
"CDmeVtex"
{{
\t"m_inputTextureArray" "element_array"
\t[
\t\t"CDmeInputTexture"
\t\t{{
\t\t\t"m_name" "string" "SheetTexture"
\t\t\t"m_fileName" "string" "{src}"
\t\t\t"m_colorSpace" "string" "srgb"
\t\t\t"m_typeString" "string" "2D"
\t\t\t"m_imageProcessorArray" "element_array"
\t\t\t[
\t\t\t]
\t\t}}
\t]
\t"m_outputTypeString" "string" "2D"
\t"m_outputFormat" "string" "RGBA8888"
\t"m_outputClearColor" "vector4" "0 0 0 0"
\t"m_nOutputMinDimension" "int" "0"
\t"m_nOutputMaxDimension" "int" "0"
\t"m_textureOutputChannelArray" "element_array"
\t[
\t\t"CDmeTextureOutputChannel"
\t\t{{
\t\t\t"m_inputTextureArray" "string_array"
\t\t\t[
\t\t\t\t"SheetTexture"
\t\t\t]
\t\t\t"m_srcChannels" "string" "rgba"
\t\t\t"m_dstChannels" "string" "rgba"
\t\t\t"m_mipAlgorithm" "CDmeImageProcessor"
\t\t\t{{
\t\t\t\t"m_algorithm" "string" ""
\t\t\t\t"m_stringArg" "string" ""
\t\t\t\t"m_vFloat4Arg" "vector4" "0 0 0 0"
\t\t\t}}
\t\t\t"m_outputColorSpace" "string" "srgb"
\t\t}}
\t]
\t"m_vClamp" "vector3" "0 0 0"
\t"m_bNoLod" "bool" "0"
}}
'''


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


def default_jobs(config: dict, target_pattern: str) -> list[dict]:
    key = cfg(config, "hero.panorama_key") or cfg(config, "hero.model_asset") or "<hero>"
    sizes = cfg(config, "stock.portrait_sizes", {}) or {}
    jobs = []
    for variant, size in sizes.items():
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            continue
        target = target_pattern.format(key=key, variant=variant)
        jobs.append({
            "source": target,
            "target": target,
            "width": int(size[0]),
            "height": int(size[1]),
        })
    return jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--route", choices=("image-compiler", "vtex"), default="image-compiler")
    parser.add_argument("--content", default=None)
    parser.add_argument("--rel-dir", default="panorama/images/heroes")
    parser.add_argument("--target-pattern", default="{key}_{variant}_psd.png")
    parser.add_argument("--jobs", default=None)
    parser.add_argument("--compiler", default=None)
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--rename-compiled", action="store_true",
                        help="copy <name>_png.vtex_c outputs to the stock <name>.vtex_c names")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    content = args.content or cfg(config, "game.content_addon_dir")
    if not content:
        raise SystemExit("--content is required (or set game.content_addon_dir)")
    content_path = Path(content)
    rel_dir = args.rel_dir.replace("\\", "/").strip("/")
    image_dir = content_path / rel_dir
    image_dir.mkdir(parents=True, exist_ok=True)

    jobs = load_json(args.jobs) if args.jobs else default_jobs(config, args.target_pattern)
    if not jobs:
        raise SystemExit("no jobs; pass --jobs or set stock.portrait_sizes in project.json")

    if args.route == "vtex":
        compiler = args.compiler or cfg(config, "paths.resourcecompiler_sdk") or cfg(config, "paths.resourcecompiler_game")
        for job in jobs:
            target = job["target"]
            stem = Path(target).stem
            source_rel = f"{rel_dir}/{target}"
            descriptor = image_dir / (stem + ".vtex")
            descriptor.write_text(TEMPLATE.format(src=source_rel), encoding="utf-8", newline="\n")
            print("wrote", descriptor, "->", source_rel)
            if args.compile:
                if not compiler:
                    raise SystemExit("--compiler is required with --compile")
                result = subprocess.run(
                    [compiler, "-f", "-i", str(descriptor)],
                    capture_output=True, text=True, errors="replace",
                    cwd=str(Path(compiler).parent),
                )
                tail = [line for line in (result.stdout + result.stderr).splitlines()
                        if "compiled" in line.lower() or "error" in line.lower()][-2:]
                print(" ", stem, "->", tail)
        return 0

    # image_compiler.vdata route: update an existing template; do not invent one.
    vdata = content_path / "panorama" / "image_compiler.vdata"
    lines = [f'panorama:"file://{{images}}/heroes/{job["target"]}"' for job in jobs]
    if not vdata.exists():
        print("image_compiler.vdata not found at", vdata)
        print("Add these lines to the addon's image_compiler.vdata template:")
        for line in lines:
            print(" ", line)
        print("Then compile the image_compiler asset in the Asset Browser (Full).")
        return 1

    text = vdata.read_text(encoding="utf-8-sig", errors="replace")
    added = []
    for line in lines:
        if line not in text:
            added.append(line)
    if added:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n".join(added) + "\n"
        vdata.write_text(text, encoding="utf-8", newline="\n")
        print("added", len(added), "line(s) to", vdata)
    else:
        print("all lines already present in", vdata)

    if args.compile:
        print("Compile the image_compiler asset in the CSDK 12 Asset Browser (Recompile -> Full).")
        print("The Asset Browser compile is GUI-driven; this script does not invoke it.")

    if args.rename_compiled:
        game_addon = cfg(config, "game.game_addon_dir")
        if not game_addon:
            raise SystemExit("--rename-compiled needs game.game_addon_dir")
        compiled_dir = Path(game_addon) / rel_dir
        for job in jobs:
            target = Path(job["target"])
            stock = compiled_dir / (target.stem + ".vtex_c")
            source = compiled_dir / (target.stem + "_png.vtex_c")
            if source.exists() and not stock.exists():
                shutil.copy2(source, stock)
                print("renamed", source.name, "->", stock.name)
            elif stock.exists():
                print("stock name already exists:", stock.name)
            else:
                print("compiled output not found for", target.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
