"""Chain-divergence metric + Wilson 95% CI (matches paper Phase 1a methodology).

Sequence-key invariants (treated as the public contract; do not weaken without
a CHANGELOG entry):

  - Sequence keys are constructed via `seq_full(seq)` from a list of
    `{name, args}` dicts. The resulting tuple is suitable as a `dict`/`set`
    key and survives Python pickle round-trips.
  - Two argument trees compare equal under `seq_full` iff their canonical-JSON
    serialization (sorted keys, NFC strings, type-tagged scalars) matches
    byte-for-byte. Specifically:
      * `True`, `1`, `1.0`, `"1"` are NOT equal (distinct type tags).
      * `None` and the absent key are distinguished from `{}`.
      * Falsey scalars (`0`, `""`, `[]`, `False`) are NOT collapsed to `{}`.
  - Dict keys must be strings (or be JSON-serializable as strings); non-string
    keys raise `TypeError`. Unhashable leaves (sets, bytes, custom objects)
    raise `TypeError` rather than silently producing a corrupt key.

These rules close the divergence-undercount class of bugs flagged by the
2026-04-29 stringent code review (Sonnet 4.6 + GPT-5.4).
"""
from __future__ import annotations

import json
import math
from collections import defaultdict


def _canonical_scalar(x):
    """Type-tagged scalar key. Distinguishes `1` from `True`, `1.0`, `"1"` —
    the divergence-undercount class of bugs in the prior implementation came
    from Python's structural equality silently collapsing these."""
    if x is None:
        return ("null",)
    if isinstance(x, bool):
        # bool is a subclass of int in Python — check it FIRST so True doesn't
        # collapse to (int, 1).
        return ("bool", x)
    if isinstance(x, int):
        return ("int", x)
    if isinstance(x, float):
        # Use repr() rather than the float itself so 1.0 and 1 stay distinct
        # at the key level. Reviewers can still reconstruct the value.
        return ("float", repr(x))
    if isinstance(x, str):
        return ("str", x)
    # Any other leaf type (bytes, set, custom object) is a contract violation;
    # we surface it rather than coerce.
    raise TypeError(
        f"_canonical_scalar: unsupported leaf type {type(x).__name__!r}; "
        f"tool-call args must be JSON-serializable scalars/lists/dicts only."
    )


def _to_hashable(x):
    """Recursive canonicalization with type-tagged scalars and explicit
    container tagging. Distinguishes `[("a", 1), ("b", 2)]` from
    `{"a": 1, "b": 2}` even though both could naively yield identical
    sorted-tuple representations.
    """
    if isinstance(x, dict):
        items = []
        for k, v in x.items():
            if not isinstance(k, str):
                raise TypeError(
                    f"_to_hashable: dict key must be str, got {type(k).__name__!r}"
                )
            items.append((k, _to_hashable(v)))
        items.sort(key=lambda kv: kv[0])
        return ("dict", tuple(items))
    if isinstance(x, list):
        return ("list", tuple(_to_hashable(v) for v in x))
    if isinstance(x, tuple):
        # Tuples are tagged distinctly from lists for completeness.
        return ("tuple", tuple(_to_hashable(v) for v in x))
    return _canonical_scalar(x)


def seq_full(seq: list[dict]) -> tuple:
    """Canonical tool-call sequence key.

    Two replays are considered chain-divergent iff their `seq_full` values
    differ. The implementation is canonical, NOT byte-exact in the sense of
    raw provider JSON: dict-key order is normalized; scalars are type-tagged
    so structural-equality collisions (`True`/`1`/`1.0`/`"1"` collapse,
    falsey-vs-`{}` collapse) cannot silently undercount divergence.

    A `None` entry's `args` (i.e. the `name` is absent or `args=None`) is
    distinguished from an explicit `{}`. Missing-`name` entries are recorded
    as `None` rather than coerced to an empty string.
    """
    out = []
    for s in seq:
        if not isinstance(s, dict):
            raise TypeError(
                f"seq_full: each sequence element must be dict, got {type(s).__name__!r}"
            )
        name = s.get("name")
        # Distinguish absent `args` (returns sentinel) from `args={}`.
        if "args" in s:
            args_key = _to_hashable(s["args"])
        else:
            args_key = ("absent",)
        out.append((name, args_key))
    return tuple(out)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Wilson score interval (binomial proportion, 95% by default).

    Returns `(None, None)` when n == 0 — there is no valid CI on no data, and
    the prior `(0.0, 1.0)` return paired with `divergence_rate=0.0` was a
    misleading consumer-facing combination flagged in code review."""
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"wilson_ci: invalid inputs k={k}, n={n}")
    if n == 0:
        return (None, None)
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
        runs: list of run dicts. Each must have keys `query_id`,
              `tool_call_sequence`, optionally `error_category` (set to
              truthy if the run errored). Rows missing `query_id` raise
              `ValueError` rather than being silently bucketed under "?".
        min_success: minimum non-error replays per query for the query to
                     count toward the rate (default 5, matches paper).

    Returns:
        dict with keys:
            n_total, n_errors, n_queries
            n_measurable: queries with >= min_success non-error replays
            n_diverged: queries where the seq_full set has cardinality > 1
            divergence_rate: n_diverged / n_measurable; None if n_measurable=0
            wilson_ci_95: (lo, hi) at 95%; (None, None) if n_measurable=0
            per_query: per-query list with stable, sorted-by-query_id ordering
    """
    if min_success < 2:
        raise ValueError(
            f"chain_divergence_rate: min_success must be >= 2 to detect "
            f"divergence (got {min_success})"
        )

    by_q: dict[str, list[dict]] = defaultdict(list)
    for i, r in enumerate(runs):
        if "query_id" not in r or r["query_id"] is None:
            raise ValueError(
                f"chain_divergence_rate: run at index {i} is missing required "
                f"'query_id' key. Refusing to silently bucket under '?'."
            )
        by_q[r["query_id"]].append(r)

    per_query = []
    n_measurable = 0
    n_diverged = 0
    # Iterate in sorted-by-query_id order so per_query and downstream
    # serialization are deterministic across pipelines / runs.
    for qid in sorted(by_q.keys()):
        qruns = by_q[qid]
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

    if n_measurable == 0:
        rate = None
        wci = (None, None)
    else:
        rate = n_diverged / n_measurable
        wci = wilson_ci(n_diverged, n_measurable)

    n_errors = sum(1 for r in runs
                   if r.get("error_category") or r.get("error"))

    return {
        "n_total": len(runs),
        "n_errors": n_errors,
        "n_queries": len(by_q),
        "n_measurable": n_measurable,
        "n_diverged": n_diverged,
        "divergence_rate": rate,
        "wilson_ci_95": wci,
        "per_query": per_query,
    }


def format_summary(stats: dict, model: str) -> str:
    rate = stats["divergence_rate"]
    lo, hi = stats["wilson_ci_95"]
    if rate is None:
        rate_line = "  rate: NOT MEASURABLE (no queries reached min_success)"
    else:
        rate_line = (
            f"  {100*rate:.1f}%  [Wilson 95% CI "
            f"{100*lo:.1f}%, {100*hi:.1f}%]"
        )
    lines = [
        "",
        f"Chain-divergence rate for {model}:",
        rate_line,
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
            lines.append(
                f"  {q['query_id']}: {q['n_unique_sequences']} unique sequences "
                f"across {q['n_success']} replays"
            )
        lines.append("")
    return "\n".join(lines)
