"""Pluggable data source. Mirrors src/lib/brandwatch/client.ts.

By default serves the synthetic dataset (zero setup). Set Brandwatch env vars
to pull real Consumer Research mentions instead:

    BRANDWATCH_API_TOKEN   - OAuth2 bearer token
    BRANDWATCH_PROJECT_ID  - Consumer Research project id
    BRANDWATCH_QUERY_ID    - optional saved query/search id
    BRANDWATCH_API_BASE    - optional base URL override

Uses only the stdlib (urllib) so the package has no hard HTTP dependency.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import uuid

from .sample import generate_sample_mentions
from .types import Mention, NetworkQuery, Platform, Sentiment


def is_real_client_configured() -> bool:
    return bool(os.environ.get("BRANDWATCH_API_TOKEN") and os.environ.get("BRANDWATCH_PROJECT_ID"))


def fetch_mentions(query: NetworkQuery | None = None) -> tuple[list[Mention], str]:
    """Return (mentions, source) where source is 'sample' or 'brandwatch'."""
    q = query or NetworkQuery()
    if not is_real_client_configured():
        return generate_sample_mentions(), "sample"
    return _fetch_brandwatch_mentions(q), "brandwatch"


def _fetch_brandwatch_mentions(query: NetworkQuery) -> list[Mention]:
    token = os.environ["BRANDWATCH_API_TOKEN"]
    project_id = os.environ["BRANDWATCH_PROJECT_ID"]
    base = os.environ.get("BRANDWATCH_API_BASE", "https://api.brandwatch.com")

    params = {"pageSize": "5000", "orderBy": "date", "orderDirection": "desc"}
    if query.search:
        params["search"] = query.search
    if os.environ.get("BRANDWATCH_QUERY_ID"):
        params["queryId"] = os.environ["BRANDWATCH_QUERY_ID"]

    url = f"{base}/projects/{project_id}/data/mentions?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        payload = json.loads(resp.read().decode())

    return [_normalize(m) for m in payload.get("results", [])]


# --- Brandwatch -> Mention normalization -----------------------------------

_STOPWORDS = set(
    "the a an and or but of to in on for with at by from is are was were be been it "
    "this that these those i you he she we they my your our as so if not no yes do "
    "does did has have had will would can could just about into over under more most "
    "very dont im its https http www com rt amp".split()
)


def _normalize(m: dict) -> Mention:
    return Mention(
        id=m.get("resourceId") or m.get("guid") or str(uuid.uuid4()),
        date=m.get("date") or "",
        platform=_map_platform(m.get("pageType")),
        author=m.get("author") or "unknown",
        text=m.get("fullText") or m.get("snippet") or "",
        sentiment=_map_sentiment(m.get("sentiment")),
        reach=int(m.get("reachEstimate") or m.get("impressions") or 0),
        keywords=_extract_keywords(m),
    )


def _extract_keywords(m: dict) -> list[str]:
    merged: list[str] = []
    for mp in m.get("matchPositions") or []:
        if mp.get("text"):
            merged.append(mp["text"])
    merged += m.get("categories") or []
    merged += m.get("tags") or []
    merged += m.get("hashtags") or []
    if not merged and m.get("fullText"):
        return _tokenize(m["fullText"])
    # dedupe, normalize, preserve order
    seen: dict[str, None] = {}
    for k in merged:
        kk = k.lower().strip()
        if kk:
            seen[kk] = None
    return list(seen.keys())


def _tokenize(text: str) -> list[str]:
    text = re.sub(r"https?://\S+", " ", text.lower())
    text = re.sub(r"[^a-z0-9#\s]", " ", text)
    out: dict[str, None] = {}
    for w in text.split():
        w = w.lstrip("#")
        if len(w) > 2 and w not in _STOPWORDS:
            out[w] = None
    return list(out.keys())[:8]


def _map_platform(page_type: str | None) -> Platform:
    pt = (page_type or "").lower()
    if pt in ("twitter", "x"):
        return "twitter"
    if pt in ("reddit", "instagram", "tiktok", "youtube", "news", "forum"):
        return pt  # type: ignore[return-value]
    return "blog"


def _map_sentiment(s: str | None) -> Sentiment:
    v = (s or "").lower()
    return v if v in ("positive", "negative") else "neutral"  # type: ignore[return-value]
