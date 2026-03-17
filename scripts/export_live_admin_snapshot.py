#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
from collections import defaultdict, deque
from pathlib import Path


def rpc(sock_path: str, request: str, arguments: dict | None = None) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(sock_path)
    sock.sendall(json.dumps({"request": request, "arguments": arguments or {}, "keepalive": False}).encode())
    chunks = []
    sock.settimeout(2)
    try:
      while True:
          data = sock.recv(65535)
          if not data:
              break
          chunks.append(data)
    except Exception:
      pass
    finally:
      sock.close()
    raw = b"".join(chunks).decode().strip()
    if not raw:
        return {}
    return json.loads(raw)


def short_label(address: str, key: str) -> str:
    if address:
        parts = address.split(":")
        if parts:
            return parts[-1]
    return key[:8]


def first_payload(response: dict) -> tuple[str, dict]:
    if not isinstance(response, dict):
        return "", {}
    for address, payload in response.items():
        if isinstance(payload, dict):
            return address, payload
    return "", {}


def remote_self(sock_path: str, key: str) -> tuple[str, dict]:
    raw = rpc(sock_path, "debug_remoteGetSelf", {"key": key}).get("response", {})
    return first_payload(raw)


def remote_peers(sock_path: str, key: str) -> tuple[str, list[str]]:
    raw = rpc(sock_path, "debug_remoteGetPeers", {"key": key}).get("response", {})
    _, payload = first_payload(raw)
    return _, dedupe_keys(payload.get("keys", []))


def remote_tree(sock_path: str, key: str) -> tuple[str, list[str]]:
    raw = rpc(sock_path, "debug_remoteGetTree", {"key": key}).get("response", {})
    _, payload = first_payload(raw)
    return _, dedupe_keys(payload.get("keys", []))


