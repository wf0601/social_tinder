"""Social Tinder — keyword chemistry from social listening (Python edition).

Mirrors the TypeScript app: synthetic Brandwatch mentions -> weighted keyword
co-occurrence network (Jaccard strength + PMI) -> community detection.
"""

from .types import KeywordEdge, KeywordNetwork, KeywordNode, Mention, NetworkQuery
from .network import build_network
from .client import fetch_mentions, is_real_client_configured
from .sample import generate_sample_mentions

__all__ = [
    "KeywordEdge",
    "KeywordNetwork",
    "KeywordNode",
    "Mention",
    "NetworkQuery",
    "build_network",
    "fetch_mentions",
    "is_real_client_configured",
    "generate_sample_mentions",
]

__version__ = "0.1.0"
