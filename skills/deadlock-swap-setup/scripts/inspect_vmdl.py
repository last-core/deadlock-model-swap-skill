"""Best-effort text inspection of a decompiled Source 2 .vmdl.

    python inspect_vmdl.py <model.vmdl> [--json-out report.json]

This is not a full keyvalues2 parser. It finds named node blocks with a
balanced-brace scan and extracts a few common keys. Use it to discover node
names and paths; confirm the important values in ModelDoc or Source 2 Viewer.

It does not modify the file.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NODE_NAMES = [
    "Skeleton",
    "RenderMeshList",
    "MaterialGroupList",
    "DefaultMaterialGroup",
    "BodyGroupList",
    "PhysicsShapeList",
    "LODGroupList",
    "HitboxSetList",
    "AttachmentList",
    "GameDataList",
    "AnimationList",
    "NmSkeletonList",
    "AnimGraph2List",
]

INTERESTING_KEYS = [
    "m_name",
    "m_fileName",
    "m_meshFile",
    "m_skeleton",
    "m_animGraph",
    "m_boneName",
    "m_parentBone",
    "m_modelName",
    "m_attachmentName",
    "m_hitboxSetName",
]


def _skip_string(text: str, i: int) -> int:
    """Return the index just past a quoted string starting at text[i] == '"'."""
    i += 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return i


def find_block(text: str, name: str) -> tuple[int, int] | None:
    """Find the first node container: a brace block or a bracket array.

    Keyvalues2 uses both `"Node" "element" { ... }` and
    `"Node" "element_array" [ ... ]`. Matching only braces would treat an
    array's first element block as the node body.
    """
    pattern = re.compile(r'"' + re.escape(name) + r'"')
    for match in pattern.finditer(text):
        i = match.end()
        while i < len(text) and text[i] not in "{[":
            if text[i] == '"':
                i = _skip_string(text, i)
            else:
                i += 1
        if i >= len(text) or text[i] not in "{[":
            continue
        start = i
        opening = text[i]
        closing = "}" if opening == "{" else "]"
        depth = 0
        j = i
        while j < len(text):
            if text[j] == '"':
                j = _skip_string(text, j)
                continue
            if text[j] == opening:
                depth += 1
            elif text[j] == closing:
                depth -= 1
                if depth == 0:
                    return start, j + 1
            j += 1
    return None


def extract_keys(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for key in INTERESTING_KEYS:
        values = re.findall(r'"' + re.escape(key) + r'"\s+"(?:string|bool|int|float)"\s+"([^"]*)"', text)
        # Some keyvalues2 variants omit the type token.
        if not values:
            values = re.findall(r'"' + re.escape(key) + r'"\s+"([^"]*)"', text)
        if values:
            found[key] = values
    return found


def inspect(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    report: dict = {"file": str(path), "blocks": {}, "top_level_keys": extract_keys(text)}
    for name in NODE_NAMES:
        block = find_block(text, name)
        if not block:
            continue
        start, end = block
        body = text[start:end]
        report["blocks"][name] = {
            "present": True,
            "length": end - start,
            "keys": extract_keys(body),
            "child_blocks": [],
        }
        for child in NODE_NAMES:
            if child == name:
                continue
            if find_block(body, child):
                report["blocks"][name]["child_blocks"].append(child)
    report["has_animgraph2"] = "AnimGraph2List" in report["blocks"]
    report["has_nmskeleton"] = "NmSkeletonList" in report["blocks"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vmdl")
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    path = Path(args.vmdl)
    if not path.exists():
        raise SystemExit(f"not found: {path}")
    report = inspect(path)

    print("file:", report["file"])
    print("blocks:")
    for name, info in report["blocks"].items():
        print(f"  {name:24s} keys={list(info['keys'])} children={info['child_blocks']}")
    print("has AnimGraph2List:", report["has_animgraph2"])
    print("has NmSkeletonList:", report["has_nmskeleton"])

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
