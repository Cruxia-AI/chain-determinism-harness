"""Chain-divergence metric + Wilson 95% CI (matches paper Phase 1a methodology)."""
from __future__ import annotations

import json
import math
from collections import defaultdict


def _to_hashable(x):
    if isinstance(x, dict):
        return tuple(sorted((k, _to_hashable(v)) for k, v in x.items()))
    if isinstance(x, list):
        return tuple(_to_hashable(v) for v in x)
    return x


def seq_full(seq: list[dict]) -> tuple:
    """Byte-exact tool-call sequence hash key.

    Matches `_seq_full` in scripts/paper4_replay_determinism.py — the
    operationalization the chain-determinism-bench-v1 dataset is built on.
    Two replays are considered chain-divergent iff their `seq_full` values
    differ.
    """
    return tuple(
        (s.get("name"), _to_hashable(s.get("args") or {}))
        for s in seq
    )


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval (binomial proportion, 95% by default)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def chain_divergence_rate(
    runs: list[dict],
    *,
    min_success: int = 5,
) -> dict:
    """Compute per-cell chain-divergence rate from replays.

    Args:
        runs: list of run dicts. Each must have keys `query_id`, `tool_call_sequence`,
              optionally `error_category` (set to truthy if the run errored).
        min_success: minimum non-error replays per query for the query to count
                     toward the rate (default 5, matches paper).

    Returns:
        dict with keys:
            n_total: total runs
            n_errors: error rows
            n_queries: distinct query_ids
            n_measurable: queries with >= min_success non-error replays
            n_diverged: queries where the seq_full set has cardinality > 1
            divergence_rate: n_diverged / n_measurable (0 if n_measurable = 0)
            wilson_ci_95: (lo, hi) Wilson score interval at 95%
            per_query: list of {query_id, n_total, n_success, diverged}
    """
    by_q: dict[str, list[dict]] = defaultdict(list)
    for r in runs:
        by_q[r.get("query_id", "?")].append(r)

    per_query = []
    n_measurable = 0
    n_diverged = 0
    for qid, qruns in by_q.items():
        ok = [r for r in qruns if not r.get("error_category") and not r.get("error")]
        n_total = len(qruns)
        n_success = len(ok)
        if n_success < min_success:
            per_query.append({
                "query_id": qid, "n_total": n_total, "n_success": n_success,
                "diverged": None, "status": "insufficient",
            })
            continue
        seqs = {seq_full(r.get("tool_call_sequence") or []) for r in ok}
        diverged = len(seqs) > 1
        per_query.append({
            "query_id": qid, "n_total": n_total, "n_success": n_success,
            "diverged": diverged, "status": "measurable",
            "n_unique_sequences": len(seqs),
        })
        n_measurable += 1
        if diverged:
            n_diverged += 1

    rate = n_diverged / n_measurable if n_measurable else 0.0
    lo, hi = wilson_ci(n_diverged, n_measurable)

    n_errors = sum(1 for r in runs
                   if r.get("error_category") or r.get("error"))

    return {
        "n_total": len(runs),
        "n_errors": n_errors,
        "n_queries": len(by_q),
        "n_measurable": n_measurable,
        "n_diverged": n_diverged,
        "divergence_rate": rate,
        "wilson_ci_95": (lo, hi),
        "per_query": per_query,
    }


def format_summary(stats: dict, model: str) -> str:
    rate = stats["divergence_rate"]
    lo, hi = stats["wilson_ci_95"]
    lines = [
        "",
        f"Chain-divergence rate for {model}:",
        f"  {100*rate:.1f}%  [Wilson 95% CI {100*lo:.1f}%, {100*hi:.1f}%]",
        "",
        f"  Diverged queries:    {stats['n_diverged']} / {stats['n_measurable']}",
        f"  Total replays:       {stats['n_total']}",
        f"  Error replays:       {stats['n_errors']}",
        f"  Insufficient cells:  {sum(1 for q in stats['per_query'] if q.get('status') == 'insufficient')}",
        "",
    ]
    div_qs = [q for q in stats["per_query"] if q.get("diverged")]
    if div_qs:
        lines.append("Diverged query breakdown:")
        for q in div_qs:
            lines.append(f"  {q['query_id']}: {q['n_unique_sequences']} unique sequences across {q['n_success']} replays")
        lines.append("")
    return "\n".join(lines)
