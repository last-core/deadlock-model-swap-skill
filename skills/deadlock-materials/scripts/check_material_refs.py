"""Check every texture path referenced by compiled Deadlock materials.

    python check_material_refs.py --matdir <game addon materials dir> \
        --game <game dir> [--s2v <Source2Viewer-CLI>] [--json-out report.json]

A reference that resolves to neither the addon nor the game paks is a missing
texture. The engine draws its checker pattern there; the shader input is absent.

The script decompiles each .vmat_c, collects g_t* paths, and checks:
  1. a local .vtex / .vtex_c under the addon materials directory;
  2. the game paks via Source 2 Viewer.

Exit code 1 if any reference is missing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


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
    parser.add_argument("--matdir", default=None,
                        help="compiled materials directory (contains .vmat_c)")
    parser.add_argument("--game", default=None, help="game directory")
    parser.add_argument("--s2v", default=None, help="Source2Viewer-CLI executable")
    parser.add_argument("--paks", default=None,
                        help="comma-separated pak paths; defaults to citadel/core pak01_dir.vpk")
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def norm_ref(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def local_candidates(matdir: Path, ref: str) -> list[Path]:
    ref = norm_ref(ref)
    tail = ref.split("materials/", 1)[-1] if "materials/" in ref else ref
    candidates = [matdir / tail]
    if tail.lower().endswith(".vtex"):
        candidates.append(matdir / (tail + "_c"))
    elif not tail.lower().endswith(".vtex_c"):
        candidates.append(matdir / (tail + ".vtex_c"))
    return candidates


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    matdir_raw = args.matdir or cfg(config, "paths.material_dir") or ""
    if not matdir_raw:
        # Derive a sensible default from the content addon if possible.
        content = cfg(config, "game.content_addon_dir")
        asset = cfg(config, "hero.model_asset")
        if content and asset:
            matdir_raw = str(Path(content) / "models" / "heroes_wip" / asset / "materials")
    if not matdir_raw:
        raise SystemExit("--matdir is required")
    matdir = Path(matdir_raw)
    if not matdir.is_dir():
        raise SystemExit(f"materials directory not found: {matdir}")

    game_raw = args.game or cfg(config, "game.install_dir") or ""
    if not game_raw:
        raise SystemExit("--game is required")
    game = Path(game_raw)
    if not game.is_dir():
        raise SystemExit(f"game directory not found: {game}")

    s2v = args.s2v or cfg(config, "paths.source2viewer")
    if not s2v:
        raise SystemExit("--s2v is required (or set paths.source2viewer)")
    s2v_path = Path(s2v)
    if not s2v_path.exists():
        raise SystemExit(f"Source2Viewer-CLI not found: {s2v_path}")

    if args.paks:
        paks = [Path(p.strip()) for p in args.paks.split(",") if p.strip()]
    else:
        paks = [
            game / "citadel" / "pak01_dir.vpk",
            game / "core" / "pak01_dir.vpk",
        ]

    temp_dir = Path(os.environ.get("TEMP", "."))
    refs: dict[str, set[str]] = {}
    vmat_files = sorted(matdir.glob("*.vmat_c"))
    if not vmat_files:
        raise SystemExit(f"no .vmat_c files in {matdir}")

    for vmat in vmat_files:
        tmp = temp_dir / ("refcheck_" + vmat.name)
        try:
            if tmp.is_file():
                tmp.unlink()
        except OSError:
            pass
        result = subprocess.run(
            [str(s2v_path), "-i", str(vmat), "-d", "-o", str(tmp)],
            capture_output=True, text=True, errors="replace",
        )
        if not tmp.exists():
            print(f"WARN could not decompile {vmat.name}: "
                  f"{(result.stdout + result.stderr).strip()[:200]}")
            continue
        text = tmp.read_text(encoding="utf-8-sig", errors="replace")
        for key, value in re.findall(r'"(g_t\w+)"\s+"([^"]+)"', text):
            refs.setdefault(value, set()).add(f"{vmat.name[:-7]}:{key}")

    print(f"{len(refs)} distinct texture refs across {len(vmat_files)} compiled materials\n")
    missing: list[dict] = []
    for ref, users in sorted(refs.items()):
        exists_local = any(candidate.exists() for candidate in local_candidates(matdir, ref))
        if exists_local:
            print(f"  OK(local) {ref}")
            continue
        hit = False
        for pak in paks:
            if not pak.exists():
                continue
            out = temp_dir / "refchk"
            result = subprocess.run(
                [str(s2v_path), "-i", str(pak), "-f", ref, "-d", "-o", str(out)],
                capture_output=True, text=True, errors="replace",
            )
            combined = (result.stdout or "") + (result.stderr or "")
            output_exists = out.exists() and (not out.is_dir() or any(out.iterdir()))
            if "Dump written" in combined or output_exists:
                hit = True
                break
        if hit:
            print(f"  OK(game)  {ref}")
        else:
            print(f"  MISSING   {ref}   <- {', '.join(sorted(users))}")
            missing.append({"path": ref, "users": sorted(users)})

    print(f"\n{len(missing)} missing reference(s)")
    report = {
        "matdir": str(matdir.resolve()),
        "game": str(game.resolve()),
        "paks": [str(p) for p in paks],
        "refs": len(refs),
        "missing": missing,
    }
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", out)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
