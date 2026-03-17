#!/usr/bin/env python3
"""
Build a compact topology snapshot for a modern frontend.

Input:
  - a JSON file shaped like the legacy `current` payload:
      { "yggnodes": { "<key>": { "address": "...", "coords": "[...]", "nodeinfo": { "name": "..." } } } }

Output:
  - a normalized JSON graph with nodes/links/stats
"""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NodeInfo:
    key: str
    address: str
    coords: str
    name: str

    def coord_list(self) -> list[str]:
        return [part for part in self.coords.strip("[]").split(" ") if part]

    def parent_coords(self) -> str:
        parts = self.coord_list()
        if not parts:
            return "[]"
        return "[" + " ".join(parts[:-1]).strip() + "]"


def load_snapshot(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize(snapshot: dict) -> dict:
    raw = snapshot.get("yggnodes", {})
    discovered: list[NodeInfo] = []

    for key, payload in raw.items():
      address = payload.get("address")
      coords = payload.get("coords")
      if not address or not coords:
          continue

      name = payload.get("nodeinfo", {}).get("name") or str(address).split(":")[-1]
      discovered.append(
          NodeInfo(
              key=str(key),
              address=str(address),
              coords=str(coords),
              name=html.escape(str(name))[:64],
          )
      )

    nodes_by_coords: dict[str, NodeInfo] = {}

    def ensure_ancestors(node: NodeInfo) -> None:
        parent_coords = node.parent_coords()
        if parent_coords == node.coords:
            return
        if parent_coords not in nodes_by_coords:
            nodes_by_coords[parent_coords] = NodeInfo(
                key=f"coord:{parent_coords}",
                address=f"? {parent_coords}",
                coords=parent_coords,
                name=f"? {parent_coords}",
            )
            ensure_ancestors(nodes_by_coords[parent_coords])

    for node in discovered:
        ensure_ancestors(node)
    for node in discovered:
        nodes_by_coords[node.coords] = node

    ordered_nodes = sorted(nodes_by_coords.values(), key=lambda item: (len(item.coord_list()), item.coords))
    links = []
    for node in ordered_nodes:
        parent_coords = node.parent_coords()
        if parent_coords == node.coords or parent_coords not in nodes_by_coords:
            continue
        links.append(
            {
                "source": node.coords,
                "target": parent_coords,
                "kind": "tree",
            }
        )

    return {
        "ok": True,
        "source_type": "legacy_current_snapshot",
        "node_count": len(ordered_nodes),
        "link_count": len(links),
        "nodes": [
            {
                "id": node.coords,
                "key": node.key,
                "address": node.address,
                "name": node.name,
                "coords": node.coords,
            }
            for node in ordered_nodes
        ],
        "links": links,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a normalized AXXA map snapshot")
    parser.add_argument("input", type=Path, help="Path to a legacy current snapshot JSON file")
    parser.add_argument("-o", "--output", type=Path, help="Write output to a file instead of stdout")
    args = parser.parse_args()

    payload = normalize(load_snapshot(args.input))
    serialized = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"

    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
