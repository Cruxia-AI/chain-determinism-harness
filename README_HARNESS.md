# chain-determinism-harness

**Measure chain-determinism for any OpenAI-compatible LLM endpoint in under 5 minutes for under $2.**

Companion harness for the *Chain-Divergence* paper (Ausili 2026, under peer review) and the [`chain-determinism-bench-v1`](https://github.com/Cruxia-AI/chain-determinism-harness/tree/main/bench) dataset.

Chain-determinism = the property that **N replays of the same query against the same vendor at T=0 produce identical tool-call sequences**. Across 9 frontier vendors at T=0 the paper finds chain-divergence rates from 17.5% (Anthropic Claude Sonnet 4.5) to 97.1% (Mistral Large 2411). This harness lets you measure your own.

## Install

```bash
pip install chain-determinism-harness
```

## Quickstart (5 minutes, ~$0.50–$2)

```bash
export OPENROUTER_API_KEY=sk-or-...        # or OPENAI_API_KEY=sk-...

python -m chain_determinism_harness eval \
    --model qwen/qwen-2.5-72b-instruct \
    --n-queries 5 --n-replays 10
```

Sample output:

```
==> chain-determinism-harness eval
    model:       qwen/qwen-2.5-72b-instruct
    queries:     5  (out of 10 embedded)
    replays:     10 per query
    total calls: 50
    ...

  [1/5] heldout::heldout_xenobiology_taxonomy_00::author_productivity::endolithic_autotroph_order
      ok=10/10  unique_sequences=4

  ...

Chain-divergence rate for qwen/qwen-2.5-72b-instruct:
  60.0%  [Wilson 95% CI 23.1%, 88.2%]

  Diverged queries:    3 / 5
  Total replays:       50
  Error replays:       0
```

## What it measures

For each (query, vendor) cell, the harness runs *N* replays of the same prompt. The agent makes tool calls (against a stub Σ-registry of 21 primitives — same registry the paper measures); the harness records the **tool-call sequence** for each replay; chain-divergence is `True` for that query if the sequences are not byte-identical across all *N* replays. Wilson 95% CIs at the per-query level.

**Same operationalization as the paper**: hashes are byte-identical to those in the `chain-determinism-bench-v1` dataset (see `chain_determinism_harness/metrics.py::seq_full`).

## Stub-environment scope

This harness uses **stub tool responses** — every non-`final_answer` tool call returns a canned response (matching the paper's §3.5 SWE-bench Lite scope). This isolates *exploration-strategy non-determinism* from *data-path non-determinism*. The full Phase 1a methodology in the paper (where tool calls are executed against a real Σ-registry KG) is implemented at `scripts/paper5_multivendor_replay.py` in the companion repository; this harness is the lighter-weight self-contained alternative for spot-checking new vendors.

The two scopes are not equivalent. Stub-environment chain-divergence will typically be **higher** than full-execution chain-divergence (the agent gets less semantically informative feedback; exploration strategies vary more across replays). Treat the harness as a **necessary condition test**: if a vendor passes under stub conditions, it likely passes under full execution; if a vendor fails under stub conditions, full execution may yet improve it.

## Endpoints supported

Anything OpenAI-compatible:

| Provider | Setup |
|---|---|
| OpenAI direct | `OPENAI_API_KEY=sk-...` |
| OpenRouter | `OPENROUTER_API_KEY=sk-or-...` (default base_url auto-detected) |
| Together AI | `--base-url https://api.together.xyz/v1` + Together API key in `OPENAI_API_KEY` |
| vLLM (local) | `--base-url http://localhost:8000/v1` |
| Modal vLLM | `--base-url https://your-app.modal.run/v1` + your Modal token |

## CLI flags

```
chain-determinism-harness eval --model X [options]

  --model MODEL              Model identifier (required)
  --n-queries N              Held-out queries to use (max 10; default 5)
  --n-replays K              Replays per query (default 10)
  --temperature T            Sampling temperature (default 0.0)
  --concurrency C            Max concurrent replays per query (default 5)
  --base-url URL             OpenAI-compatible API base URL (auto-detected if unset)
  --timeout SEC              Per-request timeout (default 60)
  --out PATH                 Write summary JSON
  --runs-out PATH            Write per-replay JSONL (downstream analysis)
```

## Cost guidance (rough)

| Configuration | Total calls | Approx. cost |
|---|---|---|
| `--n-queries 5 --n-replays 10` | 50 | $0.10–$2 (depends on vendor) |
| `--n-queries 10 --n-replays 20` | 200 | $0.50–$10 |
| `--n-queries 10 --n-replays 50` (paper's Phase 1a per-cell N) | 500 | $1–$25 |

Most frontier vendors on OpenRouter or direct API run well under a dollar for the default 5×10 = 50 calls. Mistral Large 2411 on OpenRouter (the paper's most expensive measurable vendor) is roughly $2 for 50 calls.

## Citation

If you use this harness or the companion dataset, please cite:

```
@unpublished{ausili2026chaindivergence,
  title  = {Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe
            for Replay-Attestable LLM Agents},
  author = {Ausili, Mars},
  year   = {2026},
  note   = {Under peer review. Companion harness: chain-determinism-harness;
            companion dataset: see https://github.com/Cruxia-AI/chain-determinism-harness/tree/main/bench}
}
```

## License

MIT (this harness). The companion dataset is CC-BY-4.0; vendor responses are not redistributed (hash-only).

## Caveats

- *Vendor model versions are mutable.* Today's `gpt-5.4` is not 2027's `gpt-5.4`. Pin model snapshots where the API supports it (OpenAI dated IDs; Anthropic `anthropic-version` headers).
- *OpenRouter routing variance.* OpenRouter load-balances across backend providers. Different runs may route to different providers; this is a confound for chain-divergence measurement (see paper §3.4).
- *Gameability.* Chain-divergence rewards superficial template-locking (whitespace, key ordering — already enforced by `sort_keys=True`). It is not adversarially robust as a certification metric in its present form.
