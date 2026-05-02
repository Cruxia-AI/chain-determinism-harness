"""Backfill chain-determinism-bench-v1 phase_2_v2.jsonl from raw Phase 2 runs.

Reads /tmp/p2_qwen-2.5-72b_*.jsonl (1600 raw runs from Modal vLLM Phase 2) and
emits hash-only Receipts under chain_determinism_bench/data/phase_2_v2.jsonl
matching the schema in prepare.py.

Why this exists separately from prepare.py: the original Phase 2 raw runs were
not persisted under `results/benchmarks/paper5/`; they exist locally at
`/tmp/p2_qwen-2.5-72b_*.jsonl`. This script bridges that gap so the released
HF dataset has the per-run data backing the §4 McNemar test result.

Usage:
    python chain_determinism_bench/backfill_phase2.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "chain_determinism_bench/data/phase_2_v2.jsonl"
OUT.parent.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "chain_receipt_core/python"))
from chain_receipt_core.hash import (  # noqa: E402
    compute_text_hash,
    compute_tool_calls_hash,
)


def hash_response(rationale: str | None, final_raw: str | None) -> str:
    r = unicodedata.normalize("NFC", rationale or "")
    f = unicodedata.normalize("NFC", final_raw or "")
    body = (r + "\n<<final_answer>>\n" + f).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


HELDOUT_QUERIES_PATH = (
    ROOT / "lab/epistemic_development/pipeline/dispatch_ood/data/held_out_ood.jsonl"
)
heldout_qs: dict[str, dict] = {}
with HELDOUT_QUERIES_PATH.open() as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        q = json.loads(line)
        heldout_qs[q["query_id"]] = q


def build_heldout_prompt(q: dict) -> str:
    nl = q.get("query_text") or q.get("nl_query") or ""
    return (
        "You are an analyst with access to a knowledge graph of beliefs and citations. "
        "Use the available tools to answer the question. Bind tool outputs to variables "
        "(v1, v2, ...) as needed. Call final_answer with the result.\n\n"
        f"Question: {nl}"
    )


SOURCE_FILES = {
    "baseline_all_on": Path("/tmp/p2_qwen-2.5-72b_baseline_all_on.jsonl"),
    "batch_invariant_proxy": Path("/tmp/p2_qwen-2.5-72b_batch_invariant_proxy.jsonl"),
}


def build_row(raw: dict, toggle: str) -> dict | None:
    qid = raw.get("query_id", "")
    q = heldout_qs.get(qid)
    if q is None:
        return None
    prompt = build_heldout_prompt(q)
    seq = raw.get("tool_call_sequence") or []
    rationale = raw.get("rationale", "") or ""
    final_norm = raw.get("final_answer_norm", "") or ""
    if not isinstance(final_norm, str):
        final_norm = str(final_norm)

    return {
        "row_id": str(uuid.uuid4()),
        "phase": "phase_2_v2",
        "vendor": "modal-vllm",
        "model": raw.get("model", "qwen-2.5-72b"),
        "toggle": toggle,
        "temperature": float(raw.get("temperature", 0.0)),
        "query_id": qid,
        "query_type": raw.get("query_type", ""),
        "kb_id": raw.get("kb_id", ""),
        "prompt": prompt,
        "prompt_hash": compute_text_hash(prompt),
        "response_hash": hash_response(rationale, final_norm),
        "tool_calls_hash": compute_tool_calls_hash(seq),
        "final_answer_hash": compute_text_hash(final_norm),
        "run_idx": int(raw.get("run_idx", 0)),
        "n_tool_calls": int(raw.get("n_tool_calls", 0)),
        "error_category": raw.get("error_category"),
        "latency_s": None,
        "in_tokens": None,
        "out_tokens": None,
    }


total_in = 0
total_out = 0
rows: list[dict] = []
for toggle, path in SOURCE_FILES.items():
    if not path.exists():
        print(f"  WARNING: missing {path}", flush=True)
        continue
    n_in = 0
    n_out = 0
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            row = build_row(raw, toggle=toggle)
            if row is not None:
                rows.append(row)
                n_out += 1
    print(f"  {path.name}: {n_in} in -> {n_out} out", flush=True)
    total_in += n_in
    total_out += n_out

with OUT.open("w") as f:
    for r in rows:
        f.write(json.dumps(r, default=str) + "\n")

# SHA-256 of the file (for croissant update)
sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
size = OUT.stat().st_size
print(f"\n  Wrote {len(rows)} rows -> {OUT}")
print(f"  SHA-256: {sha}")
print(f"  Size:    {size} bytes")