def dedupe_keys(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def build_layout(node_ids: list[str], links: list[dict], source_key: str) -> dict[str, tuple[float, float]]:
    adjacency = defaultdict(set)
    for link in links:
        source = link.get("source")
        target = link.get("target")
        if not source or not target or source == target:
            continue
        adjacency[source].add(target)
        adjacency[target].add(source)

    unvisited = set(node_ids)
    components = []
    roots = [source_key] if source_key in unvisited else []

    while unvisited:
        if roots:
            root = roots.pop(0)
            if root not in unvisited:
                continue
        else:
            root = sorted(unvisited)[0]

        queue = deque([root])
        component = []
        while queue:
            current = queue.popleft()
            if current not in unvisited:
                continue
            unvisited.remove(current)
            component.append(current)
            for neighbor in sorted(adjacency.get(current, [])):
                if neighbor in unvisited:
                    queue.append(neighbor)
        components.append((root, component))

    layout = {}
    component_count = max(1, len(components))
    for component_index, (root, component_nodes) in enumerate(components):
        levels = defaultdict(list)
        depths = {}
        queue = deque([(root, 0)])
        while queue:
            current, depth = queue.popleft()
            if current in depths:
                continue
            depths[current] = depth
            levels[depth].append(current)
            for neighbor in sorted(adjacency.get(current, [])):
                if neighbor not in depths:
                    queue.append((neighbor, depth + 1))

        for orphan in sorted(component_nodes):
            if orphan not in depths:
                depths[orphan] = 0
                levels[0].append(orphan)

        max_depth = max(depths.values()) if depths else 0
        segment_width = 0.76 / component_count
        segment_left = 0.12 + component_index * segment_width
        segment_inner = max(0.12, segment_width)
        for depth, keys in sorted(levels.items()):
            count = len(keys)
            for index, key in enumerate(keys):
                x_ratio = 0.5 if count == 1 else index / max(1, count - 1)
                y_ratio = 0.5 if max_depth == 0 else depth / max_depth
                layout[key] = (
                    round(segment_left + x_ratio * segment_inner, 4),
                    round(0.16 + y_ratio * 0.68, 4),
                )
    return layout


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a topology snapshot from a live Yggdrasil admin socket")
    parser.add_argument("--socket", default="/var/run/yggdrasil/yggdrasil.sock")
    parser.add_argument("--max-nodes", type=int, default=96)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    self_doc = rpc(args.socket, "getSelf").get("response", {})
    tree = rpc(args.socket, "getTree").get("response", {}).get("tree", [])
    paths = rpc(args.socket, "getPaths").get("response", {}).get("paths", [])
    sessions = rpc(args.socket, "getSessions").get("response", {}).get("sessions", [])
    peers = rpc(args.socket, "getPeers").get("response", {}).get("peers", [])

    if not self_doc.get("key"):
        raise SystemExit("getSelf returned no local key")

    tree_map = {entry["key"]: entry for entry in tree if entry.get("key")}
    path_map = {entry["key"]: entry for entry in paths if entry.get("key")}
    session_map = {entry["key"]: entry for entry in sessions if entry.get("key")}
    peer_map = {}
    for entry in peers:
        key = entry.get("key")
        if key:
            peer_map.setdefault(key, []).append(entry)

    queue = deque()
    for candidate in dedupe_keys(
        [self_doc.get("key", "")]
        + [entry.get("key", "") for entry in peers]
        + [entry.get("key", "") for entry in tree]
    ):
        queue.append(candidate)

    crawled = {}
    peer_links = set()
    discovered_total = set(queue)

    while queue and len(crawled) < args.max_nodes:
        key = queue.popleft()
        if key in crawled:
            continue

        if key == self_doc.get("key"):
            address = self_doc.get("address", "")
            remote_self_payload = {
                "key": key,
                "routing_entries": str(self_doc.get("routing_entries", "")),
            }
            peer_keys = dedupe_keys([entry.get("key", "") for entry in peers])
            tree_keys = dedupe_keys([entry.get("key", "") for entry in tree if entry.get("key") and entry.get("key") != key])
        else:
            address, remote_self_payload = remote_self(args.socket, key)
            _, peer_keys = remote_peers(args.socket, key)
            _, tree_keys = remote_tree(args.socket, key)

        info = rpc(args.socket, "getNodeInfo", {"key": key}).get("response", {}).get(key, {})
        label = info.get("name") or info.get("site") or short_label(address or tree_map.get(key, {}).get("address", ""), key)

        crawled[key] = {
            "key": key,
            "address": address or tree_map.get(key, {}).get("address", ""),
            "name": label,
            "city": info.get("city", ""),
            "country": info.get("country", ""),
            "coords": str(path_map.get(key, {}).get("path", [])),
            "metadata": {
                "owner": info.get("owner", ""),
                "site": info.get("site", ""),
                "class": info.get("class", ""),
                "transport": info.get("transport", ""),
                "routing_entries": remote_self_payload.get("routing_entries"),
                "session_uptime": session_map.get(key, {}).get("uptime"),
                "crawled_peer_count": len(peer_keys),
                "crawled_tree_count": len(tree_keys),
                "public": info.get("public", {}),
                "contact": info.get("contact", ""),
            },
        }

        for remote_key in peer_keys:
            if remote_key == key:
                continue
            peer_links.add(tuple(sorted((key, remote_key))))

        for discovered_key in dedupe_keys(peer_keys + tree_keys):
            if discovered_key not in crawled and discovered_key not in discovered_total and len(discovered_total) < args.max_nodes * 4:
                queue.append(discovered_key)
                discovered_total.add(discovered_key)

    links = []
    seen_links = set()
    for source, target in sorted(peer_links):
        if source not in crawled or target not in crawled or source == target:
            continue
        seen_links.add((source, target))
        links.append(
            {
                "source": source,
                "target": target,
                "kind": "peer",
                "metadata": {},
            }
        )

    for entry in tree:
        source = entry.get("parent")
        target = entry.get("key")
        if not source or not target or source == target:
            continue
        edge = tuple(sorted((source, target)))
        if source not in crawled or target not in crawled or edge in seen_links:
            continue
        links.append(
            {
                "source": source,
                "target": target,
                "kind": "tree",
                "metadata": {
                    "sequence": entry.get("sequence"),
                },
            }
        )

    layout = build_layout(list(crawled.keys()), links, self_doc.get("key", ""))

    nodes = []
    for key, node in crawled.items():
        x, y = layout.get(key, (0.5, 0.5))
        nodes.append(
            {
                "id": key,
                "key": key,
                "address": node["address"],
                "name": node["name"],
                "coords": node["coords"],
                "city": node["city"],
                "country": node["country"],
                "x": x,
                "y": y,
                "metadata": node["metadata"],
            }
        )

    nodes.sort(key=lambda item: (item.get("y", 0), item.get("x", 0), item.get("name", "")))

    payload = {
        "ok": True,
        "source_type": "remote_yggdrasil_crawl",
        "source_node_key": self_doc.get("key", ""),
        "source_node_address": self_doc.get("address", ""),
        "routing_entries": self_doc.get("routing_entries", 0),
        "direct_peer_count": len(peers),
        "node_count": len(nodes),
        "link_count": len(links),
        "crawl_max_nodes": args.max_nodes,
        "crawled_node_count": len(crawled),
        "nodes": nodes,
        "links": links,
    }

    serialized = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
