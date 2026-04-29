"""CLI entry point for chain-determinism-harness.

Usage::

    python -m chain_determinism_harness eval --model X [--n-queries N] [--n-replays K]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

from .client import make_client, run_query
from .metrics import chain_divergence_rate, format_summary
from .queries import QUERIES
from .tools import SYSTEM_PROMPT, TOOL_SCHEMAS_OPENAI, stub_tool_response


def _check_credentials():
    if not (os.environ.get("OPENAI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")):
        print("ERROR: no API key found. Set one of:", file=sys.stderr)
        print("    OPENAI_API_KEY=sk-...", file=sys.stderr)
        print("    OPENROUTER_API_KEY=sk-or-...", file=sys.stderr)
        print("    ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(2)


async def _eval_async(args) -> dict:
    queries = QUERIES[: args.n_queries]
    print(f"==> chain-determinism-harness eval")
    print(f"    model:       {args.model}")
    print(f"    queries:     {len(queries)}  (out of {len(QUERIES)} embedded)")
    print(f"    replays:     {args.n_replays} per query")
    print(f"    total calls: {len(queries) * args.n_replays}")
    print(f"    temperature: {args.temperature}")
    print(f"    concurrency: {args.concurrency}")
    print(f"    base_url:    {args.base_url or '(default — OpenAI or OpenRouter via env)'}")
    print()

    client = make_client(base_url=args.base_url, timeout=args.timeout)

    t0 = time.time()
    all_runs: list[dict] = []
    for i, q in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {q['query_id'][:80]}", flush=True)
        runs = await run_query(
            client, args.model, q,
            n_replays=args.n_replays,
            temperature=args.temperature,
            system_prompt=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS_OPENAI,
            stub_tool_response=stub_tool_response,
            concurrency=args.concurrency,
        )
        all_runs.extend(runs)
        n_err = sum(1 for r in runs if r.get("error_category"))
        n_ok = len(runs) - n_err
        unique_seqs = len({tuple((s.get("name"), json.dumps(s.get("args", {}), sort_keys=True))
                                  for s in (r.get("tool_call_sequence") or []))
                            for r in runs if not r.get("error_category")})
        print(f"      ok={n_ok}/{len(runs)}  unique_sequences={unique_seqs}")

    elapsed = time.time() - t0
    print(f"\n  elapsed: {elapsed:.1f}s")

    stats = chain_divergence_rate(all_runs)
    print(format_summary(stats, args.model))

    out = {
        "model": args.model,
        "n_queries": len(queries),
        "n_replays": args.n_replays,
        "temperature": args.temperature,
        "elapsed_s": elapsed,
        **stats,
    }
    if args.out:
        with open(args.out, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"  wrote: {args.out}")
        # Also dump per-replay rows if requested
        if args.runs_out:
            with open(args.runs_out, "w") as f:
                for r in all_runs:
                    f.write(json.dumps(r, default=str) + "\n")
            print(f"  wrote per-replay: {args.runs_out}")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="chain-determinism-harness",
        description="Measure chain-determinism for any OpenAI-compatible LLM endpoint.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("eval", help="Run chain-divergence measurement")
    e.add_argument("--model", required=True,
                   help="Model identifier (e.g., gpt-4.1, qwen/qwen-2.5-72b-instruct)")
    e.add_argument("--n-queries", type=int, default=5,
                   help="Number of held-out queries to use (max 10 embedded; default 5)")
    e.add_argument("--n-replays", type=int, default=10,
                   help="Replays per query (default 10)")
    e.add_argument("--temperature", type=float, default=0.0,
                   help="Sampling temperature (default 0.0)")
    e.add_argument("--concurrency", type=int, default=5,
                   help="Max concurrent replay calls (default 5)")
    e.add_argument("--base-url", default=None,
                   help="API base URL. If unset, falls back to OPENAI_API_KEY or OPENROUTER_API_KEY env auto-detection.")
    e.add_argument("--timeout", type=float, default=60.0,
                   help="Per-request timeout in seconds (default 60)")
    e.add_argument("--out", default=None,
                   help="Write summary JSON to this path")
    e.add_argument("--runs-out", default=None,
                   help="Write per-replay JSONL to this path (for downstream analysis)")
    args = parser.parse_args(argv)

    if args.cmd == "eval":
        if args.n_queries > len(QUERIES):
            print(f"ERROR: --n-queries={args.n_queries} exceeds embedded set ({len(QUERIES)})",
                  file=sys.stderr)
            sys.exit(2)
        _check_credentials()
        asyncio.run(_eval_async(args))


if __name__ == "__main__":
    main()
