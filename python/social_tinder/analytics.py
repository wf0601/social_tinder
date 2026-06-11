"""Graph algorithms used to enrich the keyword network.

All operate on a simple weighted undirected graph expressed as:
  - node_ids: list[str]
  - adj: dict[str, list[tuple[str, float]]]   (symmetric; weight = edge strength)

Implemented here (pure-stdlib, deterministic):
  - log_likelihood_ratio : Dunning's G² for 2x2 contingency  -> edge significance
  - pagerank             : weighted PageRank                  -> keyword influence
  - betweenness          : Brandes' algorithm (unweighted)    -> bridge score
  - louvain              : modularity maximization            -> communities
"""

from __future__ import annotations

import math
from collections import deque


# --- Edge significance ------------------------------------------------------

def _g2_cell(observed: float, expected: float) -> float:
    if observed <= 0 or expected <= 0:
        return 0.0
    return observed * math.log(observed / expected)


def log_likelihood_ratio(k11: int, count_a: int, count_b: int, n: int) -> float:
    """Dunning's log-likelihood ratio (G²) for the 2x2 table of A vs B presence.

    k11 = mentions with both, count_a/count_b = marginals, n = total mentions.
    Larger => the co-occurrence is less likely to be a coincidence.
    """
    if n <= 0:
        return 0.0
    k12 = count_a - k11        # A without B
    k21 = count_b - k11        # B without A
    k22 = n - count_a - count_b + k11  # neither
    e11 = count_a * count_b / n
    e12 = count_a * (n - count_b) / n
    e21 = (n - count_a) * count_b / n
    e22 = (n - count_a) * (n - count_b) / n
    g2 = 2.0 * (
        _g2_cell(k11, e11)
        + _g2_cell(k12, e12)
        + _g2_cell(k21, e21)
        + _g2_cell(k22, e22)
    )
    return max(0.0, g2)


# --- PageRank ---------------------------------------------------------------

def pagerank(
    node_ids: list[str],
    adj: dict[str, list[tuple[str, float]]],
    damping: float = 0.85,
    max_iter: int = 200,
    tol: float = 1e-9,
) -> dict[str, float]:
    """Weighted PageRank. Returns scores summing to ~1 (uniform if no edges)."""
    n = len(node_ids)
    if n == 0:
        return {}
    out_weight = {i: sum(w for _, w in adj.get(i, [])) for i in node_ids}
    pr = {i: 1.0 / n for i in node_ids}
    base = (1.0 - damping) / n

    for _ in range(max_iter):
        dangling = sum(pr[i] for i in node_ids if out_weight[i] == 0.0)
        new = {i: base + damping * dangling / n for i in node_ids}
        for i in node_ids:
            wi = out_weight[i]
            if wi == 0.0:
                continue
            share = damping * pr[i] / wi
            for j, w in adj[i]:
                new[j] += share * w
        diff = sum(abs(new[i] - pr[i]) for i in node_ids)
        pr = new
        if diff < tol:
            break
    return pr


# --- Betweenness centrality (Brandes, unweighted) ---------------------------

