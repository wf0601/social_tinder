"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { KeywordEdge, KeywordNetwork, KeywordNode } from "@/lib/brandwatch/types";

// ForceGraph2D touches `window`, so it must be client-only. next/dynamic drops
// the library's generics, so we type it loosely and keep our own typed
// accessor callbacks below.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
}) as unknown as React.ComponentType<Record<string, unknown>>;

// Distinct, readable cluster palette.
const CLUSTER_COLORS = [
  "#ff5a7e", "#4cc9f0", "#ffd166", "#06d6a0", "#b388ff",
  "#f78c6b", "#83e377", "#ff9ff3", "#54a0ff", "#feca57",
];

export function clusterColor(cluster: number): string {
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

type GraphNode = KeywordNode & { x?: number; y?: number };
type SizeBy = "mentions" | "reach";

interface Props {
  data: KeywordNetwork;
  sizeBy: SizeBy;
  onSelect: (node: KeywordNode | null) => void;
  selectedId?: string | null;
}

function useContainerSize() {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setSize({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);
    setSize({ width: el.clientWidth, height: el.clientHeight });
    return () => ro.disconnect();
  }, []);
  return { ref, size };
}

export default function NetworkGraph({ data, sizeBy, onSelect, selectedId }: Props) {
  const { ref, size } = useContainerSize();
  const [hoverId, setHoverId] = useState<string | null>(null);

  // Clone so the force sim can mutate (source/target -> node refs) without
  // touching the props object. Recompute only when the underlying data changes.
  const graphData = useMemo(() => {
    const maxMentions = Math.max(1, ...data.nodes.map((n) => n.mentions));
    const maxReach = Math.max(1, ...data.nodes.map((n) => n.reach));
    return {
      nodes: data.nodes.map((n) => ({ ...n, _maxMentions: maxMentions, _maxReach: maxReach })),
      links: data.edges.map((e) => ({ ...e })),
    };
  }, [data]);

  // Adjacency for hover/selection highlighting.
  const adjacency = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of data.edges) {
      if (!m.has(e.source)) m.set(e.source, new Set());
      if (!m.has(e.target)) m.set(e.target, new Set());
      m.get(e.source)!.add(e.target);
      m.get(e.target)!.add(e.source);
    }
    return m;
  }, [data]);

  const focusId = hoverId ?? selectedId ?? null;
  const focusSet = useMemo(() => {
    if (!focusId) return null;
    const s = new Set<string>([focusId]);
    adjacency.get(focusId)?.forEach((id) => s.add(id));
    return s;
  }, [focusId, adjacency]);

  function nodeSize(n: GraphNode & { _maxMentions: number; _maxReach: number }) {
    const v = sizeBy === "reach" ? n.reach / n._maxReach : n.mentions / n._maxMentions;
    return 2 + Math.sqrt(v) * 14;
  }

  return (
    <div ref={ref} className="h-full w-full">
      {size.width > 0 && (
        <ForceGraph2D
          width={size.width}
          height={size.height}
          graphData={graphData}
          backgroundColor="#0b0d12"
          nodeId="id"
          nodeRelSize={1}
          cooldownTicks={120}
          d3VelocityDecay={0.3}
          linkColor={(l: KeywordEdge) => {
            if (!focusSet) return "rgba(255,255,255,0.12)";
            const lit = focusSet.has(l.source as string) && focusSet.has(l.target as string) &&
              (l.source === focusId || l.target === focusId);
            return lit ? "rgba(255,255,255,0.55)" : "rgba(255,255,255,0.04)";
          }}
          linkWidth={(l: KeywordEdge) => 0.5 + l.strength * 6}
          onNodeHover={(n: GraphNode | null) => setHoverId(n?.id ?? null)}
          onNodeClick={(n: GraphNode) => onSelect(n)}
          onBackgroundClick={() => onSelect(null)}
          nodeCanvasObject={(
            node: GraphNode & { _maxMentions: number; _maxReach: number },
            ctx: CanvasRenderingContext2D,
            scale: number,
          ) => {
            const r = nodeSize(node);
            const dimmed = focusSet ? !focusSet.has(node.id) : false;
            const color = clusterColor(node.cluster);
            ctx.globalAlpha = dimmed ? 0.18 : 1;

            ctx.beginPath();
            ctx.arc(node.x!, node.y!, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
            if (node.id === selectedId) {
              ctx.lineWidth = 2 / scale;
              ctx.strokeStyle = "#ffffff";
              ctx.stroke();
            }

            // Label larger/important nodes, or whatever is in focus.
            const showLabel = !dimmed && (r > 6 || node.id === focusId || scale > 2.2);
            if (showLabel) {
              const fontSize = Math.max(3, 11 / scale);
              ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
              ctx.fillStyle = "rgba(255,255,255,0.92)";
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillText(node.id, node.x!, node.y! + r + 1);
            }
            ctx.globalAlpha = 1;
          }}
          nodePointerAreaPaint={(
            node: GraphNode & { _maxMentions: number; _maxReach: number },
            color: string,
            ctx: CanvasRenderingContext2D,
          ) => {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x!, node.y!, nodeSize(node) + 2, 0, 2 * Math.PI);
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
