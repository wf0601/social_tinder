"""The network engine. Mirrors src/lib/network/cooccurrence.ts.

Turns a flat list of mentions into a weighted keyword graph:
  - nodes  = keywords
  - edges  = co-occurrence within the same mention
  - weight = Jaccard "strength" (0..1) plus PMI for surprising pairs
Communities are found with deterministic label propagation.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone

from .types import KeywordEdge, KeywordNetwork, KeywordNode, Mention, NetworkQuery


def _sentiment_score(pos: int, neg: int, total: int) -> float:
    return 0.0 if total == 0 else (pos - neg) / total


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def build_network(
    mentions: list[Mention], query: NetworkQuery | None = None
) -> KeywordNetwork:
    q = query or NetworkQuery()

    filtered = (
        [m for m in mentions if m.platform in q.platforms]
        if q.platforms
        else mentions
    )

    # --- First pass: per-keyword stats ---
    count: dict[str, int] = defaultdict(int)
    reach: dict[str, int] = defaultdict(int)
    pos: dict[str, int] = defaultdict(int)
    neg: dict[str, int] = defaultdict(int)
    pair_count: dict[tuple[str, str], int] = defaultdict(int)

    for m in filtered:
        kws = sorted({k.lower().strip() for k in m.keywords if k.strip()})
        for k in kws:
            count[k] += 1
            reach[k] += m.reach
            if m.sentiment == "positive":
                pos[k] += 1
            elif m.sentiment == "negative":
                neg[k] += 1
        for i in range(len(kws)):
            for j in range(i + 1, len(kws)):
                pair_count[_pair_key(kws[i], kws[j])] += 1

    total_mentions = len(filtered)

    # --- Nodes: apply min_mentions, keep top-N by mentions ---
    nodes = [
        KeywordNode(
            id=k,
            mentions=c,
            reach=reach[k],
            sentiment=_sentiment_score(pos[k], neg[k], c),
            cluster=0,
        )
        for k, c in count.items()
        if c >= q.min_mentions
    ]
    nodes.sort(key=lambda n: n.mentions, reverse=True)
    if len(nodes) > q.max_nodes:
        nodes = nodes[: q.max_nodes]
    keep = {n.id for n in nodes}

    # --- Edges: Jaccard + PMI ---
    edges: list[KeywordEdge] = []
    for (a, b), co in pair_count.items():
        if co < q.min_cooccurrences or a not in keep or b not in keep:
            continue
        ca, cb = count[a], count[b]
        strength = co / (ca + cb - co)  # Jaccard
        if strength < q.min_strength:
            continue
        p_ab = co / total_mentions
        p_a = ca / total_mentions
        p_b = cb / total_mentions
        pmi = math.log2(p_ab / (p_a * p_b)) if p_ab > 0 else 0.0
        edges.append(
            KeywordEdge(source=a, target=b, cooccurrences=co, strength=strength, pmi=pmi)
        )

    # Drop isolated nodes when the graph is big enough to warrant it.
    if len(nodes) > 8:
        connected: set[str] = set()
        for e in edges:
            connected.add(e.source)
            connected.add(e.target)
        nodes = [n for n in nodes if n.id in connected]

    _assign_clusters(nodes, edges)

    return KeywordNetwork(
        nodes=nodes,
        edges=edges,
        total_mentions=total_mentions,
        generated_at=datetime.now(timezone.utc).isoformat(),
        query=q,
    )


def _assign_clusters(nodes: list[KeywordNode], edges: list[KeywordEdge]) -> None:
    """Deterministic label-propagation community detection. Mutates node.cluster."""
    label: dict[str, str] = {n.id: n.id for n in nodes}
    neighbors: dict[str, list[tuple[str, float]]] = {n.id: [] for n in nodes}
    for e in edges:
        if e.source in neighbors and e.target in neighbors:
            neighbors[e.source].append((e.target, e.strength))
            neighbors[e.target].append((e.source, e.strength))

    order = [n.id for n in nodes]
    for _ in range(12):
        changed = False
        for node_id in order:
            nbrs = neighbors[node_id]
            if not nbrs:
                continue
            tally: dict[str, float] = defaultdict(float)
            for nid, w in nbrs:
                tally[label[nid]] += w
            # Heaviest neighbor-label; tie-break by smallest label id.
            best = label[node_id]
            best_w = -1.0
            for lab, w in tally.items():
                if w > best_w or (w == best_w and lab < best):
                    best, best_w = lab, w
            if best != label[node_id]:
                label[node_id] = best
                changed = True
        if not changed:
            break

    # Re-index labels to small ints for stable coloring.
    cluster_id: dict[str, int] = {}
    nxt = 0
    for node_id in order:
        lab = label[node_id]
        if lab not in cluster_id:
            cluster_id[lab] = nxt
            nxt += 1
    for n in nodes:
        n.cluster = cluster_id[label[n.id]]
