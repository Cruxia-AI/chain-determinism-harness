"""Tests for chain_determinism_harness.metrics."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chain_determinism_harness.metrics import (
    chain_divergence_rate,
    seq_full,
    wilson_ci,
)


def test_seq_full_byte_identical():
    a = [{"name": "filter_beliefs", "args": {"term": "x"}}]
    b = [{"name": "filter_beliefs", "args": {"term": "x"}}]
    assert seq_full(a) == seq_full(b)


def test_seq_full_arg_order_invariant():
    """Args dict ordering must NOT affect the hash (we sort keys)."""
    a = [{"name": "filter_author", "args": {"in": "v1", "author": "alice"}}]
    b = [{"name": "filter_author", "args": {"author": "alice", "in": "v1"}}]
    assert seq_full(a) == seq_full(b)


def test_seq_full_different_args_diverge():
    a = [{"name": "filter_beliefs", "args": {"term": "x"}}]
    b = [{"name": "filter_beliefs", "args": {"term": "y"}}]
    assert seq_full(a) != seq_full(b)


def test_seq_full_different_op_diverge():
    a = [{"name": "filter_beliefs", "args": {"term": "x"}}]
    b = [{"name": "all_beliefs", "args": {}}]
    assert seq_full(a) != seq_full(b)


def test_wilson_ci_known():
    # 0/40 → CI lo = 0, hi ≈ 0.088 (matches paper §4 batch_invariant_proxy)
    lo, hi = wilson_ci(0, 40)
    assert lo == 0.0
    assert 0.08 < hi < 0.10


def test_wilson_ci_11_of_40():
    # 11/40 → CI matches paper §4 baseline_all_on [0.161, 0.428]
    lo, hi = wilson_ci(11, 40)
    assert 0.155 < lo < 0.170
    assert 0.420 < hi < 0.435


def test_chain_divergence_rate_no_divergence():
    # 5 replays of same query, all identical → not diverged
    runs = [
        {"query_id": "q1", "tool_call_sequence":
            [{"name": "filter_beliefs", "args": {"term": "x"}},
             {"name": "count", "args": {"in": "v1"}}]}
        for _ in range(5)
    ]
    stats = chain_divergence_rate(runs)
    assert stats["n_diverged"] == 0
    assert stats["n_measurable"] == 1
    assert stats["divergence_rate"] == 0.0


def test_chain_divergence_rate_with_divergence():
    # 5 replays where 2 differ → diverged
    runs = (
        [{"query_id": "q1", "tool_call_sequence":
            [{"name": "filter_beliefs", "args": {"term": "x"}}]}
         for _ in range(3)]
        +
        [{"query_id": "q1", "tool_call_sequence":
            [{"name": "all_beliefs", "args": {}}]}
         for _ in range(2)]
    )
    stats = chain_divergence_rate(runs)
    assert stats["n_diverged"] == 1
    assert stats["divergence_rate"] == 1.0


def test_chain_divergence_rate_insufficient():
    # Only 3 replays — below min_success=5 → not measurable
    runs = [
        {"query_id": "q1", "tool_call_sequence":
            [{"name": "filter_beliefs", "args": {"term": "x"}}]}
        for _ in range(3)
    ]
    stats = chain_divergence_rate(runs)
    assert stats["n_measurable"] == 0
    assert stats["per_query"][0]["status"] == "insufficient"


def test_chain_divergence_rate_excludes_errors():
    # 4 success + 5 errors → only 4 measurable replays of the only query
    # = below min_success=5 → not measurable
    runs = (
        [{"query_id": "q1", "tool_call_sequence":
            [{"name": "filter_beliefs", "args": {"term": "x"}}]}
         for _ in range(4)]
        +
        [{"query_id": "q1", "tool_call_sequence": [],
          "error_category": "api_error"}
         for _ in range(5)]
    )
    stats = chain_divergence_rate(runs)
    assert stats["n_errors"] == 5
    assert stats["n_measurable"] == 0


if __name__ == "__main__":
    import sys as _sys
    fns = [k for k in globals() if k.startswith("test_")]
    fail = 0
    for k in sorted(fns):
        try:
            globals()[k]()
            print(f"  PASS  {k}")
        except AssertionError as e:
            print(f"  FAIL  {k}: {e}")
            fail += 1
        except Exception as e:
            print(f"  ERROR {k}: {type(e).__name__}: {e}")
            fail += 1
    print(f"\n  {len(fns) - fail}/{len(fns)} tests passed.")
    _sys.exit(0 if fail == 0 else 1)
