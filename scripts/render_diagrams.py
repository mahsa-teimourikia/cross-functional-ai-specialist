"""Validate diagram layout specifications and render deterministic SVG assets."""

from __future__ import annotations

import argparse
import html
import json
import textwrap
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]


def port_position(node: dict[str, Any], port_name: str) -> tuple[int, int]:
    bounds = node["bounds"]
    port = node["ports"][port_name]
    x = bounds["x"]
    y = bounds["y"]
    width = bounds["width"]
    height = bounds["height"]
    offset = port.get("offset", 0.5)
    side = port["side"]
    if side == "left":
        return x, round(y + height * offset)
    if side == "right":
        return x + width, round(y + height * offset)
    if side == "top":
        return round(x + width * offset), y
    if side == "bottom":
        return round(x + width * offset), y + height
    raise ValueError(f"Unknown port side: {side}")


def overlaps(first: dict[str, int], second: dict[str, int]) -> bool:
    return not (
        first["x"] + first["width"] <= second["x"]
        or second["x"] + second["width"] <= first["x"]
        or first["y"] + first["height"] <= second["y"]
        or second["y"] + second["height"] <= first["y"]
    )


def validate(spec: dict[str, Any], source: Path) -> None:
    canvas = spec["canvas"]
    margin = canvas["margin"]
    node_ids = [node["id"] for node in spec["nodes"]]
    edge_ids = [edge["id"] for edge in spec["edges"]]
    assert len(node_ids) == len(set(node_ids)), f"{source}: duplicate node ID"
    assert len(edge_ids) == len(set(edge_ids)), f"{source}: duplicate edge ID"

    nodes = {node["id"]: node for node in spec["nodes"]}
    for node in spec["nodes"]:
        bounds = node["bounds"]
        assert bounds["x"] >= margin and bounds["y"] >= 128, (
            f"{source}: {node['id']} violates outer margin/title clearance"
        )
        assert bounds["x"] + bounds["width"] <= canvas["width"] - margin
        assert bounds["y"] + bounds["height"] <= canvas["height"] - margin
        assert bounds["width"] >= 160 and bounds["height"] >= 80

    for index, first in enumerate(spec["nodes"]):
        for second in spec["nodes"][index + 1 :]:
            assert not overlaps(first["bounds"], second["bounds"]), (
                f"{source}: nodes overlap: {first['id']} and {second['id']}"
            )

    for edge in spec["edges"]:
        source_ref = edge["from"]
        target_ref = edge["to"]
        assert source_ref["node"] in nodes and target_ref["node"] in nodes
        source_node = nodes[source_ref["node"]]
        target_node = nodes[target_ref["node"]]
        assert source_ref["port"] in source_node["ports"]
        assert target_ref["port"] in target_node["ports"]
        route = [tuple(point) for point in edge["route"]]
        assert len(route) >= 2, f"{source}: {edge['id']} needs a route"
        assert route[0] == port_position(source_node, source_ref["port"]), (
            f"{source}: {edge['id']} is detached from its source port"
        )
        assert route[-1] == port_position(target_node, target_ref["port"]), (
            f"{source}: {edge['id']} is detached from its target port"
        )
        for start, end in pairwise(route):
            assert start[0] == end[0] or start[1] == end[1], (
                f"{source}: {edge['id']} must use orthogonal routing"
            )


def wrapped_lines(label: str, width: int) -> list[str]:
    return textwrap.wrap(label, width=max(12, width // 9)) or [label]


def render(spec: dict[str, Any]) -> str:
    canvas = spec["canvas"]
    colors = spec["style"]["semantic_colors"]
    width = canvas["width"]
    height = canvas["height"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{html.escape(spec["title"])}</title>',
        f'<desc id="desc">{html.escape(spec["output"]["alt_text"])}</desc>',
        "<defs>",
        '<marker id="arrow-primary" markerWidth="9" markerHeight="9" '
        'refX="8" refY="4.5" orient="auto">'
        '<path d="M0,0 L9,4.5 L0,9 z" fill="#2F6BFF"/></marker>',
        '<marker id="arrow-secondary" markerWidth="9" markerHeight="9" '
        'refX="8" refY="4.5" orient="auto">'
        '<path d="M0,0 L9,4.5 L0,9 z" fill="#52606D"/></marker>',
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="{canvas["background"]}"/>',
        f'<text x="64" y="64" font-family="{html.escape(spec["style"]["font_family"])}" '
        f'font-size="30" font-weight="700" fill="{spec["style"]["title_color"]}">'
        f"{html.escape(spec['title'])}</text>",
        f'<text x="64" y="96" font-family="{html.escape(spec["style"]["font_family"])}" '
        'font-size="16" fill="#52606D">'
        f"{html.escape(spec['purpose'])}</text>",
    ]

    for edge in spec["edges"]:
        route = edge["route"]
        points = " ".join(f"{point[0]},{point[1]}" for point in route)
        secondary = edge.get("kind") == "secondary"
        stroke = "#52606D" if secondary else "#2F6BFF"
        dash = ' stroke-dasharray="8 7"' if secondary else ""
        marker = "arrow-secondary" if secondary else "arrow-primary"
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{stroke}" stroke-width="2.5"'
            f'{dash} marker-end="url(#{marker})" stroke-linejoin="round"/>'
        )
        if label := edge.get("label"):
            start = route[len(route) // 2 - 1]
            end = route[len(route) // 2]
            label_x = (start[0] + end[0]) / 2
            label_y = (start[1] + end[1]) / 2 - 12
            parts.append(
                f'<text x="{label_x}" y="{label_y}" text-anchor="middle" '
                f'font-family="{html.escape(spec["style"]["font_family"])}" font-size="14" '
                f'fill="#334155">{html.escape(label)}</text>'
            )

    for node in spec["nodes"]:
        bounds = node["bounds"]
        palette = colors[node["type"]]
        parts.append(
            f'<rect x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" '
            f'height="{bounds["height"]}" rx="14" fill="{palette["fill"]}" '
            f'stroke="{palette["stroke"]}" stroke-width="2"/>'
        )
        lines = wrapped_lines(node["label"], bounds["width"] - 32)
        line_height = 22
        total_height = len(lines) * line_height
        start_y = bounds["y"] + (bounds["height"] - total_height) / 2 + 16
        for line_index, line in enumerate(lines):
            parts.append(
                f'<text x="{bounds["x"] + bounds["width"] / 2}" '
                f'y="{start_y + line_index * line_height}" text-anchor="middle" '
                f'font-family="{html.escape(spec["style"]["font_family"])}" font-size="17" '
                f'font-weight="600" fill="#16324F">{html.escape(line)}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("specs", nargs="*", type=Path)
    arguments = parser.parse_args()
    specs = arguments.specs or sorted(ROOT.glob("curriculum/**/assets/*-diagram-spec.json"))
    assert specs, "No diagram specifications found"
    for source in specs:
        source = source if source.is_absolute() else ROOT / source
        spec = json.loads(source.read_text(encoding="utf-8"))
        validate(spec, source)
        output = ROOT / spec["output"]["svg"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render(spec), encoding="utf-8")
        print(f"Rendered {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
