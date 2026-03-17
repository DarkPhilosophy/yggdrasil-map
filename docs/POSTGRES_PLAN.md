# PostgreSQL Plan

`pg.axxa.dev` is useful for the parts that static JSON cannot handle well:

- historical topology snapshots
- per-node probe history
- later comparisons between snapshots
- future uptime and latency charts

## Minimal flow

1. Collector fetches or builds a normalized snapshot.
2. Snapshot is inserted into `topology_snapshot`.
3. Nodes are inserted into `topology_node`.
4. Links are inserted into `topology_link`.
5. Probe jobs append rows to `topology_probe`.

## Why this is worth it

- the Worker stays simple
- the frontend can query a latest snapshot
- historical analytics stop depending on flat files
- topology and reachability become queryable separately

## First SQL migration

See `sql/001_axxa_map.sql`.
