"""Social Tinder CLI.

    python -m social_tinder serve                 # live FastAPI app at :8000
    python -m social_tinder export -o network.html   # standalone interactive HTML
    python -m social_tinder json   -o network.json   # raw network data
    python -m social_tinder top                   # print strongest connections

All commands accept the same filter flags (--min-strength, --min-cooccurrences,
--min-mentions, --max-nodes, --platforms, --search).
"""

from __future__ import annotations

import argparse
import json
import sys

from .client import fetch_mentions
from .network import build_network
from .types import NetworkQuery


def _add_filter_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--min-strength", type=float, default=0.04)
    p.add_argument("--min-cooccurrences", type=int, default=3)
    p.add_argument("--min-mentions", type=int, default=5)
    p.add_argument("--min-llr", type=float, default=0.0,
                   help="drop edges below this significance (Dunning G²)")
    p.add_argument("--max-nodes", type=int, default=80)
    p.add_argument("--platforms", default=None, help="comma-separated platform list")
    p.add_argument("--search", default=None, help="topic (live Brandwatch only)")


def _query(args: argparse.Namespace) -> NetworkQuery:
    return NetworkQuery(
        search=args.search,
        min_strength=args.min_strength,
        min_cooccurrences=args.min_cooccurrences,
        min_mentions=args.min_mentions,
        min_llr=args.min_llr,
        max_nodes=args.max_nodes,
        platforms=[p for p in args.platforms.split(",") if p] if args.platforms else None,
    )


def _build(args: argparse.Namespace):
    query = _query(args)
    mentions, source = fetch_mentions(query)
    net = build_network(mentions, query)
    net.source = source
    return net


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn/fastapi not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1
    print(f"Social Tinder running at http://{args.host}:{args.port}")
    uvicorn.run("social_tinder.server:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .viz import static_page

    net = _build(args)
    html = static_page(net.to_dict())
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {args.out} — {len(net.nodes)} keywords, {len(net.edges)} connections "
          f"({net.source} data). Open it in a browser.")
    return 0


def cmd_json(args: argparse.Namespace) -> int:
    net = _build(args)
    payload = json.dumps(net.to_dict(), indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"Wrote {args.out}")
    else:
        print(payload)
    return 0


def cmd_top(args: argparse.Namespace) -> int:
    net = _build(args)
    clusters = len({n.cluster for n in net.nodes})
    print(f"source={net.source}  mentions={net.total_mentions}  "
          f"nodes={len(net.nodes)}  edges={len(net.edges)}  communities={clusters}")

    print("\nStrongest connections (by significance, G²):")
    for e in sorted(net.edges, key=lambda x: -x.llr)[: args.limit]:
        print(f"  {e.source:>16}  <->  {e.target:<16}  "
              f"llr={e.llr:7.1f}  strength={e.strength:.3f}  co={e.cooccurrences}")

    print("\nMost influential keywords (PageRank):")
    for n in sorted(net.nodes, key=lambda x: -x.influence)[:8]:
        print(f"  {n.id:>16}  influence={n.influence:.4f}  community={n.cluster}")

    print("\nTop bridge keywords (betweenness — connect communities):")
    for n in sorted(net.nodes, key=lambda x: -x.bridge)[:8]:
        print(f"  {n.id:>16}  bridge={n.bridge:.4f}  community={n.cluster}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="social_tinder", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="run the live FastAPI app")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_export = sub.add_parser("export", help="write a standalone interactive HTML")
    p_export.add_argument("-o", "--out", default="network.html")
    _add_filter_args(p_export)
    p_export.set_defaults(func=cmd_export)

    p_json = sub.add_parser("json", help="dump the network as JSON")
    p_json.add_argument("-o", "--out", default=None)
    _add_filter_args(p_json)
    p_json.set_defaults(func=cmd_json)

    p_top = sub.add_parser("top", help="print strongest connections")
    p_top.add_argument("--limit", type=int, default=20)
    _add_filter_args(p_top)
    p_top.set_defaults(func=cmd_top)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
