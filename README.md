# 🔥 Social Tinder

**Keyword chemistry from social listening.** Social Tinder turns Brandwatch
social-media data into an interactive network graph: each node is a keyword,
each edge shows how strongly two keywords *connect* — i.e. how often they show
up together in the same conversations.

Think of it as matchmaking for topics: it surfaces which terms have chemistry,
which cluster into communities, and which surprising pairings beat random chance.

---

## Two editions

This repo ships the same engine twice, so you can use whichever fits:

| Edition | Stack | Best for | Docs |
| --- | --- | --- | --- |
| **Web app** (root) | Next.js 16 · React 19 · TypeScript · Tailwind · react-force-graph | A polished, deployable interactive product | this file |
| **Python** ([`python/`](python/)) | FastAPI · vis-network · stdlib | Notebooks, data pipelines, a CLI, or a no-JS-build server | [python/README.md](python/README.md) |

Both run the same analytics: synthetic (or live Brandwatch) mentions → weighted
keyword co-occurrence graph (**Jaccard strength**, **PMI**, **log-likelihood
G²**) → **Louvain** communities, with each keyword scored by **PageRank**
(influence) and **betweenness** (bridge). They share the same `BRANDWATCH_*`
env vars and filter semantics, and the two engines are kept in lockstep (the
Python `analytics.py` and TS `analytics.ts` produce identical results on
identical input — verified by unit tests).

> The two editions port the same seeded `mulberry32` PRNG, so each is fully
> deterministic — but they are **not** byte-for-byte identical to each other
> (JS's `sort(() => rng()-0.5)` and Python's `sorted(key=...)` consume randoms
> differently). The sample datasets are statistically equivalent, not the same
> rows.

---

## What it does

- **Co-occurrence network** — two keywords appearing in the same post create/
  strengthen an edge.
- **Connection strength & significance** — every edge has a Jaccard *strength*
  (0–1, "how connected are these"), a *PMI* score (surprising associations), and
  a *log-likelihood ratio* G² (statistical significance, for pruning coincidences).
- **Influence & bridges** — keywords are scored by **PageRank** (how central /
  influential a term is) and **betweenness** (which terms *bridge* communities —
  often the most strategically interesting).
- **Communities** — **Louvain** modularity clustering colors thematically
  related keywords together.
- **Live filtering** — thresholds for strength, co-occurrence count, keyword
  frequency, **significance**, node cap, and platform; size nodes by mentions,
  reach, influence, or bridge score.
- **Drill-down** — inspect any keyword's mentions, reach, net sentiment,
  influence, bridge score, and strongest connections.

---

## Web app (TypeScript)

```bash
npm install
npm run dev
```

Open http://localhost:3000. With no credentials it runs on a built-in synthetic
dataset (amber **Sample data** badge).

### Architecture

| Layer | File |
| --- | --- |
| Types / data model | [`src/lib/brandwatch/types.ts`](src/lib/brandwatch/types.ts) |
| Data source (sample ↔ live) | [`src/lib/brandwatch/client.ts`](src/lib/brandwatch/client.ts) |
| Synthetic dataset | [`src/lib/brandwatch/sample.ts`](src/lib/brandwatch/sample.ts) |
| Network engine (Jaccard, PMI, G², orchestration) | [`src/lib/network/cooccurrence.ts`](src/lib/network/cooccurrence.ts) |
| Graph algorithms (PageRank, betweenness, Louvain) | [`src/lib/network/analytics.ts`](src/lib/network/analytics.ts) |
| API endpoint | [`src/app/api/network/route.ts`](src/app/api/network/route.ts) |
| Force-graph visualization | [`src/components/NetworkGraph.tsx`](src/components/NetworkGraph.tsx) |
| App UI | [`src/app/page.tsx`](src/app/page.tsx) |

### Deploy

```bash
vercel deploy        # preview
vercel deploy --prod # production
```

Set the `BRANDWATCH_*` env vars in your Vercel project to go live.

---

## Python edition

A standalone port with a CLI and a FastAPI server — no JS build step. Full
details in [python/README.md](python/README.md).

```bash
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # only needed for `serve`

python -m social_tinder top                  # strongest connections in terminal
python -m social_tinder export -o net.html   # self-contained interactive HTML
python -m social_tinder serve                # live app at http://127.0.0.1:8000
```

---

## Connect real Brandwatch data

Both editions read the same environment variables. Leave them unset to run on
the sample dataset (amber **Sample data** badge); set them to pull live
Brandwatch Consumer Research mentions (green **Live Brandwatch** badge).

```
BRANDWATCH_API_TOKEN=...      # OAuth2 bearer token
BRANDWATCH_PROJECT_ID=...     # Consumer Research project id
BRANDWATCH_QUERY_ID=...       # optional saved query/search id
BRANDWATCH_API_BASE=...       # optional base URL override
```

For the web app, copy `.env.example` to `.env.local`. The Brandwatch → internal
mapping lives in [`src/lib/brandwatch/client.ts`](src/lib/brandwatch/client.ts)
(TS) and [`python/social_tinder/client.py`](python/social_tinder/client.py)
(Python) — adjust the field paths (`matchPositions` / `categories` / `tags` /
sentiment / reach) to match your account's response shape.

> ⚠️ The live Brandwatch mapping is written against the documented API shape but
> has not been tested against a live account. Validate it when you wire in real
> credentials.

---

## The analytics

**Edge measures** — for keywords *A* and *B* appearing in the same mentions:

- **Co-occurrence** = number of mentions containing both.
- **Strength (Jaccard)** = `co(A,B) / (count(A) + count(B) − co(A,B))` — robust
  to popular terms dominating.
- **PMI** = `log₂( P(A,B) / (P(A)·P(B)) )` — positive means the pair appears
  together more than chance would predict.
- **Significance (Dunning G²)** = log-likelihood ratio over the 2×2 presence
  table. Unlike PMI it stays reliable for rare terms, so the **Min. significance**
  filter prunes coincidental edges cleanly.

**Node measures** — computed on the final graph:

- **Influence (PageRank)** — weighted PageRank over edge strengths. Surfaces
  central, well-connected keywords.
- **Bridge (betweenness)** — Brandes' algorithm; fraction of shortest paths a
  keyword sits on. High-bridge terms connect otherwise-separate communities.
- **Community (Louvain)** — modularity maximization; no preset cluster count,
  near-linear, and sharper than the label-propagation it replaced.

The graph algorithms live in
[`src/lib/network/analytics.ts`](src/lib/network/analytics.ts) /
[`python/social_tinder/analytics.py`](python/social_tinder/analytics.py), with
unit tests in [`python/tests/`](python/tests/).
