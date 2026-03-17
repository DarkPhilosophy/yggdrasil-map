## AXXA Modernization Plan

This repository is a useful reference for Yggdrasil topology collection, but not a good web stack to ship as-is.

### What is still valuable

- `web/updateGraph.py` explains the current data flow:
  - read a Yggdrasil network snapshot (`current`)
  - derive parent/child links from tree coordinates
  - emit `static/graph.json`
- `web/graphPlotter.py` defines the legacy graph JSON format:
  - `created`
  - `nodes[]`
  - `edges[]`
- `scripts/crawler.go` is the most interesting collector logic in the repo.

### What should not be carried forward

- Python 2 Flask app in `web/web.py`
- jQuery canvas frontend in `web/static/network.js`
- old MySQL/FCGI assumptions
- Graphviz-bound rendering pipeline as a runtime dependency for the website

### Recommended architecture for AXXA

1. Keep collection separate from presentation.
2. Produce a clean JSON snapshot from a collector job.
3. Serve the snapshot through `ygg.axxa.dev/api/*`.
4. Render `/map` in the existing Cloudflare Worker frontend.

### Proposed split

- `collector/`
  - Yggdrasil crawler or importer
  - normalization step
  - snapshot writer
- `docs/`
  - reverse-engineering notes
  - data schema
- existing AXXA worker
  - browser rendering
  - interaction, animation, filtering

### Practical migration path

#### Phase 1

- Reuse the upstream graph format as a compatibility target.
- Build a small exporter that can emit:
  - nodes
  - edges
  - timestamps
  - optional reachability metadata

#### Phase 2

- Replace Graphviz layout with a browser-side layout or precomputed positions.
- Keep the map interactive and animated in the Worker frontend.

#### Phase 3

- Add richer metadata:
  - node labels
  - owners
  - protocols
  - probe latency
  - reachability state

### Current recommendation

Use this repository as a data-source and topology-reference project.
Do not deploy this web stack directly.
