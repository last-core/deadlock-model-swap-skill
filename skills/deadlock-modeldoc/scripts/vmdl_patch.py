"""Targeted text patches for a decompiled Source 2 .vmdl.

    python vmdl_patch.py check model.vmdl [--json-out report.json]
    python vmdl_patch.py remove-animgraph model.vmdl --out work.vmdl
    python vmdl_patch.py set-render-meshes model.vmdl \
        --map old_name=new_name,old_path=new_path --out work.vmdl
    python vmdl_patch.py set-material-group model.vmdl \
        --materials mat_a,mat_b --template stock.vmdl --out work.vmdl
    python vmdl_patch.py add-animgraph model.vmdl \
        --skeleton models/.../hero.vnmskel \
        --default-graph animgraphs/.../hero.vnmgraph+hero.vnmgraph \
        --ui-graph animgraphs/.../hero_ui.vnmgraph+hero.vnmgraph \
        --out work.vmdl

This is a best-effort keyvalues2 text patcher, not a full serializer. It uses a
balanced-brace scan that respects quoted strings. Always compile/check the
result in ModelDoc; if a node shape differs, copy the stock block instead.

ModelDoc and CS2 Workshop Tools are GUI-first; this script automates the safe
text edits and leaves bodygroups/ragdoll/LODs to ModelDoc when necessary.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
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


def skip_string(text: str, i: int) -> int:
    i += 1
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return i


def find_node_span(text: str, name: str) -> tuple[int, int] | None:
    """Find a node's container: either a brace block or a bracket array.

    Keyvalues2 uses both:

        "Node" "element" { ... }
        "Node" "element_array" [ ... ]

    Matching only braces would treat an array's first element block as the
    node's body and delete the following nodes. Match the first opening
    delimiter, brace or bracket, and its balanced close.
    """
    pattern = re.compile(r'"' + re.escape(name) + r'"')
    for match in pattern.finditer(text):
        i = match.end()
        while i < len(text) and text[i] not in "{[":
            if text[i] == '"':
                i = skip_string(text, i)
            else:
                i += 1
        if i >= len(text) or text[i] not in "{[":
            continue
        opening = text[i]
        closing = "}" if opening == "{" else "]"
        depth = 0
        j = i
        while j < len(text):
            if text[j] == '"':
                j = skip_string(text, j)
                continue
            if text[j] == opening:
                depth += 1
            elif text[j] == closing:
                depth -= 1
                if depth == 0:
                    return match.start(), j + 1
            j += 1
    return None


def extract_node(text: str, name: str) -> str | None:
    span = find_node_span(text, name)
    if not span:
        return None
    return text[span[0]:span[1]]


def remove_node(text: str, name: str) -> tuple[str, bool]:
    span = find_node_span(text, name)
    if not span:
        return text, False
    start, end = span
    # Also consume trailing whitespace/newline.
    while end < len(text) and text[end] in " \t\r\n":
        end += 1
    return text[:start] + text[end:], True


def insert_before_final_brace(text: str, block: str) -> str:
    index = text.rfind("}")
    if index < 0:
        raise SystemExit("could not find the final closing brace")
    return text[:index] + block.rstrip() + "\n" + text[index:]


def replace_node(text: str, name: str, block: str) -> str:
    span = find_node_span(text, name)
    if span:
        return text[:span[0]] + block.rstrip() + text[span[1]:]
    return insert_before_final_brace(text, block)


def replace_inside_node(text: str, node: str, replacements: dict[str, str]) -> tuple[str, int]:
    span = find_node_span(text, node)
    if not span:
        return text, 0
    start, end = span
    body = text[start:end]
    changed = 0
    for old, new in replacements.items():
        pattern = '"' + re.escape(old) + '"'
        body, count = re.subn(pattern, '"' + new.replace("\\", "\\\\") + '"', body)
        changed += count
    return text[:start] + body + text[end:], changed


def material_group_block(materials: list[str], template: str | None = None) -> str:
    if template:
        block = extract_node(template, "DefaultMaterialGroup")
        if block:
            # Replace the whole m_materials array with our list.
            array = "[\n" + "".join(f'\t\t\t"{m}"\n' for m in materials) + "\t\t]"
            block, count = re.subn(
                r'("m_materials"\s+"string_array"\s*)\[[^\]]*\]',
                r"\1" + array,
                block,
                flags=re.S,
            )
            if count:
                return block
            # Fall back to appending a fresh array.
            return block.rstrip()[:-1] + f'\n\t\t"m_materials" "string_array"\n{array}\n\t}}\n'
    lines = [
        '"DefaultMaterialGroup" "element"',
        "{",
        '\t"m_name" "string" "default"',
        '\t"m_materials" "string_array"',
        "\t[",
    ]
    for material in materials:
        lines.append(f'\t\t"{material}"')
    lines += ["\t]", "}", ""]
    return "\n".join(lines)


def animgraph_blocks(skeleton: str, default_graph: str, ui_graph: str) -> str:
    return f'''"NmSkeletonReference" "element"
{{
	"m_skeleton" "string" "{skeleton}"
}}
"DefaultAnimGraph2" "element"
{{
	"m_animGraph" "string" "{default_graph}"
}}
"AnimGraph2" "element"
{{
	"m_name" "string" "ui"
	"m_animGraph" "string" "{ui_graph}"
}}
'''


def check(text: str) -> dict:
    report = {"nodes": {}, "counts": {}}
    for name in NODE_NAMES:
        block = extract_node(text, name)
        report["nodes"][name] = bool(block)
        if block:
            report["counts"][name] = len(re.findall(r'"m_name"', block))
    report["render_meshes"] = re.findall(
        r'"m_name"\s+"string"\s+"([^"]+)"', extract_node(text, "RenderMeshList") or ""
    )
    report["material_group_materials"] = re.findall(
        r'"([^"]+\.vmat)"', extract_node(text, "DefaultMaterialGroup") or ""
    )
    report["has_animgraph2"] = "AnimGraph2List" in report["nodes"] and report["nodes"]["AnimGraph2List"]
    report["has_nmskeleton"] = "NmSkeletonList" in report["nodes"] and report["nodes"]["NmSkeletonList"]
    return report


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def write_text(path: str, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("wrote", out)


def parse_map(raw: str) -> dict[str, str]:
    mapping = {}
    for pair in raw.split(","):
        if not pair.strip():
            continue
        if "=" not in pair:
            raise SystemExit(f"bad --map pair (expected old=new): {pair!r}")
        old, new = pair.split("=", 1)
        mapping[old.strip()] = new.strip()
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check")
    p_check.add_argument("vmdl")
    p_check.add_argument("--json-out", default=None)

    p_remove = sub.add_parser("remove-animgraph")
    p_remove.add_argument("vmdl")
    p_remove.add_argument("--out", required=True)

    p_meshes = sub.add_parser("set-render-meshes")
    p_meshes.add_argument("vmdl")
    p_meshes.add_argument("--map", required=True)
    p_meshes.add_argument("--out", required=True)

    p_mats = sub.add_parser("set-material-group")
    p_mats.add_argument("vmdl")
    p_mats.add_argument("--materials", required=True)
    p_mats.add_argument("--template", default=None)
    p_mats.add_argument("--out", required=True)

    p_graph = sub.add_parser("add-animgraph")
    p_graph.add_argument("vmdl")
    p_graph.add_argument("--skeleton", required=True)
    p_graph.add_argument("--default-graph", required=True)
    p_graph.add_argument("--ui-graph", required=True)
    p_graph.add_argument("--out", required=True)

    args = parser.parse_args()

    if args.command == "check":
        report = check(read_text(args.vmdl))
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.json_out:
            out = Path(args.json_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(report, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            print("wrote", out)
        return 0

    text = read_text(args.vmdl)

    if args.command == "remove-animgraph":
        text, removed_graph = remove_node(text, "AnimGraph2List")
        text, removed_skeleton = remove_node(text, "NmSkeletonList")
        print("removed AnimGraph2List:", removed_graph, "NmSkeletonList:", removed_skeleton)
        write_text(args.out, text)
        return 0

    if args.command == "set-render-meshes":
        mapping = parse_map(args.map)
        text, changed = replace_inside_node(text, "RenderMeshList", mapping)
        print("replacements:", changed)
        if changed == 0:
            print("WARNING: no render-mesh strings matched; inspect RenderMeshList and adjust --map")
        write_text(args.out, text)
        return 0

    if args.command == "set-material-group":
        materials = [m.strip() for m in args.materials.split(",") if m.strip()]
        template = read_text(args.template) if args.template else None
        block = material_group_block(materials, template)
        text = replace_node(text, "DefaultMaterialGroup", block)
        write_text(args.out, text)
        return 0

    if args.command == "add-animgraph":
        block = animgraph_blocks(args.skeleton, args.default_graph, args.ui_graph)
        # Remove any previous copies, then append the fresh blocks.
        for name in ("NmSkeletonReference", "DefaultAnimGraph2", "AnimGraph2"):
            text, _ = remove_node(text, name)
        text = insert_before_final_brace(text, block)
        write_text(args.out, text)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
