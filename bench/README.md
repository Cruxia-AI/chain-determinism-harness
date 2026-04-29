---
license: cc-by-4.0
language:
- en
pretty_name: Chain-Determinism Bench v1
size_categories:
- 10K<n<100K
task_categories:
- other
tags:
- chain-determinism
- agent-reproducibility
- llm-evaluation
- audit-trail
- tool-calling
- eu-ai-act
configs:
- config_name: phase_1a
  data_files:
  - split: train
    path: data/phase_1a.jsonl
- config_name: phase_1b
  data_files:
  - split: train
    path: data/phase_1b.jsonl
- config_name: phase_2_v2
  data_files:
  - split: train
    path: data/phase_2_v2.jsonl
- config_name: phase_3_5_swebench
  data_files:
  - split: train
    path: data/phase_3_5_swebench.jsonl
---

# Chain-Determinism Bench v1

Reference dataset for *Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe for Replay-Attestable LLM Agents* (Ausili 2026, under peer review). Released by Cruxia-AI.

## What this is

31,764 hash-only observations from a 22,000-run multi-vendor chain-determinism study plus follow-up phases (Phase 1b temperature sweep, Phase 2 mechanism attribution, Phase 3.5 SWE-bench Lite). Each row records what an agent loop produced for one (vendor, model, temperature, query, run) cell — captured as **prompt text + content hashes**, not raw responses.

This is the supporting data for the §10 chain-divergence-rate measurements and the cross-vendor variance plots. Hashes are byte-identical to the [chain-receipt-sdk](https://pypi.org/project/chain-receipt-sdk/), so each row can be replayed via `chain-receipt replay <hash>`.

## Why hash-only

- **Vendor responses are not ours to redistribute.** We observed them; we publish hashes (the content-addressed audit-trail format the Chain-Receipt protocol uses).
- **Prompts are ours to publish.** They are synthetic Σ-registry queries we authored against held-out OOD knowledge bases.
- **Replication does not require raw responses** — anyone can re-run the prompt and verify the hash matches.

## Splits

| Split | Rows | Description |
|---|---|---|
| `phase_1a` | 22,000 | T=0.0 multi-vendor replay. 11 models × 40 held-out OOD queries × 50 runs. |
| `phase_1b` | 8,000 | Temperature sweep (T=0.5 / T=1.0). 10 models × 40 queries × 20 runs × 2 temps. One model dropped from 1b. |
| `phase_2_v2` | 1,600 | Mechanism attribution: Qwen 2.5 72B Instruct on Modal vLLM (A100-80GB:2). 40 held-out queries × 20 replays × 2 toggles (`baseline_all_on`, `batch_invariant_proxy`). `baseline_all_on` chain-divergence 27.5% [Wilson 95% CI 16.1%, 42.8%]; `batch_invariant_proxy` 0.0% [0.0%, 8.8%]; **McNemar exact-binomial two-sided p = 0.000977** (11 baseline-only-diverge discordant pairs, 0 reverse). Includes `toggle` field per row. |
| `phase_3_5_swebench` | 164 | SWE-bench Lite chain-divergence subset. 3 models × 30 instances × ~2 runs. |
| **TOTAL** | **31,764** | |

Vendor breakdown (Phase 1a): Anthropic 4,000 / OpenAI 6,000 / OpenRouter (Llama / Qwen / DeepSeek / Mistral / Gemini) 12,000.

## Schema

Per-row fields (all splits):

| Field | Type | Notes |
|---|---|---|
| `row_id` | str | UUID for joining/citation |
| `phase` | str | `phase_1a` / `phase_1b` / `phase_2_v2` / `phase_3_5_swebench` |
| `vendor` | str | `anthropic` / `openai` / `openrouter` |
| `model` | str | e.g., `claude-sonnet-4-5`, `gpt-5.4`, `llama-3.1-70b` |
| `temperature` | float | `0.0` / `0.5` / `1.0` |
| `query_id` | str | e.g., `heldout::heldout_quantum_nebula_catalog_00::busiest_window::365` |
| `query_type` | str | `busiest_window`, `deepest_chain`, etc. |
| `kb_id` | str | held-out KB identifier |
| `prompt` | str | full prompt text (system + user, synthetic queries) |
| `prompt_hash` | str | `sha256:<hex>` of NFC-utf8 prompt |
| `response_hash` | str | `sha256:<hex>` of NFC(rationale) + sentinel + NFC(final_answer_raw) |
| `tool_calls_hash` | str | `sha256:<hex>` of `paper4_replay_determinism::_seq_full(sequence)` |
| `final_answer_hash` | str | `sha256:<hex>` of NFC-utf8 normalized final answer |
| `run_idx` | int | independent-run index `0..N-1` for the cell |
| `n_tool_calls` | int | observed tool-call count |
| `error_category` | str \| null | `null` on success, else e.g. `turn_limit`, `refusal_no_tool_no_text` |
| `latency_s` | float \| null | wall-clock latency |
| `in_tokens` / `out_tokens` | int \| null | usage when reported by the API |

Phase 3.5 rows additionally include `task_id` (e.g., `django__django-12453`).

## Hash specification

`tool_calls_hash` is computed exactly as in `paper4_replay_determinism.py::_seq_full`:

```python
parts = []
for s in sequence:
    args = s.get("args") or {}
    parts.append(s["name"] + ":" + json.dumps(args, sort_keys=True, default=str))
joined = "||".join(parts)
hash = "sha256:" + sha256(joined.encode("utf-8")).hexdigest()
```

`prompt_hash` and `final_answer_hash` use `chain_receipt_core.compute_text_hash` (NFC + utf-8 + sha256). Reference implementations: [`chain_receipt_core` (Python)](https://pypi.org/project/chain-receipt-core/) and [`@cruxia/chain-receipt-core` (TypeScript)](https://www.npmjs.com/package/@cruxia/chain-receipt-core).

## Replication

```bash
pip install chain-receipt-sdk
chain-receipt replay sha256:<prompt_hash> --n 10
```

Or, to reproduce the chain-divergence rates from the paper:

```python
from datasets import load_dataset
ds = load_dataset("cruxia/chain-determinism-bench-v1", "phase_1a")["train"]

# Group runs by (model, temperature, query_id) and check tool_calls_hash agreement
from collections import defaultdict
cells = defaultdict(list)
for row in ds:
    key = (row["model"], row["temperature"], row["query_id"])
    cells[key].append(row["tool_calls_hash"])

# Chain-divergence rate per model = fraction of cells with >1 unique hash
import statistics
by_model = defaultdict(list)
for (model, temp, qid), hashes in cells.items():
    by_model[model].append(int(len(set(hashes)) > 1))
for model, divs in sorted(by_model.items()):
    print(f"{model:25s}  divergence={statistics.mean(divs):.1%}  (n={len(divs)})")
```

## Citation

```bibtex
@unpublished{ausili2026chaindivergence,
  title  = {Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe for Replay-Attestable LLM Agents},
  author = {Ausili, Mars},
  year   = {2026},
  note   = {Under peer review. See https://chain-determinism.org/paper for current status.}
}
```

## License

[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). Cite the paper if you use this data.

## Maintainer

Mars Ausili — `mars@cruxia.ai`. Issues: open a discussion on this dataset page.
