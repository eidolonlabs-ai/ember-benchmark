"""
EMBER CLI — run benchmarks from the command line.

Usage:
    ember run --adapter eidolon --url http://localhost:3456
    ember run --adapter ai-companions --db-url postgresql+asyncpg://...
    ember run --adapter eidolon --tiers 1,2
    ember run --adapter eidolon --json results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from ember.types import TierResult

# Lazy imports for adapters and tiers to keep startup fast


async def _run_benchmark(
    adapter_name: str,
    tiers: list[int],
    adapter_kwargs: dict,
    verbose: bool = False,
) -> list[TierResult]:
    """Run selected tiers against a named adapter."""
    # Resolve adapter
    adapter = _create_adapter(adapter_name, adapter_kwargs)

    await adapter.setup()

    results = []
    try:
        if 1 in tiers:
            from ember.tiers.tier1_extraction import run_tier1
            results.append(await run_tier1(adapter, verbose=verbose))

        if 2 in tiers:
            from ember.tiers.tier2_retrieval import run_tier2
            results.append(await run_tier2(adapter, verbose=verbose))

        if 2 in tiers:  # 2b is technically part of Tier 2
            from ember.tiers.tier2b_recency import run_tier2b
            results.append(await run_tier2b(adapter, verbose=verbose))

        if 3 in tiers:
            from ember.tiers.tier3_roundtrip import run_tier3
            results.append(await run_tier3(adapter, verbose=verbose))
    finally:
        await adapter.teardown()

    return results


def _create_adapter(name: str, kwargs: dict):
    """Instantiate an adapter by name."""
    if name == "eidolon":
        from ember.adapters.eidolon_mcp import EidolonMCPAdapter
        return EidolonMCPAdapter(
            server_url=kwargs.get("url", "http://localhost:3456"),
            user_id=kwargs.get("user_id", "ember-eval-user"),
        )
    elif name == "ai-companions":
        from ember.adapters.ai_companions import AICompanionsAdapter
        return AICompanionsAdapter(
            db_url=kwargs.get("db_url"),
        )
    elif name in {"eidolon-agent-memory", "eidolon_agent_memory"}:
        from ember.adapters.eidolon_agent_memory import EidolonAgentMemoryAdapter
        return EidolonAgentMemoryAdapter(
            server_url=kwargs.get("url", "http://localhost:3100"),
        )
    else:
        raise ValueError(
            f"Unknown adapter: {name!r}. "
            f"Available: eidolon, ai-companions, eidolon-agent-memory. "
            f"Or write your own — see docs/ADAPTERS.md"
        )


def _print_results(results: list[TierResult], verbose: bool = False) -> None:
    """Pretty-print benchmark results."""
    try:
        from rich.console import Console
        from rich.table import Table
        console = Console()

        table = Table(title="EMBER Benchmark Results", show_lines=True)
        table.add_column("Tier", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        for r in results:
            status = "[green]PASS[/green]" if r.passed else "[red]FAIL[/red]"
            details = ""
            if verbose:
                details = json.dumps(r.details, indent=2, default=str)[:200]
            table.add_row(r.tier, f"{r.score:.3f}", status, details)

        console.print(table)
    except ImportError:
        # Fallback without rich
        for r in results:
            print(r.summary())


def main():
    parser = argparse.ArgumentParser(
        prog="ember",
        description="EMBER: Emotionally-aware Memory Benchmark for Empathic Recall",
    )
    sub = parser.add_subparsers(dest="command")

    # --- run ---
    run_parser = sub.add_parser("run", help="Run benchmark tiers")
    run_parser.add_argument(
        "--adapter", "-a",
        required=True,
        help="Adapter name: eidolon, ai-companions, eidolon-agent-memory",
    )
    run_parser.add_argument(
        "--tiers", "-t",
        default="1,2,3",
        help="Comma-separated tier numbers to run (default: 1,2,3)",
    )
    run_parser.add_argument(
        "--url",
        default="http://localhost:3456",
        help="Server URL (for MCP adapters)",
    )
    run_parser.add_argument(
        "--db-url",
        help="Database URL (for direct-access adapters)",
    )
    run_parser.add_argument(
        "--user-id",
        default="ember-eval-user",
        help="User ID for test isolation",
    )
    run_parser.add_argument(
        "--json", "-j",
        help="Write JSON results to file",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed per-item results",
    )

    # --- list ---
    sub.add_parser("list", help="List available adapters and tiers")

    args = parser.parse_args()

    if args.command == "list":
        print("Adapters:")
        print("  eidolon        — Eidolon MCP Server (HTTP)")
        print("  ai-companions  — AI Companions (direct PostgreSQL)")
        print("  eidolon-agent-memory  — Eidolon Agent Memory MCP Server (HTTP)")
        print()
        print("Tiers:")
        print("  1  Extraction Quality (salience-weighted recall)")
        print("  2  Retrieval Quality (recall@k + graceful omission)")
        print("  2b Recency Bias (tests temporal ranking)")
        print("  3  End-to-End Roundtrip (extraction → retrieval)")
        print("  4  Relational Quality (planned)")
        print("  5  Agent Tool-Use (planned)")
        return

    if args.command == "run":
        tiers = [int(t.strip()) for t in args.tiers.split(",")]
        adapter_kwargs = {
            "url": args.url,
            "db_url": args.db_url,
            "user_id": args.user_id,
        }

        start = time.monotonic()
        results = asyncio.run(
            _run_benchmark(args.adapter, tiers, adapter_kwargs, args.verbose)
        )
        elapsed = time.monotonic() - start

        _print_results(results, args.verbose)
        print(f"\nCompleted in {elapsed:.1f}s")

        # Optionally write JSON
        if args.json:
            output = {
                "adapter": args.adapter,
                "tiers_run": tiers,
                "elapsed_seconds": round(elapsed, 2),
                "results": [r.model_dump() for r in results],
            }
            Path(args.json).write_text(
                json.dumps(output, indent=2, default=str),
                encoding="utf-8",
            )
            print(f"Results written to {args.json}")

        # Exit code: non-zero if any tier failed
        if any(not r.passed for r in results):
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
