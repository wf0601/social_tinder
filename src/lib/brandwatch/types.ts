// Core data model for Social Tinder.
//
// A `Mention` is one social-media post as returned by Brandwatch Consumer
// Research. We keep only the fields the network engine needs, plus a few
// useful for display/sizing. `keywords` is the set of normalized terms the
// post matched — this is what we build the keyword network from.

export type Platform =
  | "twitter"
  | "reddit"
  | "instagram"
  | "tiktok"
  | "youtube"
  | "news"
  | "forum"
  | "blog";

export type Sentiment = "positive" | "neutral" | "negative";

export interface Mention {
  id: string;
  date: string; // ISO timestamp
  platform: Platform;
  author: string;
  text: string;
  sentiment: Sentiment;
  reach: number; // estimated impressions / audience size
  /**
   * Normalized keywords/topics this mention contains. In Brandwatch terms
   * these map to matched query terms, hashtags, or entity tags.
   */
  keywords: string[];
}

/** A keyword node in the network. */
export interface KeywordNode {
  id: string;
  /** Number of mentions containing this keyword. */
  mentions: number;
  /** Summed reach across mentions containing this keyword. */
  reach: number;
  /** Net sentiment in [-1, 1]: (positive - negative) / total. */
  sentiment: number;
  /** Community id, assigned by Louvain modularity clustering. */
  cluster: number;
  /** Weighted PageRank — how central/influential the keyword is (sums to ~1). */
  influence: number;
  /** Normalized betweenness in [0, 1] — "bridge" keywords connecting clusters. */
  bridge: number;
}

/** A weighted edge between two co-occurring keywords. */
export interface KeywordEdge {
  source: string;
  target: string;
  /** Raw count of mentions containing BOTH keywords. */
  cooccurrences: number;
  /**
   * Connection strength in [0, 1]. Jaccard index:
   * co(A,B) / (count(A) + count(B) - co(A,B)).
   * "How often these two show up together vs. apart."
   */
  strength: number;
  /**
   * Pointwise mutual information. Positive => the pair appears together
   * more than chance; useful for surfacing surprising associations.
   */
  pmi: number;
  /**
   * Dunning log-likelihood ratio (G²) — statistical significance of the
   * association. Robust to rare terms; used to prune coincidental edges.
   */
  llr: number;
}

export interface KeywordNetwork {
  nodes: KeywordNode[];
  edges: KeywordEdge[];
  meta: {
    totalMentions: number;
    generatedAt: string;
    /** Echo of the filters used to build this network. */
    query?: NetworkQuery;
  };
}

/** Filters for building / fetching a network. */
export interface NetworkQuery {
  /** Free-text search term to fetch mentions for (real Brandwatch). */
  search?: string;
  /** Only include edges at/above this strength (Jaccard, 0..1). */
  minStrength?: number;
  /** Only include edges with at least this many co-occurrences. */
  minCooccurrences?: number;
  /** Drop keywords appearing in fewer than this many mentions. */
  minMentions?: number;
  /** Drop edges below this log-likelihood ratio (significance, G²). */
  minLLR?: number;
  /** Restrict to these platforms. */
  platforms?: Platform[];
  /** Cap the number of nodes (keeps the top-N by mentions). */
  maxNodes?: number;
}
