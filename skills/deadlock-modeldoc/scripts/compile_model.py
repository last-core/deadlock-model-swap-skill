"""Run a Source 2 resource compiler on a .vmdl, .vmat or .vtex asset.

    python compile_model.py --input work.vmdl --compiler <resourcecompiler.exe> \
        [--cwd <compiler dir>] [--output <expected.vmdl_c>] [--extra -someflag]

The compiler is invoked as:

    <compiler> -f -i <input> [extra...]

with the working directory set to the compiler's folder by default. This avoids
the "compiler sees a .vpk in the working directory" failure.

Works for CSDK 12 and CS2 Workshop Tools; pass the matching compiler path. The
default expected output is the input with `_c` appended (`.vmdl_c`, `.vmat_c`,
`.vtex_c`). The script does not modify the input.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--extra", nargs="*", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.input)
    compiler = Path(args.compiler)
    if not source.exists():
        raise SystemExit(f"input not found: {source}")
    if not compiler.exists():
        raise SystemExit(f"compiler not found: {compiler}")

    cwd = Path(args.cwd) if args.cwd else compiler.parent
    command = [str(compiler), "-f", "-i", str(source)] + list(args.extra)
    print("cwd:", cwd)
    print("command:", " ".join(command))
    result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, errors="replace")
    combined = (result.stdout or "") + (result.stderr or "")
    tail = "\n".join(combined.splitlines()[-30:])
    print(tail)
    print("exit code:", result.returncode)

    expected = Path(args.output) if args.output else source.with_suffix(source.suffix + "_c")
    if not expected.exists():
        # The compiler may write beside the content source rather than the input.
        print(f"ERROR: expected output not found: {expected}")
        return 1
    print(f"output: {expected} ({expected.stat().st_size} bytes)")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
