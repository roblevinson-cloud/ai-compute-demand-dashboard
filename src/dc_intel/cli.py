from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime

from .db import connect, init_database, upsert_sources
from .demo import build_demo_data
from .digest import write_digest
from .pipeline import collect_due, process_pending, run_once, run_worker
from .site import build_site
from .source_registry import load_source_registry, source_summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dc-intel", description="Data-center development intelligence monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create or upgrade the PostgreSQL schema")
    sub.add_parser("sync-sources", help="Load config/sources.yml into PostgreSQL")
    sub.add_parser("seed-demo-db", help="Upsert the New Mexico pilot into PostgreSQL")
    sub.add_parser("collect", help="Poll due sources and preserve new raw documents")
    sub.add_parser("process", help="Extract and resolve unprocessed documents")
    sub.add_parser("run-once", help="Sync sources, collect, and process one cycle")
    worker = sub.add_parser("worker", help="Run the scheduled collection worker")
    worker.add_argument("--poll-seconds", type=int, default=60)
    build = sub.add_parser("build-demo", help="Build the evidence-backed New Mexico pilot dashboard")
    build.add_argument("--output", default="docs/index.html")
    live = sub.add_parser("build-live", help="Build the dashboard from PostgreSQL")
    live.add_argument("--output", default="docs/index.html")
    digest = sub.add_parser("digest", help="Generate email-ready digest files from the pilot dataset")
    digest.add_argument("--type", choices=["morning", "evening"], default="evening")
    digest.add_argument("--as-of", default=None)
    sub.add_parser("source-summary", help="Validate and summarize the source registry")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parser().parse_args(argv)
    if args.command == "init-db":
        init_database()
        print("PostgreSQL schema is ready.")
    elif args.command == "sync-sources":
        sources = load_source_registry()
        with connect() as connection:
            count = upsert_sources(connection, sources)
        print(f"Synchronized {count} sources.")
    elif args.command == "seed-demo-db":
        from .seed import seed_demo_database

        with connect() as connection:
            print(json.dumps(seed_demo_database(connection), indent=2))
    elif args.command == "collect":
        with connect() as connection:
            print(json.dumps(collect_due(connection), indent=2))
    elif args.command == "process":
        with connect() as connection:
            print(json.dumps(process_pending(connection), indent=2))
    elif args.command == "run-once":
        print(json.dumps(run_once(), indent=2))
    elif args.command == "worker":
        run_worker(poll_seconds=args.poll_seconds)
    elif args.command == "build-demo":
        path = build_site(build_demo_data(), args.output)
        print(f"Built {path}")
    elif args.command == "build-live":
        from .dashboard import build_live_dashboard_data

        with connect() as connection:
            path = build_site(build_live_dashboard_data(connection), args.output)
        print(f"Built {path}")
    elif args.command == "digest":
        data = build_demo_data()
        as_of = args.as_of or datetime.now(UTC).replace(microsecond=0).isoformat()
        paths = write_digest(data["events"], args.type, as_of)
        print("\n".join(str(path) for path in paths))
    elif args.command == "source-summary":
        print(json.dumps(source_summary(load_source_registry()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
