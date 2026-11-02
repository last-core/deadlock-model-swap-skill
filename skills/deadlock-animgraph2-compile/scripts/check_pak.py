"""Verify a packed Deadlock VPK and the staging folder it came from.

    python check_pak.py --vpk pak05_dir.vpk --model <compiled>.vmdl_c \
        [--staging staging_dir] [--s2v Source2Viewer-CLI] \
        [--expect-size N] [--expect-crc CRC32] [--json-out report.json]

Checks:
  - VPK footer signature/version and non-zero size;
  - in-pak listing contains the model, with size/CRC if the listing exposes it;
  - the compiled model's size and CRC32 match --expect-* when supplied;
  - the staging folder contains only compiled assets.

This is a best-effort wrapper around Source 2 Viewer's listing output; the raw
listing is printed so a format change is visible.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path

VPK_SIGNATURE = 0x55AA1234
FORBIDDEN_SUFFIXES = (
    ".dmx", ".vmdl", ".fbx", ".gltf", ".glb", ".blend",
    ".vtex", ".vmat", ".vdata", ".vpdi",
    ".vnmskel_c", ".vnmclip_c", ".vdata_c",
)
FORBIDDEN_NAMES = {"gameinfo.gi", "image_compiler.vdata_c"}
ALLOWED_SUFFIXES = (".vmdl_c", ".vmat_c", ".vtex_c")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vpk", required=True)
    parser.add_argument("--model", default=None, help="compiled .vmdl_c to compare")
    parser.add_argument("--staging", default=None, help="staging folder to inspect")
    parser.add_argument("--s2v", default=None, help="Source2Viewer-CLI executable")
    parser.add_argument("--expect-size", type=int, default=None)
    parser.add_argument("--expect-crc", default=None, help="expected CRC32 as hex or int")
    parser.add_argument("--json-out", default=None)
    return parser.parse_args()


def crc32(path: Path) -> int:
    value = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value = zlib.crc32(chunk, value)
    return value & 0xFFFFFFFF


def check_footer(path: Path) -> dict:
    size = path.stat().st_size
    result = {"size": size, "signature": None, "version": None, "footer_ok": False}
    if size < 48:
        result["error"] = "file shorter than a VPK2 footer"
        return result
    with open(path, "rb") as handle:
        handle.seek(-48, os.SEEK_END)
        footer = handle.read(48)
    signature, version, tree_size, file_data_size = (
        int.from_bytes(footer[0:4], "little"),
        int.from_bytes(footer[4:8], "little"),
        int.from_bytes(footer[8:12], "little"),
        int.from_bytes(footer[12:16], "little"),
    )
    result.update({
        "signature": hex(signature),
        "version": version,
        "tree_size": tree_size,
        "file_data_size": file_data_size,
    })
    result["footer_ok"] = signature == VPK_SIGNATURE and version in (1, 2)
    return result


def run_s2v(s2v: str, vpk: Path) -> str:
    attempts = [
        [s2v, "--vpk_dir", str(vpk)],
        [s2v, "-i", str(vpk), "--vpk_dir"],
        [s2v, "-i", str(vpk), "-l"],
    ]
    last = ""
    for command in attempts:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        last = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and last.strip():
            return last
    return last


def inspect_staging(root: Path) -> dict:
    forbidden = []
    unexpected = []
    allowed_count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        name = path.name
        rel = str(path.relative_to(root)).replace("\\", "/")
        if name in FORBIDDEN_NAMES or name.endswith(FORBIDDEN_SUFFIXES):
            forbidden.append(rel)
        elif name.endswith(ALLOWED_SUFFIXES):
            allowed_count += 1
        else:
            unexpected.append(rel)
    return {
        "root": str(root.resolve()),
        "allowed_files": allowed_count,
        "forbidden": forbidden,
        "unexpected": unexpected,
    }


def main() -> int:
    args = parse_args()
    vpk = Path(args.vpk)
    if not vpk.exists():
        raise SystemExit(f"VPK not found: {vpk}")

    report: dict = {"vpk": str(vpk.resolve()), "footer": check_footer(vpk)}
    errors = []
    warnings = []

    if not report["footer"]["footer_ok"]:
        errors.append("VPK footer signature/version check failed")

    model_info = None
    if args.model:
        model = Path(args.model)
        if not model.exists():
            errors.append(f"compiled model not found: {model}")
        else:
            size = model.stat().st_size
            crc = crc32(model)
            model_info = {"path": str(model.resolve()), "size": size, "crc32": f"{crc:08x}"}
            if args.expect_size is not None and size != args.expect_size:
                errors.append(f"compiled model size {size} != expected {args.expect_size}")
            if args.expect_crc is not None:
                expected = args.expect_crc.lower().replace("0x", "")
                if f"{crc:08x}" != expected:
                    errors.append(f"compiled model CRC {crc:08x} != expected {expected}")
    report["model"] = model_info

    if args.s2v:
        listing = run_s2v(args.s2v, vpk)
        report["listing_excerpt"] = "\n".join(
            line for line in listing.splitlines()
            if args.model is None or Path(args.model).name.lower() in line.lower()
        )[:4000]
        if args.model and Path(args.model).name.lower() not in listing.lower():
            errors.append(f"model name {Path(args.model).name} not found in VPK listing")
        if args.expect_size is not None and str(args.expect_size) not in listing:
            warnings.append("expected size not found in the S2V listing text; inspect the excerpt")
    else:
        warnings.append("--s2v not supplied; in-pak listing not checked")

    if args.staging:
        staging = Path(args.staging)
        if not staging.is_dir():
            errors.append(f"staging folder not found: {staging}")
        else:
            report["staging"] = inspect_staging(staging)
            if report["staging"]["forbidden"]:
                errors.append("forbidden files in staging")
            if report["staging"]["unexpected"]:
                warnings.append("unexpected file types in staging; inspect the list")

    for warning in warnings:
        print("WARN ", warning)
    for error in errors:
        print("ERROR", error)

    report["errors"] = errors
    report["warnings"] = warnings
    report["ok"] = not errors
    print(json.dumps({k: v for k, v in report.items() if k != "listing_excerpt"}, indent=2, ensure_ascii=False))
    if report.get("listing_excerpt"):
        print("\nlisting excerpt:\n" + report["listing_excerpt"])

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", out)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
