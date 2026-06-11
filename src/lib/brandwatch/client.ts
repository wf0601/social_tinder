// Pluggable data source. By default Social Tinder serves a synthetic dataset
// so it runs with zero setup. Provide Brandwatch credentials via env vars to
// pull real Consumer Research mentions instead.
//
// Required env to enable the real client:
//   BRANDWATCH_API_TOKEN   - OAuth2 bearer token
//   BRANDWATCH_PROJECT_ID  - Consumer Research project id
// Optional:
//   BRANDWATCH_QUERY_ID    - default saved query/search id to pull from
//
// The Brandwatch Consumer Research API is documented at
// https://developers.brandwatch.com/ — the mapping below targets the
// /projects/{projectId}/data/mentions endpoint. Adjust field paths to match
// your account's response shape.

import type { Mention, NetworkQuery, Platform, Sentiment } from "./types";
import { generateSampleMentions } from "./sample";

export function isRealClientConfigured(): boolean {
  return Boolean(process.env.BRANDWATCH_API_TOKEN && process.env.BRANDWATCH_PROJECT_ID);
}

export interface FetchResult {
  mentions: Mention[];
  source: "sample" | "brandwatch";
}

/**
 * Fetch mentions for a query. Falls back to the sample dataset whenever the
 * real client isn't configured, so callers never have to branch.
 */
export async function fetchMentions(query: NetworkQuery = {}): Promise<FetchResult> {
  if (!isRealClientConfigured()) {
    return { mentions: generateSampleMentions(), source: "sample" };
  }
  const mentions = await fetchBrandwatchMentions(query);
  return { mentions, source: "brandwatch" };
}

async function fetchBrandwatchMentions(query: NetworkQuery): Promise<Mention[]> {
  const token = process.env.BRANDWATCH_API_TOKEN!;
  const projectId = process.env.BRANDWATCH_PROJECT_ID!;
  const base = process.env.BRANDWATCH_API_BASE ?? "https://api.brandwatch.com";

  const params = new URLSearchParams({
    pageSize: "5000",
    orderBy: "date",
    orderDirection: "desc",
  });
  if (query.search) params.set("search", query.search);
  if (process.env.BRANDWATCH_QUERY_ID) params.set("queryId", process.env.BRANDWATCH_QUERY_ID);

  const res = await fetch(
    `${base}/projects/${projectId}/data/mentions?${params.toString()}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error(`Brandwatch API ${res.status}: ${await res.text().catch(() => "")}`);
  }

  const json = (await res.json()) as { results?: BrandwatchMention[] };
  return (json.results ?? []).map(normalizeBrandwatchMention);
}

// --- Brandwatch -> Mention normalization -----------------------------------

interface BrandwatchMention {
  resourceId?: string;
  guid?: string;
  date?: string;
  pageType?: string;
  author?: string;
  fullText?: string;
  snippet?: string;
  sentiment?: string; // "positive" | "neutral" | "negative"
  reachEstimate?: number;
  impressions?: number;
  // Brandwatch returns matched terms / categories / tags in several places;
  // we merge whatever is present.
  matchPositions?: { text?: string }[];
  categories?: string[];
  tags?: string[];
  hashtags?: string[];
}

function normalizeBrandwatchMention(m: BrandwatchMention): Mention {
  const keywords = extractKeywords(m);
  return {
    id: m.resourceId ?? m.guid ?? crypto.randomUUID(),
    date: m.date ?? new Date().toISOString(),
    platform: mapPlatform(m.pageType),
    author: m.author ?? "unknown",
    text: m.fullText ?? m.snippet ?? "",
    sentiment: mapSentiment(m.sentiment),
    reach: m.reachEstimate ?? m.impressions ?? 0,
    keywords,
  };
}

function extractKeywords(m: BrandwatchMention): string[] {
  const fromMatches = (m.matchPositions ?? [])
    .map((p) => p.text)
    .filter((t): t is string => Boolean(t));
  const merged = [
    ...fromMatches,
    ...(m.categories ?? []),
    ...(m.tags ?? []),
    ...(m.hashtags ?? []),
  ];
  // Fall back to a simple text tokenization when no structured terms exist.
  if (merged.length === 0 && m.fullText) return tokenize(m.fullText);
  return Array.from(new Set(merged.map((k) => k.toLowerCase().trim()))).filter(Boolean);
}

const STOPWORDS = new Set(
  "the a an and or but of to in on for with at by from is are was were be been it this that these those i you he she we they my your our as so if not no yes do does did has have had will would can could just about into over under more most very can't dont don't im it's https http www com rt amp".split(
    " ",
  ),
);

function tokenize(text: string): string[] {
  const words = text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[^a-z0-9#\s]/g, " ")
    .split(/\s+/)
    .map((w) => w.replace(/^#/, ""))
    .filter((w) => w.length > 2 && !STOPWORDS.has(w));
  return Array.from(new Set(words)).slice(0, 8);
}

function mapPlatform(pageType?: string): Platform {
  switch ((pageType ?? "").toLowerCase()) {
    case "twitter":
    case "x":
      return "twitter";
    case "reddit":
      return "reddit";
    case "instagram":
      return "instagram";
    case "tiktok":
      return "tiktok";
    case "youtube":
      return "youtube";
    case "news":
      return "news";
    case "forum":
      return "forum";
    default:
      return "blog";
  }
}

function mapSentiment(s?: string): Sentiment {
  const v = (s ?? "").toLowerCase();
  if (v === "positive" || v === "negative") return v;
  return "neutral";
}
