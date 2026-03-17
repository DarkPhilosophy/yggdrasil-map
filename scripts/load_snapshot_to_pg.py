#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path


def run_psql(sql_text: str, *, host: str, port: int, dbname: str, user: str, password: str) -> str:
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(sql_text)
        temp_path = handle.name

    try:
        proc = subprocess.run(
            [
                "psql",
                "-h", host,
                "-p", str(port),
                "-U", user,
                "-d", dbname,
                "-v", "ON_ERROR_STOP=1",
                "-Atf", temp_path,
            ],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"psql failed with code {proc.returncode}")
    return proc.stdout.strip()


def quoted_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=True)
    return payload.replace("'", "''")


def quoted_text(value) -> str:
    return str(value).replace("'", "''")


def build_sql(payload: dict, source: str, source_revision: str) -> str:
    nodes = payload.get("nodes", [])
    links = payload.get("links", [])
    snapshot_payload = quoted_json(payload)

    statements = [
        "begin;",
        (
            "insert into topology_snapshot "
            "(source, source_revision, node_count, link_count, payload) "
            f"values ('{quoted_text(source)}', "
            f"'{quoted_text(source_revision)}', "
            f"{len(nodes)}, {len(links)}, '{snapshot_payload}'::jsonb) "
            "returning id;"
        ),
    ]

    for node in nodes:
        metadata = {
            "browser_probe_url": node.get("browser_probe_url", ""),
            "tls_uri": node.get("tls_uri", ""),
            "quic_uri": node.get("quic_uri", ""),
            "ygg_address": node.get("ygg_address", ""),
        }
        statements.append(
            "insert into topology_node "
            "(snapshot_id, node_id, node_key, address, name, coords, city, country, x, y, metadata) "
            "select currval('topology_snapshot_id_seq'), "
            f"'{quoted_text(node.get('id', ''))}', "
            f"'{quoted_text(node.get('key', ''))}', "
            f"'{quoted_text(node.get('address', ''))}', "
            f"'{quoted_text(node.get('name', ''))}', "
            f"'{quoted_text(node.get('coords', ''))}', "
            f"'{quoted_text(node.get('city', ''))}', "
            f"'{quoted_text(node.get('country', ''))}', "
            f"{'null' if node.get('x') is None else float(node.get('x'))}, "
            f"{'null' if node.get('y') is None else float(node.get('y'))}, "
            f"'{quoted_json(metadata)}'::jsonb;"
        )

    for link in links:
        statements.append(
            "insert into topology_link "
            "(snapshot_id, source_node_id, target_node_id, kind, metadata) "
            "select currval('topology_snapshot_id_seq'), "
            f"'{quoted_text(link.get('source', ''))}', "
            f"'{quoted_text(link.get('target', ''))}', "
            f"'{quoted_text(link.get('kind', 'mesh'))}', "
            f"'{quoted_json(link.get('metadata', {}))}'::jsonb;"
        )

    statements.append(
        "select currval('topology_snapshot_id_seq') || '|' || "
        "(select node_count from topology_snapshot where id = currval('topology_snapshot_id_seq')) || '|' || "
        "(select link_count from topology_snapshot where id = currval('topology_snapshot_id_seq'));"
    )
    statements.append("commit;")
    return "\n".join(statements) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Load a normalized Ygg map snapshot into PostgreSQL")
    parser.add_argument("input", help="Path to normalized snapshot JSON or - for stdin")
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "15432")))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "ygg"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""))
    parser.add_argument("--source", default="axxa-api")
    parser.add_argument("--source-revision", default="manual")
    args = parser.parse_args()

    if args.input == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = run_psql(
      build_sql(payload, args.source, args.source_revision),
      host=args.host,
      port=args.port,
      dbname=args.dbname,
      user=args.user,
      password=args.password,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
