# chain-determinism-harness

[![License: MIT (code)](https://img.shields.io/badge/license-MIT%20%28code%29-blue.svg)](./LICENSE-CODE)
[![License: CC-BY-4.0 (data)](https://img.shields.io/badge/license-CC--BY--4.0%20%28data%29-orange.svg)](./LICENSE-DATA)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://www.python.org/downloads/)
[![Standard: Chain-Determinism](https://img.shields.io/badge/standard-chain--determinism-blueviolet.svg)](https://chain-determinism.org)
[![Verifier: live](https://img.shields.io/badge/verifier-live-success.svg)](https://chain-determinism.org/verify)

Reference reproducibility package for the **Chain-Determinism Standard**.

> **Chain-divergence** is the fraction of replay-pairs that produce non-byte-identical tool-call sequences for the same query under fixed configuration. Most production LLM agents are chain-divergent at temperature zero. This package lets you measure that — for any OpenAI-compatible endpoint — in under five minutes.

This repository accompanies *Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe for Replay-Attestable LLM Agents* (under peer review, 2026). It contains:

1. **`chain_determinism_harness/`** — a lightweight Python harness that measures chain-divergence on any OpenAI-compatible LLM endpoint in under five minutes. Same operationalization as the paper's §3.1 cross-vendor measurement; hashes are byte-identical to the released dataset.
2. **`bench/`** — the released `chain-determinism-bench-v1` dataset: full per-replay raw chains for the 22,000 Phase 1a runs across nine non-reasoning vendors plus o3 and Gemini 2.5 Flash, with Croissant 1.0 metadata and a Datasheet for Datasets.

Companion artifacts:

- Paper landing page — <https://chain-determinism.org/paper>
- Public verifier endpoint — <https://chain-determinism.org/verify/{receipt_hash}>
- Receipt SDK on PyPI — <https://pypi.org/project/chain-receipt-sdk/>

## Install the harness

The harness ships from source today (PyPI publication forthcoming):

```bash
pip install git+https://github.com/Cruxia-AI/chain-determinism-harness.git
```

Or clone and install editable for the dataset reproduce-path below:

```bash
git clone https://github.com/Cruxia-AI/chain-determinism-harness.git
cd chain-determinism-harness
pip install -e .
```

## Quickstart (about five minutes, under two dollars in API spend)

```bash
export OPENROUTER_API_KEY=sk-or-...        # or OPENAI_API_KEY=sk-...

python -m chain_determinism_harness eval \
    --model qwen/qwen-2.5-72b-instruct \
    --n-queries 5 --n-replays 10
```

Sample output:

```
Chain-divergence rate for qwen/qwen-2.5-72b-instruct:
  60.0%  [Wilson 95% CI 23.1%, 88.2%]

  Diverged queries:    3 / 5
  Total replays:       50
  Error replays:       0
```

See [`README_HARNESS.md`](./README_HARNESS.md) for the full harness usage notes, scope statement, and supported endpoints.

## Reproduce the paper's §3.1 cross-vendor table

The released dataset under `bench/raw_chains_v72/` contains complete tool-call sequences for every Phase 1a run. Each per-vendor file (`phase1a_full_<model>.jsonl.gz`) holds 2,000 rows (40 queries × 50 replays). Total: 22,000 rows across 11 vendor cells.

Each row carries `tool_call_sequence`, `final_answer_norm`, `rationale`, `n_tool_calls`, latency, and error category. Re-hashing `tool_call_sequence` via the SCHEMA §3.1 algorithm (see `chain_determinism_harness/metrics.py::seq_full`) reproduces the §3.1 vendor table directly from the JSONL — no remote dependency required.

```bash
git clone https://github.com/Cruxia-AI/chain-determinism-harness.git
cd chain-determinism-harness
pip install -e .

python -c "
from pathlib import Path
import gzip, json
from chain_determinism_harness.metrics import seq_full

for fp in sorted(Path('bench/raw_chains_v72').glob('phase1a_full_*.jsonl.gz')):
    rows = [json.loads(l) for l in gzip.open(fp, 'rt')]
    by_q = {}
    for r in rows:
        by_q.setdefault(r['query_id'], set()).add(seq_full(r['tool_call_sequence']))
    diverged = sum(1 for s in by_q.values() if len(s) > 1)
    print(f'{fp.stem.split(chr(95))[-1]}: {diverged}/{len(by_q)} queries diverged')
"
```

## Structure

```
chain_determinism_harness/   # Python package (MIT)
├── __init__.py
├── client.py                # OpenAI-compatible endpoint adapter
├── tools.py                 # Σ-registry stub tool-call schema
├── queries.py               # 10 embedded queries (paper-cited)
├── metrics.py               # seq_full hash, Wilson CI, divergence aggregates
├── cli.py                   # `python -m chain_determinism_harness ...`
├── __main__.py
└── ...

tests/                       # pytest unit tests for metrics + tools
pyproject.toml               # package metadata

bench/                       # Released dataset (CC-BY-4.0)
├── README.md                # Dataset overview
├── DATASHEET.md             # Datasheet for Datasets
├── croissant.json           # Croissant 1.0 metadata
├── raw_chains_v1.*          # Earlier hash-only release (preserved for backwards compatibility)
└── raw_chains_v72/          # Full per-replay raw chains for all 22,000 Phase 1a runs
    ├── INDEX.json
    └── phase1a_full_<model>.jsonl.gz   (11 files, ~50KB each)
```

## License

This repository is dual-licensed:

- **Code** (`chain_determinism_harness/`, `tests/`, `pyproject.toml`, top-level scripts) — MIT, see [`LICENSE-CODE`](./LICENSE-CODE).
- **Data** (`bench/`) — CC-BY-4.0, see [`LICENSE-DATA`](./LICENSE-DATA).

If you use this work, please cite:

```bibtex
@unpublished{ausili2026chaindivergence,
  title  = {Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe
            for Replay-Attestable LLM Agents},
  author = {Ausili, Mars},
  year   = {2026},
  note   = {Under peer review. See https://chain-determinism.org/paper for current status.}
}
```

## Status

Under peer review (2026). Issues and pull requests welcome at <https://github.com/Cruxia-AI/chain-determinism-harness/issues>.

## About

Maintained by [Cruxia AI](https://chain-determinism.org). Author: Mars Ausili (<mars@cruxia.ai>).
