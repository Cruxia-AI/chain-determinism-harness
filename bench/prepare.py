"""Build chain-determinism-bench-v1 hash-only HF dataset splits.

Reads per-run JSONL files in `results/benchmarks/paper5/` and writes
4 split files (`phase_1a.jsonl`, `phase_1b.jsonl`, `phase_2_v2.jsonl`,
`phase_3_5_swebench.jsonl`) under `chain_determinism_bench/data/`.

IP guardrails:
  - Per-row schema is HASH-ONLY for response/tool-calls/final-answer.
  - Prompt text is included (synthetic Sigma-registry queries; ours to publish).
  - No raw rationales, no raw vendor responses.
  - Hashes are byte-identical to `paper5_multivendor_replay.py::_seq_full`
    via `chain_receipt_core.compute_text_hash` / `compute_tool_calls_hash`.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "chain_determinism_bench" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Use the published chain_receipt_core hash helpers — these are byte-identical
# to paper4_replay_determinism::_seq_full per the SDK spec.
sys.path.insert(0, str(ROOT / "chain_receipt_core" / "python"))
from chain_receipt_core.hash import (  # noqa: E402
    compute_text_hash,
    compute_tool_calls_hash,
)

# --- canonical hash for final answer (NFC + utf-8 + sha256) -----------------
def hash_text(s: str | None) -> str:
    return compute_text_hash(s or "")


def hash_response(rationale: str | None, final_raw: str | None) -> str:
    """Response hash combines rationale + final_answer_raw.

    These are the only response-side bytes captured per run (see
    paper5_multivendor_replay::_run_anthropic_once / _run_openai_compatible_once).
    Combined as NFC(rationale) + '\\n<<final_answer>>\\n' + NFC(final_raw)
    to disambiguate empty-rationale-but-text-only-response cases.
    """
    r = unicodedata.normalize("NFC", rationale or "")
    f = unicodedata.normalize("NFC", final_raw or "")
    body = (r + "\n<<final_answer>>\n" + f).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


# --- vendor mapping ---------------------------------------------------------
ANTHROPIC_MODELS = {"claude-sonnet-4-5", "claude-opus-4-6"}
OPENAI_MODELS = {"gpt-5.4", "gpt-4.1", "o3"}
# everything else routed via OpenRouter

def vendor_for(model: str) -> str:
    if model in ANTHROPIC_MODELS:
        return "anthropic"
    if model in OPENAI_MODELS:
        return "openai"
    return "openrouter"


# --- build prompt-text registry --------------------------------------------
HELDOUT_QUERIES_PATH = (
    ROOT / "lab/epistemic_development/pipeline/dispatch_ood/data/held_out_ood.jsonl"
)
SWEBENCH_LITE_PATH = ROOT / "data/swebench_lite_test.json"

print(f"Loading held-out OOD queries from {HELDOUT_QUERIES_PATH} ...", flush=True)
heldout_qs: dict[str, dict] = {}
with HELDOUT_QUERIES_PATH.open() as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        q = json.loads(line)
        heldout_qs[q["query_id"]] = q
print(f"  loaded {len(heldout_qs)} OOD queries", flush=True)

print(f"Loading SWE-bench Lite tasks from {SWEBENCH_LITE_PATH} ...", flush=True)
swebench_tasks: dict[str, dict] = {}
with SWEBENCH_LITE_PATH.open() as f:
    for t in json.load(f):
        swebench_tasks[t["instance_id"]] = t
print(f"  loaded {len(swebench_tasks)} SWE-bench Lite tasks", flush=True)


SYSTEM_PROMPT_HELDOUT = """You are a precise analyst answering questions about a structured knowledge graph of source entries (each with source_id, term, definition, timestamp, author, optional `revises` predecessor).

You have access to 21 primitive tool functions that operate on the knowledge graph. To answer a question:
1. Compose primitives by passing the variable name of a previous step's result (e.g., "v1") as the `in` argument of a later primitive.
2. Each tool result will be returned to you with a step variable name (v1, v2, ...).
3. After at most 10 tool calls, you MUST invoke `final_answer(answer="...")` with a concise final answer.

The graders are deterministic and exact-match: emit exact source_ids, integer counts, or yes/no when relevant. Avoid prose explanations in the final answer; just give the value(s).

