import { NextRequest, NextResponse } from "next/server";
import { fetchMentions } from "@/lib/brandwatch/client";
import { buildNetwork } from "@/lib/network/cooccurrence";
import type { NetworkQuery, Platform } from "@/lib/brandwatch/types";

export const dynamic = "force-dynamic";

function num(v: string | null): number | undefined {
  if (v == null || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;

  const query: NetworkQuery = {
    search: sp.get("search") ?? undefined,
    minStrength: num(sp.get("minStrength")),
    minCooccurrences: num(sp.get("minCooccurrences")),
    minMentions: num(sp.get("minMentions")),
    minLLR: num(sp.get("minLLR")),
    maxNodes: num(sp.get("maxNodes")),
    platforms: (sp.get("platforms")?.split(",").filter(Boolean) as Platform[]) || undefined,
  };

  try {
    const { mentions, source } = await fetchMentions(query);
    const network = buildNetwork(mentions, query);
    return NextResponse.json({ ...network, source });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Failed to build network" },
      { status: 500 },
    );
  }
}
