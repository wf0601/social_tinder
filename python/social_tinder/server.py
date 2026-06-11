"""FastAPI server. Mirrors the Next.js /api/network route + serves the UI."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .client import fetch_mentions
from .network import build_network
from .types import NetworkQuery
from .viz import interactive_page

app = FastAPI(title="Social Tinder", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return interactive_page()


@app.get("/api/network")
def network(
    search: str | None = None,
    minStrength: float = 0.0,
    minCooccurrences: int = 1,
    minMentions: int = 1,
    maxNodes: int = 120,
    platforms: str | None = None,
) -> JSONResponse:
    query = NetworkQuery(
        search=search,
        min_strength=minStrength,
        min_cooccurrences=minCooccurrences,
        min_mentions=minMentions,
        max_nodes=maxNodes,
        platforms=[p for p in platforms.split(",") if p] if platforms else None,
    )
    try:
        mentions, source = fetch_mentions(query)
        net = build_network(mentions, query)
        net.source = source
        return JSONResponse(net.to_dict())
    except Exception as err:  # noqa: BLE001 — surface as a clean 500
        return JSONResponse({"error": str(err)}, status_code=500)
