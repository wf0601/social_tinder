// Graph algorithms that enrich the keyword network. Ports of the Python
// social_tinder/analytics.py — kept in lockstep so both editions agree.
//
// All operate on a weighted undirected graph:
//   nodeIds: string[]
//   adj: Map<string, [string, number][]>   (symmetric; weight = edge strength)

// --- Edge significance ------------------------------------------------------

function g2Cell(observed: number, expected: number): number {
  if (observed <= 0 || expected <= 0) return 0;
  return observed * Math.log(observed / expected);
}

/**
 * Dunning's log-likelihood ratio (G²) for the 2x2 table of A vs B presence.
 * Larger => the co-occurrence is less likely to be coincidental.
 */
export function logLikelihoodRatio(
  k11: number,
  countA: number,
  countB: number,
  n: number,
): number {
  if (n <= 0) return 0;
  const k12 = countA - k11; // A without B
  const k21 = countB - k11; // B without A
  const k22 = n - countA - countB + k11; // neither
  const e11 = (countA * countB) / n;
  const e12 = (countA * (n - countB)) / n;
  const e21 = ((n - countA) * countB) / n;
  const e22 = ((n - countA) * (n - countB)) / n;
  const g2 =
    2 * (g2Cell(k11, e11) + g2Cell(k12, e12) + g2Cell(k21, e21) + g2Cell(k22, e22));
  return Math.max(0, g2);
}

// --- PageRank ---------------------------------------------------------------

/** Weighted PageRank. Returns scores summing to ~1 (uniform if no edges). */
export function pagerank(
  nodeIds: string[],
  adj: Map<string, [string, number][]>,
  damping = 0.85,
  maxIter = 200,
  tol = 1e-9,
): Map<string, number> {
  const n = nodeIds.length;
  const pr = new Map<string, number>();
  if (n === 0) return pr;

  const outWeight = new Map<string, number>();
  for (const i of nodeIds) {
    outWeight.set(i, (adj.get(i) ?? []).reduce((s, [, w]) => s + w, 0));
    pr.set(i, 1 / n);
  }
  const base = (1 - damping) / n;

  for (let iter = 0; iter < maxIter; iter++) {
    let dangling = 0;
    for (const i of nodeIds) if (outWeight.get(i) === 0) dangling += pr.get(i)!;
    const next = new Map<string, number>();
    for (const i of nodeIds) next.set(i, base + (damping * dangling) / n);
    for (const i of nodeIds) {
      const wi = outWeight.get(i)!;
      if (wi === 0) continue;
      const share = (damping * pr.get(i)!) / wi;
      for (const [j, w] of adj.get(i)!) next.set(j, next.get(j)! + share * w);
    }
    let diff = 0;
    for (const i of nodeIds) diff += Math.abs(next.get(i)! - pr.get(i)!);
    for (const i of nodeIds) pr.set(i, next.get(i)!);
    if (diff < tol) break;
  }
  return pr;
}

// --- Betweenness centrality (Brandes, unweighted) ---------------------------

/**
 * Normalized betweenness in [0, 1]. Identifies "bridge" keywords on many
 * shortest paths between communities. Treats edges as unweighted.
 */
export function betweenness(
  nodeIds: string[],
  adj: Map<string, [string, number][]>,
): Map<string, number> {
  const cb = new Map<string, number>(nodeIds.map((v) => [v, 0]));
  const neighbors = new Map<string, string[]>(
    nodeIds.map((v) => [v, (adj.get(v) ?? []).map(([j]) => j)]),
  );

  for (const s of nodeIds) {
    const stack: string[] = [];
    const pred = new Map<string, string[]>(nodeIds.map((v) => [v, []]));
    const sigma = new Map<string, number>(nodeIds.map((v) => [v, 0]));
    const dist = new Map<string, number>(nodeIds.map((v) => [v, -1]));
    sigma.set(s, 1);
    dist.set(s, 0);
    const queue: string[] = [s];
    let head = 0;
    while (head < queue.length) {
      const v = queue[head++];
      stack.push(v);
      for (const w of neighbors.get(v)!) {
        if (dist.get(w)! < 0) {
          dist.set(w, dist.get(v)! + 1);
          queue.push(w);
        }
        if (dist.get(w) === dist.get(v)! + 1) {
          sigma.set(w, sigma.get(w)! + sigma.get(v)!);
          pred.get(w)!.push(v);
        }
      }
    }
    const delta = new Map<string, number>(nodeIds.map((v) => [v, 0]));
    while (stack.length) {
      const w = stack.pop()!;
      for (const v of pred.get(w)!) {
        if (sigma.get(w)! > 0) {
          delta.set(v, delta.get(v)! + (sigma.get(v)! / sigma.get(w)!) * (1 + delta.get(w)!));
        }
      }
      if (w !== s) cb.set(w, cb.get(w)! + delta.get(w)!);
    }
  }

  const n = nodeIds.length;
  const scale = n > 2 ? ((n - 1) * (n - 2)) / 2 : 0;
  for (const v of nodeIds) {
    const halved = cb.get(v)! / 2; // undirected: each path counted twice
    cb.set(v, scale > 0 ? halved / scale : 0);
  }
  return cb;
}

// --- Louvain community detection -------------------------------------------

type WeightMap = Map<string, Map<string, number>>;

