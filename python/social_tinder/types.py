"""Core data model. Mirrors src/lib/brandwatch/types.ts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Platform = Literal[
    "twitter", "reddit", "instagram", "tiktok", "youtube", "news", "forum", "blog"
]
Sentiment = Literal["positive", "neutral", "negative"]


@dataclass
class Mention:
    """One social-media post, as returned by Brandwatch Consumer Research."""

    id: str
    date: str  # ISO timestamp
    platform: Platform
    author: str
    text: str
    sentiment: Sentiment
    reach: int  # estimated impressions / audience size
    keywords: list[str]  # normalized terms this mention matched


@dataclass
class KeywordNode:
    id: str
    mentions: int  # number of mentions containing this keyword
    reach: int  # summed reach across those mentions
    sentiment: float  # net sentiment in [-1, 1]
    cluster: int  # community id from label propagation

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mentions": self.mentions,
            "reach": self.reach,
            "sentiment": self.sentiment,
            "cluster": self.cluster,
        }


@dataclass
class KeywordEdge:
    source: str
    target: str
    cooccurrences: int  # mentions containing BOTH keywords
    strength: float  # Jaccard index in [0, 1]
    pmi: float  # pointwise mutual information

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "cooccurrences": self.cooccurrences,
            "strength": self.strength,
            "pmi": self.pmi,
        }


@dataclass
class NetworkQuery:
    """Filters for building / fetching a network."""

    search: Optional[str] = None
    min_strength: float = 0.0
    min_cooccurrences: int = 1
    min_mentions: int = 1
    platforms: Optional[list[Platform]] = None
    max_nodes: int = 120

    def to_dict(self) -> dict:
        return {
            "search": self.search,
            "minStrength": self.min_strength,
            "minCooccurrences": self.min_cooccurrences,
            "minMentions": self.min_mentions,
            "platforms": self.platforms,
            "maxNodes": self.max_nodes,
        }


@dataclass
class KeywordNetwork:
    nodes: list[KeywordNode]
    edges: list[KeywordEdge]
    total_mentions: int
    generated_at: str
    query: Optional[NetworkQuery] = None
    source: str = "sample"

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "meta": {
                "totalMentions": self.total_mentions,
                "generatedAt": self.generated_at,
                "query": self.query.to_dict() if self.query else None,
            },
            "source": self.source,
        }
