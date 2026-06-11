# 🔥 Social Tinder — Python edition

A standalone Python port of Social Tinder. Same engine as the TypeScript app:
synthetic (or live Brandwatch) mentions → weighted keyword co-occurrence network
(**Jaccard strength** + **PMI**) → label-propagation **communities** → interactive
graph.

No JavaScript build step. Ships a **FastAPI** app and a **CLI**.

## Install

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # only needed for `serve`
```

## CLI

```bash
# Print the strongest keyword connections to the terminal (stdlib only):
python -m social_tinder top

# Export a self-contained interactive HTML you can open directly:
python -m social_tinder export -o network.html

# Dump the raw network as JSON:
python -m social_tinder json -o network.json

# Run the live app with filter sliders:
python -m social_tinder serve            # http://127.0.0.1:8000
```

All commands share the same filter flags:

```
--min-strength 0.04   --min-cooccurrences 3   --min-mentions 5
--max-nodes 80        --platforms twitter,reddit   --search "electric vehicles"
```

## Live Brandwatch data

Set the same env vars as the TS app — the badge flips to **Live Brandwatch**:

```bash
export BRANDWATCH_API_TOKEN=...
export BRANDWATCH_PROJECT_ID=...
export BRANDWATCH_QUERY_ID=...     # optional
```

Tune the field mapping in [`social_tinder/client.py`](social_tinder/client.py)
to match your account's response shape.

## Library use

```python
from social_tinder import fetch_mentions, build_network, NetworkQuery

mentions, source = fetch_mentions()
net = build_network(mentions, NetworkQuery(min_strength=0.1, min_mentions=10))
for e in sorted(net.edges, key=lambda e: -e.strength)[:5]:
    print(e.source, "<->", e.target, round(e.strength, 3))
```

## Layout

| Module | Role |
| --- | --- |
| `social_tinder/types.py` | dataclasses (`Mention`, `KeywordNode`, `KeywordEdge`, …) |
| `social_tinder/sample.py` | deterministic synthetic dataset (ports the JS `mulberry32` PRNG) |
| `social_tinder/network.py` | co-occurrence engine: Jaccard, PMI, clustering |
| `social_tinder/client.py` | sample ↔ Brandwatch data source (stdlib `urllib`) |
| `social_tinder/viz.py` | vis-network HTML (interactive + static) |
| `social_tinder/server.py` | FastAPI app (`/` UI + `/api/network`) |
| `social_tinder/__main__.py` | CLI |

Both editions port the same seeded `mulberry32` PRNG, so each is fully
deterministic. They are **not** byte-for-byte identical to each other, though:
JS's `sort(() => rng()-0.5)` consumes a variable number of random draws per
shuffle while Python's `sorted(key=...)` draws once per element, so the streams
diverge. The datasets are statistically equivalent (same themes and structure),
not the same rows.