/**
 * Deterministic Louvain modularity maximization. Returns node -> community
 * index (small ints).
 */
export function louvain(
  nodeIds: string[],
  adj: Map<string, [string, number][]>,
  resolution = 1,
): Map<string, number> {
  const result = new Map<string, number>();
  if (nodeIds.length === 0) return result;

  let keys = [...nodeIds];
  let g: WeightMap = new Map(keys.map((k) => [k, new Map<string, number>()]));
  for (const i of keys) {
    for (const [j, w] of adj.get(i) ?? []) {
      g.get(i)!.set(j, (g.get(i)!.get(j) ?? 0) + w);
    }
  }
  let selfLoops = new Map<string, number>(keys.map((k) => [k, 0]));
  const membership = new Map<string, string>(nodeIds.map((i) => [i, i]));

  for (;;) {
    const { comm, improved } = louvainOneLevel(keys, g, selfLoops, resolution);
    for (const [orig, sup] of membership) membership.set(orig, String(comm.get(sup)!));
    if (!improved) break;

    const newKeys = [...new Set([...comm.values()])].sort((a, b) => a - b).map(String);
    const ng: WeightMap = new Map(newKeys.map((k) => [k, new Map<string, number>()]));
    const nsl = new Map<string, number>(newKeys.map((k) => [k, 0]));
    for (const i of keys) {
      const ci = String(comm.get(i)!);
      nsl.set(ci, nsl.get(ci)! + selfLoops.get(i)!);
      for (const [j, w] of g.get(i)!) {
        const cj = String(comm.get(j)!);
        if (ci === cj) nsl.set(ci, nsl.get(ci)! + w);
        else ng.get(ci)!.set(cj, (ng.get(ci)!.get(cj) ?? 0) + w);
      }
    }
    keys = newKeys;
    g = ng;
    selfLoops = nsl;
    if (newKeys.length === 1) break;
  }

  // Re-index final communities to 0..k-1 in original-node order.
  const remap = new Map<string, number>();
  let nextId = 0;
  for (const i of nodeIds) {
    const c = membership.get(i)!;
    if (!remap.has(c)) remap.set(c, nextId++);
    result.set(i, remap.get(c)!);
  }
  return result;
}

function louvainOneLevel(
  keys: string[],
  g: WeightMap,
  selfLoops: Map<string, number>,
  resolution: number,
): { comm: Map<string, number>; improved: boolean } {
  const k = new Map<string, number>();
  for (const i of keys) {
    let deg = selfLoops.get(i)! * 2;
    for (const [, w] of g.get(i)!) deg += w;
    k.set(i, deg);
  }
  const m = [...k.values()].reduce((s, v) => s + v, 0) / 2;
  if (m === 0) {
    return { comm: new Map(keys.map((i, idx) => [i, idx])), improved: false };
  }

  const community = new Map<string, string>(keys.map((i) => [i, i]));
  const tot = new Map<string, number>(keys.map((i) => [i, k.get(i)!]));

  let improvedAny = false;
  let moved = true;
  let passes = 0;
  while (moved && passes < 50) {
    moved = false;
    passes++;
    for (const i of keys) {
      const ci = community.get(i)!;
      const nbrW = new Map<string, number>();
      for (const [j, w] of g.get(i)!) {
        if (j === i) continue;
        const cj = community.get(j)!;
        nbrW.set(cj, (nbrW.get(cj) ?? 0) + w);
      }
      tot.set(ci, tot.get(ci)! - k.get(i)!);
      let bestC = ci;
      let bestGain = (nbrW.get(ci) ?? 0) - (resolution * tot.get(ci)! * k.get(i)!) / (2 * m);
      for (const [c, wIn] of nbrW) {
        const gain = wIn - (resolution * tot.get(c)! * k.get(i)!) / (2 * m);
        if (gain > bestGain || (gain === bestGain && c < bestC)) {
          bestC = c;
          bestGain = gain;
        }
      }
      tot.set(bestC, tot.get(bestC)! + k.get(i)!);
      community.set(i, bestC);
      if (bestC !== ci) {
        moved = true;
        improvedAny = true;
      }
    }
  }

  const remap = new Map<string, number>();
  let nextId = 0;
  const comm = new Map<string, number>();
  for (const i of keys) {
    const c = community.get(i)!;
    if (!remap.has(c)) remap.set(c, nextId++);
    comm.set(i, remap.get(c)!);
  }
  return { comm, improved: improvedAny };
}

/** Newman modularity Q of a partition — exported for tests/validation. */
export function modularity(
  nodeIds: string[],
  adj: Map<string, [string, number][]>,
  community: Map<string, number>,
  resolution = 1,
): number {
  let m2 = 0;
  for (const i of nodeIds) for (const [, w] of adj.get(i) ?? []) m2 += w;
  if (m2 === 0) return 0;
  const deg = new Map<string, number>();
  for (const i of nodeIds) deg.set(i, (adj.get(i) ?? []).reduce((s, [, w]) => s + w, 0));
  let q = 0;
  for (const i of nodeIds) {
    for (const [j, w] of adj.get(i) ?? []) {
      if (community.get(i) === community.get(j)) {
        q += w - (resolution * deg.get(i)! * deg.get(j)!) / m2;
      }
    }
  }
  return q / m2;
}