def betweenness(
    node_ids: list[str],
    adj: dict[str, list[tuple[str, float]]],
) -> dict[str, float]:
    """Normalized betweenness in [0, 1]. Identifies 'bridge' keywords that sit
    on many shortest paths between communities. Treats edges as unweighted."""
    cb = {v: 0.0 for v in node_ids}
    neighbors = {v: [j for j, _ in adj.get(v, [])] for v in node_ids}

    for s in node_ids:
        stack: list[str] = []
        pred: dict[str, list[str]] = {v: [] for v in node_ids}
        sigma = {v: 0.0 for v in node_ids}
        dist = {v: -1 for v in node_ids}
        sigma[s] = 1.0
        dist[s] = 0
        q: deque[str] = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in neighbors[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = {v: 0.0 for v in node_ids}
        while stack:
            w = stack.pop()
            for v in pred[w]:
                if sigma[w] > 0:
                    delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                cb[w] += delta[w]

    # Undirected: each path counted twice. Normalize by max possible pairs.
    n = len(node_ids)
    scale = (n - 1) * (n - 2) / 2.0 if n > 2 else 0.0
    for v in node_ids:
        cb[v] /= 2.0
        cb[v] = cb[v] / scale if scale > 0 else 0.0
    return cb


# --- Louvain community detection -------------------------------------------

def louvain(
    node_ids: list[str],
    adj: dict[str, list[tuple[str, float]]],
    resolution: float = 1.0,
    max_passes: int = 20,
) -> dict[str, int]:
    """Deterministic Louvain modularity maximization. Returns node -> community
    index (small ints). Falls back to singletons when there are no edges."""
    if not node_ids:
        return {}

    # Aggregate self-loops as we coarsen; start with the raw graph.
    # graph: list of node keys; weights between super-nodes; self-loop weights.
    keys = list(node_ids)
    # adjacency as dict[key][key] = weight (undirected, stored once each dir)
    g: dict[str, dict[str, float]] = {k: {} for k in keys}
    for i in keys:
        for j, w in adj.get(i, []):
            g[i][j] = g[i].get(j, 0.0) + w
    self_loops: dict[str, float] = {k: 0.0 for k in keys}

    # Track the mapping from original nodes to current super-nodes.
    membership = {i: i for i in node_ids}

    while True:
        comm, improved = _louvain_one_level(keys, g, self_loops, resolution)
        # Re-index communities of this level to contiguous ids.
        # Update original-node membership.
        for orig, sup in membership.items():
            membership[orig] = comm[sup]
        if not improved:
            break
        # Build aggregated graph keyed by community id.
        new_keys = sorted(set(comm.values()))
        ng: dict[str, dict[str, float]] = {k: {} for k in new_keys}
        nsl: dict[str, float] = {k: 0.0 for k in new_keys}
        for i in keys:
            ci = comm[i]
            nsl[ci] += self_loops[i]
            for j, w in g[i].items():
                cj = comm[j]
                if ci == cj:
                    nsl[ci] += w  # counted once per direction -> internal*2 total
                else:
                    ng[ci][cj] = ng[ci].get(cj, 0.0) + w
        keys, g, self_loops = new_keys, ng, nsl
        if len(new_keys) == 1:
            break

    # Re-index final communities to 0..k-1 in a stable order.
    order_seen: dict[int, int] = {}
    nxt = 0
    result: dict[str, int] = {}
    for i in node_ids:  # original order is deterministic
        c = membership[i]
        if c not in order_seen:
            order_seen[c] = nxt
            nxt += 1
        result[i] = order_seen[c]
    return result


def _louvain_one_level(
    keys: list[str],
    g: dict[str, dict[str, float]],
    self_loops: dict[str, float],
    resolution: float,
) -> tuple[dict[str, int], bool]:
    """One pass of local moving. Returns (node->community-int, improved?)."""
    # Degree (k_i) includes self-loop weight twice.
    k = {i: self_loops[i] * 2 + sum(g[i].values()) for i in keys}
    m = sum(k.values()) / 2.0  # total edge weight
    if m == 0:
        return {i: idx for idx, i in enumerate(keys)}, False

    community = {i: i for i in keys}
    tot = {i: k[i] for i in keys}  # sum of degrees in each community

    improved_any = False
    moved = True
    passes = 0
    while moved and passes < 50:
        moved = False
        passes += 1
        for i in keys:
            ci = community[i]
            # weights from i to each neighboring community
            nbr_w: dict[str, float] = {}
            for j, w in g[i].items():
                if j == i:
                    continue
                nbr_w[community[j]] = nbr_w.get(community[j], 0.0) + w
            # Remove i from its community.
            tot[ci] -= k[i]
            ki_in_ci = nbr_w.get(ci, 0.0)
            # Find best community (deterministic: best gain, tie -> smallest id).
            best_c, best_gain = ci, ki_in_ci - resolution * tot[ci] * k[i] / (2.0 * m)
            for c, w_in in nbr_w.items():
                gain = w_in - resolution * tot[c] * k[i] / (2.0 * m)
                if gain > best_gain or (gain == best_gain and str(c) < str(best_c)):
                    best_c, best_gain = c, gain
            tot[best_c] += k[i]
            community[i] = best_c
            if best_c != ci:
                moved = True
                improved_any = True

    # Re-index this level's communities to contiguous ints.
    remap: dict[str, int] = {}
    nxt = 0
    out: dict[str, int] = {}
    for i in keys:
        c = community[i]
        if c not in remap:
            remap[c] = nxt
            nxt += 1
        out[i] = remap[c]
    return out, improved_any


def modularity(
    node_ids: list[str],
    adj: dict[str, list[tuple[str, float]]],
    community: dict[str, int],
    resolution: float = 1.0,
) -> float:
    """Newman modularity Q of a partition — used for tests/validation."""
    m2 = sum(w for i in node_ids for _, w in adj.get(i, []))  # = 2m
    if m2 == 0:
        return 0.0
    deg = {i: sum(w for _, w in adj.get(i, [])) for i in node_ids}
    q = 0.0
    for i in node_ids:
        for j, w in adj.get(i, []):
            if community[i] == community[j]:
                q += w - resolution * deg[i] * deg[j] / m2
    return q / m2
