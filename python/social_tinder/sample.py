"""Deterministic synthetic Brandwatch dataset. Mirrors sample.ts.

We port the same mulberry32 PRNG (32-bit ops), so this generator is itself
fully deterministic for a given seed. Note it does NOT reproduce the TS app's
dataset exactly: JS's ``array.sort(() => rng()-0.5)`` consumes a
variable, engine-dependent number of random draws per shuffle, whereas Python's
``sorted(key=...)`` draws exactly once per element. The two streams therefore
diverge after the first shuffle. The datasets are statistically equivalent
(same themes, same structure), not byte-for-byte identical.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .types import Mention, Platform, Sentiment

_MASK = 0xFFFFFFFF


class Mulberry32:
    """Seeded PRNG matching the JS mulberry32 implementation bit-for-bit."""

    def __init__(self, seed: int) -> None:
        self.seed = seed & _MASK

    @staticmethod
    def _imul(a: int, b: int) -> int:
        return (a * b) & _MASK

    def __call__(self) -> float:
        # Faithful port of:
        #   seed = (seed + 0x6D2B79F5) | 0
        #   let t = imul(seed ^ (seed >>> 15), 1 | seed)
        #   t = (t + imul(t ^ (t >>> 7), 61 | t)) ^ t
        #   return ((t ^ (t >>> 14)) >>> 0) / 4294967296
        self.seed = (self.seed + 0x6D2B79F5) & _MASK
        s = self.seed
        t = self._imul(s ^ (s >> 15), 1 | s)
        t = ((t + self._imul(t ^ (t >> 7), 61 | t)) & _MASK) ^ t
        t &= _MASK
        return ((t ^ (t >> 14)) & _MASK) / 4294967296.0


class Theme:
    def __init__(
        self,
        core: list[str],
        bridges: list[str],
        platform_bias: list[Platform],
        sentiment_bias: Sentiment,
    ) -> None:
        self.core = core
        self.bridges = bridges
        self.platform_bias = platform_bias
        self.sentiment_bias = sentiment_bias


THEMES: dict[str, Theme] = {
    "ai": Theme(
        ["ai", "chatgpt", "openai", "machine learning", "automation", "llm", "prompt"],
        ["jobs", "ethics", "tesla"],
        ["twitter", "reddit", "news"],
        "neutral",
    ),
    "crypto": Theme(
        ["bitcoin", "ethereum", "crypto", "blockchain", "nft", "web3", "defi"],
        ["tesla", "regulation", "ai"],
        ["twitter", "reddit"],
        "negative",
    ),
    "climate": Theme(
        ["climate", "sustainability", "renewable", "solar", "ev", "carbon"],
        ["tesla", "regulation", "fashion"],
        ["news", "twitter", "blog"],
        "neutral",
    ),
    "gaming": Theme(
        ["gaming", "esports", "twitch", "playstation", "nintendo", "steam"],
        ["nft", "ai", "streetwear"],
        ["youtube", "tiktok", "reddit"],
        "positive",
    ),
    "fashion": Theme(
        ["fashion", "streetwear", "sneakers", "nike", "thrift", "runway"],
        ["sustainability", "nft", "ai"],
        ["instagram", "tiktok"],
        "positive",
    ),
    "wellness": Theme(
        ["wellness", "fitness", "mindfulness", "nutrition", "running", "sleep"],
        ["ai", "sustainability", "fashion"],
        ["instagram", "tiktok", "youtube"],
        "positive",
    ),
}

AUTHORS = [
    "@maya_t", "@devon", "@nori", "@kp_writes", "@late_night_dev", "@sora",
    "@green_juno", "@bitflux", "@runwaykid", "@coachZ", "@pixelpede", "@anon",
]

ALL_PLATFORMS: list[Platform] = [
    "twitter", "reddit", "instagram", "tiktok", "youtube", "news", "forum", "blog",
]

_SENTIMENTS: list[Sentiment] = ["positive", "neutral", "negative"]


def _pick(rng: Mulberry32, arr: list):
    return arr[int(rng() * len(arr))]


def _sample_sentiment(rng: Mulberry32, bias: Sentiment) -> Sentiment:
    r = rng()
    if r < 0.55:
        return bias
    others = [s for s in _SENTIMENTS if s != bias]
    return others[0] if r < 0.8 else others[1]


def generate_sample_mentions(n: int = 1500, seed: int = 42) -> list[Mention]:
    """Generate ``n`` synthetic mentions across all themes."""
    rng = Mulberry32(seed)
    theme_names = list(THEMES.keys())
    now = datetime.now(timezone.utc)
    mentions: list[Mention] = []

    for i in range(n):
        theme_name = _pick(rng, theme_names)
        theme = THEMES[theme_name]

        k = 2 + int(rng() * 3)
        shuffled = sorted(theme.core, key=lambda _: rng() - 0.5)
        keywords = set(shuffled[:k])

        if rng() < 0.3 and theme.bridges:
            keywords.add(_pick(rng, theme.bridges))

        sentiment = _sample_sentiment(rng, theme.sentiment_bias)
        platform = (
            _pick(rng, theme.platform_bias)
            if rng() < 0.75
            else _pick(rng, ALL_PLATFORMS)
        )

        reach = round(50 + (rng() ** 4) * 500_000)

        days_ago = int(rng() * 30)
        date = now - timedelta(days=days_ago, seconds=int(rng() * 86_400))

        mentions.append(
            Mention(
                id=f"m_{i:x}",
                date=date.isoformat(),
                platform=platform,
                author=_pick(rng, AUTHORS),
                text=f"{' + '.join(sorted(keywords))} — {theme_name} chatter",
                sentiment=sentiment,
                reach=reach,
                keywords=sorted(keywords),
            )
        )

    return mentions
