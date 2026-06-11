// Deterministic synthetic Brandwatch dataset, used as the default data source
// so the app runs with zero credentials. Mentions are generated from themes
// with overlapping keywords and a few cross-theme "bridge" terms, so the
// resulting network has real clusters that connect — which is the whole point.

import type { Mention, Platform, Sentiment } from "./types";

// Seeded PRNG (mulberry32) so the dataset is stable across runs/builds.
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

interface Theme {
  core: string[];
  /** keywords that bridge into other themes (used less often) */
  bridges: string[];
  platformBias: Platform[];
  sentimentBias: Sentiment; // dominant mood
}

const THEMES: Record<string, Theme> = {
  ai: {
    core: ["ai", "chatgpt", "openai", "machine learning", "automation", "llm", "prompt"],
    bridges: ["jobs", "ethics", "tesla"],
    platformBias: ["twitter", "reddit", "news"],
    sentimentBias: "neutral",
  },
  crypto: {
    core: ["bitcoin", "ethereum", "crypto", "blockchain", "nft", "web3", "defi"],
    bridges: ["tesla", "regulation", "ai"],
    platformBias: ["twitter", "reddit"],
    sentimentBias: "negative",
  },
  climate: {
    core: ["climate", "sustainability", "renewable", "solar", "ev", "carbon"],
    bridges: ["tesla", "regulation", "fashion"],
    platformBias: ["news", "twitter", "blog"],
    sentimentBias: "neutral",
  },
  gaming: {
    core: ["gaming", "esports", "twitch", "playstation", "nintendo", "steam"],
    bridges: ["nft", "ai", "streetwear"],
    platformBias: ["youtube", "tiktok", "reddit"],
    sentimentBias: "positive",
  },
  fashion: {
    core: ["fashion", "streetwear", "sneakers", "nike", "thrift", "runway"],
    bridges: ["sustainability", "nft", "ai"],
    platformBias: ["instagram", "tiktok"],
    sentimentBias: "positive",
  },
  wellness: {
    core: ["wellness", "fitness", "mindfulness", "nutrition", "running", "sleep"],
    bridges: ["ai", "sustainability", "fashion"],
    platformBias: ["instagram", "tiktok", "youtube"],
    sentimentBias: "positive",
  },
};

const AUTHORS = [
  "@maya_t", "@devon", "@nori", "@kp_writes", "@late_night_dev", "@sora",
  "@green_juno", "@bitflux", "@runwaykid", "@coachZ", "@pixelpede", "@anon",
];

function pick<T>(rng: () => number, arr: T[]): T {
  return arr[Math.floor(rng() * arr.length)];
}

function sampleSentiment(rng: () => number, bias: Sentiment): Sentiment {
  const r = rng();
  // 55% chance of the theme's dominant mood, rest spread across the others.
  if (r < 0.55) return bias;
  const others: Sentiment[] = (["positive", "neutral", "negative"] as Sentiment[]).filter(
    (s) => s !== bias,
  );
  return r < 0.8 ? others[0] : others[1];
}

/**
 * Generate `n` synthetic mentions across all themes.
 */
export function generateSampleMentions(n = 1500, seed = 42): Mention[] {
  const rng = mulberry32(seed);
  const themeNames = Object.keys(THEMES);
  const mentions: Mention[] = [];
  const now = Date.now();

  for (let i = 0; i < n; i++) {
    const themeName = pick(rng, themeNames);
    const theme = THEMES[themeName];

    // Choose 2–4 core keywords for this post.
    const k = 2 + Math.floor(rng() * 3);
    const shuffled = [...theme.core].sort(() => rng() - 0.5);
    const keywords = new Set(shuffled.slice(0, k));

    // ~30% of posts carry a bridge keyword, creating inter-cluster edges.
    if (rng() < 0.3 && theme.bridges.length) {
      keywords.add(pick(rng, theme.bridges));
    }

    const sentiment = sampleSentiment(rng, theme.sentimentBias);
    const platform =
      rng() < 0.75 ? pick(rng, theme.platformBias) : (pick(rng, ALL_PLATFORMS) as Platform);

    // Reach is heavy-tailed: most posts small, a few viral.
    const reach = Math.round(50 + Math.pow(rng(), 4) * 500_000);

    const daysAgo = Math.floor(rng() * 30);
    const date = new Date(now - daysAgo * 86_400_000 - Math.floor(rng() * 86_400_000));

    mentions.push({
      id: `m_${i.toString(36)}`,
      date: date.toISOString(),
      platform,
      author: pick(rng, AUTHORS),
      text: `${[...keywords].join(" + ")} — ${themeName} chatter`,
      sentiment,
      reach,
      keywords: [...keywords],
    });
  }

  return mentions;
}

const ALL_PLATFORMS: Platform[] = [
  "twitter", "reddit", "instagram", "tiktok", "youtube", "news", "forum", "blog",
];
