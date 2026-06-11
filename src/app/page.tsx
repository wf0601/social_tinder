"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import NetworkGraph, { clusterColor } from "@/components/NetworkGraph";
import type { KeywordNetwork, KeywordNode, Platform } from "@/lib/brandwatch/types";

type SizeBy = "mentions" | "reach" | "influence" | "bridge";

interface Filters {
  search: string;
  minStrength: number;
  minCooccurrences: number;
  minMentions: number;
  minLLR: number;
  maxNodes: number;
  platforms: Platform[];
}

const DEFAULTS: Filters = {
  search: "",
  minStrength: 0.04,
  minCooccurrences: 3,
  minMentions: 5,
  minLLR: 0,
  maxNodes: 80,
  platforms: [],
};

const ALL_PLATFORMS: Platform[] = [
  "twitter", "reddit", "instagram", "tiktok", "youtube", "news", "forum", "blog",
];

const SIZE_BY_HELP: Record<SizeBy, string> = {
  mentions: "Number of posts containing the keyword",
  reach: "Total audience reached",
  influence: "Weighted PageRank — how central the keyword is",
  bridge: "Betweenness — keywords that connect communities",
};

type NetworkResponse = KeywordNetwork & { source: "sample" | "brandwatch" };

export default function Home() {
  const [filters, setFilters] = useState<Filters>(DEFAULTS);
  const [sizeBy, setSizeBy] = useState<SizeBy>("mentions");
  const [data, setData] = useState<NetworkResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<KeywordNode | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (f: Filters) => {
    setLoading(true);
    setError(null);
    const p = new URLSearchParams({
      minStrength: String(f.minStrength),
      minCooccurrences: String(f.minCooccurrences),
      minMentions: String(f.minMentions),
      minLLR: String(f.minLLR),
      maxNodes: String(f.maxNodes),
    });
    if (f.search) p.set("search", f.search);
    if (f.platforms.length) p.set("platforms", f.platforms.join(","));
    try {
      const res = await fetch(`/api/network?${p.toString()}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Request failed");
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load network");
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced reload whenever filters change.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => load(filters), 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [filters, load]);

  const set = <K extends keyof Filters>(key: K, value: Filters[K]) =>
    setFilters((f) => ({ ...f, [key]: value }));

  const togglePlatform = (p: Platform) =>
    setFilters((f) => ({
      ...f,
      platforms: f.platforms.includes(p)
        ? f.platforms.filter((x) => x !== p)
        : [...f.platforms, p],
    }));

  // Top connections for the selected keyword.
  const connections = useMemo(() => {
    if (!data || !selected) return [];
    return data.edges
      .filter((e) => e.source === selected.id || e.target === selected.id)
      .map((e) => ({
        other: e.source === selected.id ? e.target : e.source,
        strength: e.strength,
        cooccurrences: e.cooccurrences,
        pmi: e.pmi,
        llr: e.llr,
      }))
      .sort((a, b) => b.strength - a.strength)
      .slice(0, 12);
  }, [data, selected]);

  // Max influence/bridge so the details panel can show 0–100 relative scores.
  const ranks = useMemo(() => {
    if (!data || data.nodes.length === 0) return { maxInfluence: 1, maxBridge: 1 };
    return {
      maxInfluence: Math.max(1e-9, ...data.nodes.map((n) => n.influence)),
      maxBridge: Math.max(1e-9, ...data.nodes.map((n) => n.bridge)),
    };
  }, [data]);

  const clusters = useMemo(() => {
    if (!data) return [];
    const byCluster = new Map<number, { count: number; top: string }>();
    for (const n of [...data.nodes].sort((a, b) => b.mentions - a.mentions)) {
      const c = byCluster.get(n.cluster);
      if (!c) byCluster.set(n.cluster, { count: 1, top: n.id });
      else c.count++;
    }
    return [...byCluster.entries()].sort((a, b) => b[1].count - a[1].count);
  }, [data]);

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <Header source={data?.source} loading={loading} />

      <div className="flex min-h-0 flex-1">
        {/* Controls */}
        <aside className="w-72 shrink-0 overflow-y-auto border-r border-panel-border bg-panel p-4">
          <Field label="Search topic">
            <input
              value={filters.search}
              onChange={(e) => set("search", e.target.value)}
              placeholder="e.g. electric vehicles"
              className="w-full rounded-md border border-panel-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <p className="mt-1 text-[11px] text-white/40">
              Used by the live Brandwatch client. Ignored for sample data.
            </p>
          </Field>

          <Slider
            label="Min. connection strength"
            value={filters.minStrength}
            min={0}
            max={0.4}
            step={0.01}
            display={filters.minStrength.toFixed(2)}
            onChange={(v) => set("minStrength", v)}
          />
          <Slider
            label="Min. co-occurrences"
            value={filters.minCooccurrences}
            min={1}
            max={30}
            step={1}
            display={String(filters.minCooccurrences)}
            onChange={(v) => set("minCooccurrences", v)}
          />
          <Slider
            label="Min. keyword mentions"
            value={filters.minMentions}
            min={1}
            max={50}
            step={1}
            display={String(filters.minMentions)}
            onChange={(v) => set("minMentions", v)}
          />
          <Slider
            label="Min. significance (G²)"
            value={filters.minLLR}
            min={0}
            max={50}
            step={1}
            display={filters.minLLR === 0 ? "off" : String(filters.minLLR)}
            onChange={(v) => set("minLLR", v)}
          />
          <Slider
            label="Max. keywords shown"
            value={filters.maxNodes}
            min={10}
            max={150}
            step={5}
            display={String(filters.maxNodes)}
            onChange={(v) => set("maxNodes", v)}
          />

          <Field label="Size nodes by">
            <div className="grid grid-cols-2 gap-2">
              {(["mentions", "reach", "influence", "bridge"] as SizeBy[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setSizeBy(s)}
                  title={SIZE_BY_HELP[s]}
                  className={`rounded-md border px-2 py-1.5 text-xs capitalize transition ${
                    sizeBy === s
                      ? "border-accent bg-accent/15 text-white"
                      : "border-panel-border text-white/60 hover:text-white"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Platforms">
            <div className="flex flex-wrap gap-1.5">
              {ALL_PLATFORMS.map((p) => {
                const on = filters.platforms.includes(p);
                return (
                  <button
                    key={p}
                    onClick={() => togglePlatform(p)}
                    className={`rounded-full border px-2.5 py-1 text-[11px] capitalize transition ${
                      on
                        ? "border-accent bg-accent/15 text-white"
                        : "border-panel-border text-white/55 hover:text-white"
                    }`}
                  >
                    {p}
                  </button>
                );
              })}
            </div>
          </Field>

          <button
            onClick={() => setFilters(DEFAULTS)}
            className="mt-2 w-full rounded-md border border-panel-border py-1.5 text-xs text-white/60 hover:text-white"
          >
            Reset filters
          </button>

          {clusters.length > 0 && (
            <div className="mt-6">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-white/40">
                Communities
              </p>
              <ul className="space-y-1.5">
                {clusters.map(([id, info]) => (
                  <li key={id} className="flex items-center gap-2 text-xs text-white/70">
                    <span
                      className="inline-block h-3 w-3 rounded-full"
                      style={{ background: clusterColor(id) }}
                    />
                    <span className="font-medium text-white/90">{info.top}</span>
                    <span className="text-white/40">+{info.count - 1} more</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>

        {/* Graph */}
        <main className="relative min-w-0 flex-1">
          {error ? (
            <div className="flex h-full items-center justify-center p-8 text-center text-sm text-red-300">
              {error}
            </div>
          ) : data && data.nodes.length === 0 ? (
            <div className="flex h-full items-center justify-center p-8 text-center text-sm text-white/50">
              No keyword network at these thresholds. Try lowering the minimums.
            </div>
          ) : data ? (
            <NetworkGraph
              data={data}
              sizeBy={sizeBy}
              onSelect={setSelected}
              selectedId={selected?.id}
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-white/40">
              Building network…
            </div>
          )}

          {data && (
            <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-black/40 px-3 py-1.5 text-[11px] text-white/60 backdrop-blur">
              {data.nodes.length} keywords · {data.edges.length} connections ·{" "}
              {data.meta.totalMentions.toLocaleString()} mentions
            </div>
          )}
        </main>

        {/* Details */}
        {selected && (
          <aside className="w-80 shrink-0 overflow-y-auto border-l border-panel-border bg-panel p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className="inline-block h-3 w-3 rounded-full"
                    style={{ background: clusterColor(selected.cluster) }}
                  />
                  <h2 className="text-lg font-semibold">{selected.id}</h2>
                </div>
                <p className="mt-0.5 text-xs text-white/45">Community #{selected.cluster}</p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="text-white/40 hover:text-white"
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <Stat label="Mentions" value={selected.mentions.toLocaleString()} />
              <Stat label="Reach" value={compact(selected.reach)} />
              <Stat
                label="Sentiment"
                value={selected.sentiment >= 0 ? `+${selected.sentiment.toFixed(2)}` : selected.sentiment.toFixed(2)}
                color={selected.sentiment > 0.1 ? "#06d6a0" : selected.sentiment < -0.1 ? "#ff5a7e" : undefined}
              />
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-center">
              <Stat
                label="Influence"
                value={`${Math.round((selected.influence / ranks.maxInfluence) * 100)}`}
              />
              <Stat
                label="Bridge"
                value={`${Math.round((selected.bridge / ranks.maxBridge) * 100)}`}
              />
            </div>

            <p className="mt-5 mb-2 text-xs font-semibold uppercase tracking-wide text-white/40">
              Strongest connections
            </p>
            <ul className="space-y-2">
              {connections.map((c) => (
                <li key={c.other}>
                  <button
                    onClick={() => {
                      const node = data?.nodes.find((n) => n.id === c.other);
                      if (node) setSelected(node);
                    }}
                    title={`significance G²=${c.llr.toFixed(0)} · PMI=${c.pmi.toFixed(2)}`}
                    className="w-full text-left"
                  >
                    <div className="flex items-baseline justify-between text-sm">
                      <span className="font-medium text-white/90 hover:text-accent">{c.other}</span>
                      <span className="text-xs text-white/50">{c.cooccurrences}× together</span>
                    </div>
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-accent"
                        style={{ width: `${Math.min(100, c.strength * 100)}%` }}
                      />
                    </div>
                  </button>
                </li>
              ))}
              {connections.length === 0 && (
                <li className="text-xs text-white/40">No connections at current thresholds.</li>
              )}
            </ul>
          </aside>
        )}
      </div>
    </div>
  );
}

function Header({ source, loading }: { source?: string; loading: boolean }) {
  return (
    <header className="flex items-center justify-between border-b border-panel-border bg-panel px-5 py-3">
      <div className="flex items-baseline gap-3">
        <h1 className="text-lg font-bold tracking-tight">
          <span className="text-accent">🔥 Social</span> Tinder
        </h1>
        <span className="text-xs text-white/40">keyword chemistry from social listening</span>
      </div>
      <div className="flex items-center gap-3 text-xs">
        {loading && <span className="text-white/40">updating…</span>}
        <span
          className={`rounded-full px-2.5 py-1 font-medium ${
            source === "brandwatch"
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-amber-500/15 text-amber-300"
          }`}
        >
          {source === "brandwatch" ? "Live Brandwatch" : "Sample data"}
        </span>
      </div>
    </header>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-white/40">
        {label}
      </label>
      {children}
    </div>
  );
}

function Slider({
  label, value, min, max, step, display, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number;
  display: string; onChange: (v: number) => void;
}) {
  return (
    <div className="mb-4">
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wide text-white/40">{label}</label>
        <span className="text-xs font-mono text-white/70">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-md border border-panel-border bg-background py-2">
      <div className="text-sm font-semibold" style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-white/40">{label}</div>
    </div>
  );
}

function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
