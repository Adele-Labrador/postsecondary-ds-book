"""Decode the us-atlas Albers TopoJSON into ready-to-render SVG paths.

The dashboard map needs state outlines plus institution dots that line up with
them. ``states-albers-10m.json`` is already projected with

    d3.geoAlbersUsa().scale(1300).translate([487.5, 305])

into a 975x610 viewBox, so decoding it here gives exact SVG path strings and
the browser can project institution lat/lon with the same parameters via d3.
Doing the decode at build time keeps topojson-client out of the page.

Run:
    python -m src.ingest.build_us_map

Input:  dashboard/data/states-albers-10m.json  (downloaded from us-atlas)
Output: dashboard/data/us-states.json
"""

from __future__ import annotations

import json
from pathlib import Path

SRC = Path("dashboard/data/states-albers-10m.json")
OUT = Path("dashboard/data/us-states.json")

VIEWBOX = "-62 0 1042 615"


def decode_arcs(topology: dict) -> list[list[tuple[float, float]]]:
    """Undo TopoJSON quantization and delta encoding into absolute points."""
    transform = topology.get("transform")
    if transform:
        sx, sy = transform["scale"]
        tx, ty = transform["translate"]
    else:
        sx = sy = 1.0
        tx = ty = 0.0

    arcs = []
    for arc in topology["arcs"]:
        x = y = 0
        points = []
        for dx, dy in arc:
            x += dx
            y += dy
            points.append((x * sx + tx, y * sy + ty))
        arcs.append(points)
    return arcs


def arc_points(arcs, index: int) -> list[tuple[float, float]]:
    """Resolve an arc reference; negative indices mean traverse in reverse."""
    if index < 0:
        return arcs[~index][::-1]
    return arcs[index]


def ring_to_path(arcs, ring: list[int]) -> str:
    points: list[tuple[float, float]] = []
    for index in ring:
        segment = arc_points(arcs, index)
        # Consecutive arcs share an endpoint; drop the duplicate join point.
        points.extend(segment[1:] if points else segment)
    if not points:
        return ""
    head = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    body = "".join(f"L{x:.1f},{y:.1f}" for x, y in points[1:])
    return head + body + "Z"


def geometry_to_path(arcs, geometry: dict) -> str:
    kind = geometry.get("type")
    if kind == "Polygon":
        polygons = [geometry["arcs"]]
    elif kind == "MultiPolygon":
        polygons = geometry["arcs"]
    else:
        return ""
    return "".join(ring_to_path(arcs, ring) for polygon in polygons for ring in polygon)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"Missing {SRC}. Download it first:\n"
            "  curl -sfL https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json "
            f"-o {SRC}"
        )

    topology = json.loads(SRC.read_text())
    arcs = decode_arcs(topology)

    states = []
    for geometry in topology["objects"]["states"]["geometries"]:
        path = geometry_to_path(arcs, geometry)
        if not path:
            continue
        props = geometry.get("properties") or {}
        states.append({"name": props.get("name"), "d": path})

    nation = geometry_to_path(arcs, topology["objects"]["nation"]["geometries"][0])

    payload = {
        "viewBox": VIEWBOX,
        "projection": {"type": "albersUsa", "scale": 1300, "translate": [487.5, 305]},
        "nation": nation,
        "states": states,
    }
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Wrote {OUT} ({len(states)} states, {OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
