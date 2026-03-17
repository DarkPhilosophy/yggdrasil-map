# Upstream Audit

## Repositories

- Original historical base: `zielmicha/fc00.org`
- Yggdrasil-focused fork: `Arceliar/yggdrasil-map`

## Why the fork is still the better base

The GitHub "behind" count is misleading here because the projects diverged.

- `Arceliar/yggdrasil-map`
  - latest branch tip observed: `2023-11-04`
  - adapted for Yggdrasil
  - includes Yggdrasil-specific crawler and `current` snapshot flow
- `zielmicha/fc00.org`
  - latest branch tip observed: `2019-10-08`
  - historical Hyperboria/cjdns project

## Useful files

- `scripts/crawler.go`
- `web/updateGraph.py`
- `web/graphPlotter.py`
- `web/static/network.js`

## What to extract

- graph shape
- crawler ideas
- snapshot format
- topology semantics from coordinates

## What to leave behind

- Python 2
- Flask app
- jQuery canvas UI
- MySQL/FCGI deployment model