Compose primitives carefully — do NOT try to read the KB and answer directly. Use tool calls to compute the answer."""


def build_heldout_prompt(q: dict) -> str:
    parts = [f"# Knowledge base id: {q['kb_id']}",
             "(Use tool calls like `all_beliefs()` or `filter_beliefs(term=...)` "
             "to inspect contents.)"]
    if q.get("target_term"):
        parts.append(f"Target term mentioned in the question: '{q['target_term']}'")
    summary = "\n".join(parts)
    user = (
        f"{summary}\n\n"
        f"Question: {q['question']}\n\n"
        f"Use the primitive tools to compute the answer; then call final_answer "
        f"with just the value."
    )
    # System + user merged for canonical prompt-hash purposes.
    return f"<system>\n{SYSTEM_PROMPT_HELDOUT}\n</system>\n\n<user>\n{user}\n</user>"


def build_swebench_prompt(task_id: str) -> str:
    t = swebench_tasks.get(task_id, {})
    repo = t.get("repo", "?")
    problem = t.get("problem_statement", "")
    return (
        f"# Repository: {repo}\n"
        f"# Instance: {task_id}\n\n"
        f"Problem statement:\n{problem}\n\n"
        "Use the available tools (read_file, write_file, run_tests, etc.) to "
        "diagnose and patch the bug, then call final_answer with a brief summary "
        "of the fix."
    )


# --- per-row builder --------------------------------------------------------
def build_row(raw: dict, phase: str, *, swebench: bool = False) -> dict | None:
    model = raw.get("model")
    if not model:
        return None
    vendor = vendor_for(model)
    query_id = raw.get("query_id", "")
    if swebench:
        # query_id formatted as "swebench::<instance_id>"
        task_id = query_id.split("::", 1)[1] if "::" in query_id else query_id
        prompt = build_swebench_prompt(task_id)
    else:
        q = heldout_qs.get(query_id)
        if q is None:
            return None
        prompt = build_heldout_prompt(q)

    seq = raw.get("tool_call_sequence") or []
    rationale = raw.get("rationale", "") or ""
    final_raw = raw.get("final_answer_raw", "")
    if final_raw is None:
        final_raw = ""
    elif not isinstance(final_raw, str):
        final_raw = str(final_raw)
    final_norm = raw.get("final_answer_norm", "")
    if final_norm is None:
        final_norm = ""
    elif not isinstance(final_norm, str):
        final_norm = str(final_norm)

    row = {
        "row_id": str(uuid.uuid4()),
        "phase": phase,
        "vendor": vendor,
        "model": model,
        "temperature": float(raw.get("temperature", 0.0)),
        "query_id": query_id,
        "query_type": raw.get("query_type", ""),
        "kb_id": raw.get("kb_id", ""),
        "prompt": prompt,
        "prompt_hash": compute_text_hash(prompt),
        "response_hash": hash_response(rationale, final_raw),
        "tool_calls_hash": compute_tool_calls_hash(seq),
        "final_answer_hash": compute_text_hash(final_norm),
        "run_idx": int(raw.get("run_idx", 0)),
        "n_tool_calls": int(raw.get("n_tool_calls", 0)),
        "error_category": raw.get("error_category"),
        "latency_s": float(raw["latency_s"]) if raw.get("latency_s") is not None else None,
        "in_tokens": int(raw["in_tokens"]) if raw.get("in_tokens") is not None else None,
        "out_tokens": int(raw["out_tokens"]) if raw.get("out_tokens") is not None else None,
    }
    if swebench:
        row["task_id"] = task_id
    return row


# --- input file groups ------------------------------------------------------
P5_DIR = ROOT / "results/benchmarks/paper5"
PHASE_1A_FILES = [
    P5_DIR / "multivendor_anthropic.jsonl",
    P5_DIR / "multivendor_openai.jsonl",
    P5_DIR / "multivendor_openrouter.jsonl",
]
PHASE_1B_FILES = [
    P5_DIR / "phase1b_anthropic.jsonl",
    P5_DIR / "phase1b_openai.jsonl",
    P5_DIR / "phase1b_openrouter.jsonl",
]
PHASE_3_5_FILES = [P5_DIR / "swebench_lite_chain_div.jsonl"]


def process_files(files: list[Path], phase: str, *, swebench: bool = False) -> list[dict]:
    rows: list[dict] = []
    for fp in files:
        if not fp.exists():
            print(f"  WARNING: missing {fp}", flush=True)
            continue
        n_in = 0
        n_out = 0
        with fp.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n_in += 1
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row = build_row(raw, phase, swebench=swebench)
                if row is not None:
                    rows.append(row)
                    n_out += 1
        print(f"  {fp.name}: {n_in} in -> {n_out} out", flush=True)
    return rows


# --- write per-split files -------------------------------------------------
def write_split(rows: list[dict], name: str) -> None:
    out = OUT_DIR / f"{name}.jsonl"
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    print(f"  -> wrote {len(rows)} rows to {out}", flush=True)


print("\n=== Phase 1a (T=0 multi-vendor) ===", flush=True)
rows_1a = process_files(PHASE_1A_FILES, "phase_1a")
write_split(rows_1a, "phase_1a")

print("\n=== Phase 1b (T=1.0 sweep) ===", flush=True)
rows_1b = process_files(PHASE_1B_FILES, "phase_1b")
write_split(rows_1b, "phase_1b")

# Phase 2 v2: no per-run JSONL exists in this snapshot; only the aggregate
# `mechanism_attribution.json` (40 queries x 2 toggles, n_runs_total=800/toggle).
# We document this as missing and emit an empty split file so downstream
# consumers see the split exists but is empty for this release.
print("\n=== Phase 2 v2 (mechanism, Qwen 72B) ===", flush=True)
mech_attr_path = P5_DIR / "mechanism_attribution.json"
if mech_attr_path.exists():
    print(
        f"  NOTE: only aggregate {mech_attr_path.name} found; per-run JSONL was not "
        "persisted for this experiment. Emitting empty phase_2_v2.jsonl. "
        "Aggregate stats are summarized in README.md. (See report.)",
        flush=True,
    )
else:
    print("  WARNING: no mechanism file at all", flush=True)
write_split([], "phase_2_v2")

print("\n=== Phase 3.5 SWE-bench Lite ===", flush=True)
rows_35 = process_files(PHASE_3_5_FILES, "phase_3_5_swebench", swebench=True)
write_split(rows_35, "phase_3_5_swebench")

# --- summary ---------------------------------------------------------------
counts = {
    "phase_1a": len(rows_1a),
    "phase_1b": len(rows_1b),
    "phase_2_v2": 0,
    "phase_3_5_swebench": len(rows_35),
}
total = sum(counts.values())
print("\n=== Summary ===", flush=True)
for k, v in counts.items():
    print(f"  {k:24s}  {v:>6d}", flush=True)
print(f"  {'TOTAL':24s}  {total:>6d}", flush=True)

# Emit a counts.json to make programmatic verification trivial in upload.py.
(OUT_DIR / "counts.json").write_text(json.dumps(counts, indent=2))
print(f"\nWrote counts to {OUT_DIR / 'counts.json'}", flush=True)
