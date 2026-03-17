#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
from collections import defaultdict, deque
from pathlib import Path


def rpc(sock_path: str, request: str, arguments: dict | None = None) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    s.sendall(json.dumps({"request": request, "arguments": arguments or {}, "keepalive": False}).encode())
    chunks = []
    s.settimeout(2)
    try:
        while True:
            data = s.recv(65535)
            if not data:
                break
            chunks.append(data)
    except Exception:
        pass
    finally:
        s.close()
    raw = b"".join(chunks).decode().strip()
    if not raw:
        return {}
    return json.loads(raw)


def short_label(address: str) -> str:
    parts = address.split(":")
    return parts[-1] if parts else address


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a topology snapshot from a live Yggdrasil admin socket")
    parser.add_argument("--socket", default="/var/run/yggdrasil/yggdrasil.sock")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    self_doc = rpc(args.socket, "getSelf").get("response", {})
    tree = rpc(args.socket, "getTree").get("response", {}).get("tree", [])
    paths = rpc(args.socket, "getPaths").get("response", {}).get("paths", [])
    sessions = rpc(args.socket, "getSessions").get("response", {}).get("sessions", [])
    peers = rpc(args.socket, "getPeers").get("response", {}).get("peers", [])

    if not tree:
        raise SystemExit("getTree returned no entries")

    key_to_tree = {entry["key"]: entry for entry in tree if entry.get("key")}
    nodeinfo = {}
    for key in list(key_to_tree.keys()):
        try:
            info = rpc(args.socket, "getNodeInfo", {"key": key}).get("response", {}).get(key, {})
        except Exception:
            info = {}
        nodeinfo[key] = info

    children = defaultdict(list)
    roots = []
    for entry in tree:
        key = entry["key"]
        parent = entry.get("parent")
        if parent == key or parent not in key_to_tree:
            roots.append(key)
        else:
            children[parent].append(key)

    if not roots:
        roots = [self_doc.get("key")] if self_doc.get("key") else [tree[0]["key"]]

    depth = {}
    order_by_depth = defaultdict(list)
    queue = deque((root, 0) for root in roots)
    seen = set()
    while queue:
        key, d = queue.popleft()
        if key in seen:
            continue
        seen.add(key)
        depth[key] = d
        order_by_depth[d].append(key)
        for child in children.get(key, []):
            queue.append((child, d + 1))

    max_depth = max(depth.values()) if depth else 0
    path_map = {item["key"]: item for item in paths if item.get("key")}
    session_map = {item["key"]: item for item in sessions if item.get("key")}

    nodes = []
    for d, keys in sorted(order_by_depth.items()):
        count = len(keys)
        for idx, key in enumerate(keys):
            entry = key_to_tree[key]
            info = nodeinfo.get(key, {})
            label = info.get("name") or info.get("site") or short_label(entry.get("address", ""))
            x = 0.5 if count == 1 else idx / max(1, count - 1)
            y = 0.12 if max_depth == 0 else d / max_depth
            nodes.append(
                {
                    "id": key,
                    "key": key,
                    "address": entry.get("address", ""),
                    "name": label,
                    "coords": str(path_map.get(key, {}).get("path", [])),
                    "city": "",
                    "country": "",
                    "x": round(0.12 + x * 0.76, 4),
                    "y": round(0.16 + y * 0.68, 4),
                    "metadata": {
                        "parent": entry.get("parent", ""),
                        "sequence": entry.get("sequence"),
                        "routing_entries": info.get("routing_entries") or info.get("routingentries"),
                        "owner": info.get("owner", ""),
                        "site": info.get("site", ""),
                        "class": info.get("class", ""),
                        "transport": info.get("transport", ""),
                        "session_uptime": session_map.get(key, {}).get("uptime"),
                    },
                }
            )

    links = []
    for entry in tree:
        key = entry["key"]
        parent = entry.get("parent")
        if not parent or parent == key or parent not in key_to_tree:
            continue
        links.append(
            {
                "source": parent,
                "target": key,
                "kind": "tree",
                "metadata": {
                    "sequence": entry.get("sequence"),
                },
            }
        )

    payload = {
        "ok": True,
        "source_type": "live_yggdrasil_admin",
        "source_node_key": self_doc.get("key", ""),
        "source_node_address": self_doc.get("address", ""),
        "routing_entries": self_doc.get("routing_entries", 0),
        "node_count": len(nodes),
        "link_count": len(links),
        "direct_peer_count": len(peers),
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
