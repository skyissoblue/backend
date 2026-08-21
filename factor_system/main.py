"""Factor-system CLI."""
from __future__ import annotations

import argparse
import json
import random

from .factor_lib.registry import auto_discover, list_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A-share local factor system")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--kind", choices=("ta", "alpha", "pattern"))
    run.add_argument("--codes")
    listing = sub.add_parser("list")
    listing.add_argument("--kind", choices=("ta", "alpha", "pattern"))
    sub.add_parser("status")
    sub.add_parser("verify")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    auto_discover()
    if args.command == "run":
        from .precompute import run_all
        print(json.dumps(run_all(args.kind, args.codes.split(",") if args.codes else None), ensure_ascii=False))
    elif args.command == "list":
        items = [item for item in list_all() if args.kind is None or item["kind"] == args.kind]
        for kind in ("ta", "alpha", "pattern"):
            names = [item["name"] for item in items if item["kind"] == kind]
            if names: print(f"{kind} ({len(names)}): " + ", ".join(names))
    elif args.command == "status":
        from . import redis_store
        print(json.dumps({"redis": redis_store.health_check(), "stock_keys": sum(1 for _ in redis_store.client().scan_iter("stock:*")), **redis_store.get_memory_usage()}, ensure_ascii=False))
    else:
        from . import kline_reader
        from .precompute import run_single
        codes = random.sample(kline_reader.get_all_codes(), min(10, len(kline_reader.get_all_codes())))
        print(json.dumps({code: len(run_single(code)) for code in codes}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
