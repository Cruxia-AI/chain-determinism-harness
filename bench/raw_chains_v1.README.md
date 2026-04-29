# raw_chains_v1.jsonl.gz

Companion raw-chain release for the Chain-Divergence paper. Addresses the reviewer concern that the hash-only release ties verification to the remote `chain-determinism.org/verify/{hash}` endpoint. This file lets a reviewer **locally** reconstruct §3.1 family-clustering and §5 chain-answer divergence findings without hitting any endpoint.

**Coverage:**
- 11 per-vendor exemplar queries from Phase 1a
- All replays per query (50 each, run_idx field tracks the replay index)
- Total: **550 raw tool-call sequences** with full `tool_call_sequence`, `final_answer_raw`, `rationale`, `n_tool_calls` fields

**Phase 2 v2 raw runs** (1,600 Qwen 2.5 72B + 1,600 Mistral 7B v0.3 mechanism-attribution rows): stored on Modal volume `sagrada-finetune` and accessible via the lab's Modal account. The per-query divergence indicators for §3.2 are in `chain_determinism_bench/data/phase_2_v2.jsonl` (hash-only) + `results/benchmarks/paper5/mechanism_attribution.json` (analysis aggregates with diverged-query IDs).

**Format:** JSONL, gzip-compressed. First row is a `_meta` header; subsequent rows match the `multivendor_*.jsonl` schema.

**License:** CC-BY-4.0
**SHA-256:** `e7f9d3c1f41867fbd91585bbb84f6fa5f62ff56be56420770c37dc4dc3adda1b`

**Verification one-liner:**
```bash
gunzip -c raw_chains_v1.jsonl.gz | head -1 | python3 -m json.tool   # see metadata header
gunzip -c raw_chains_v1.jsonl.gz | tail -n +2 | python3 -c "import json,sys; rows=[json.loads(l) for l in sys.stdin]; print(f'{len(rows)} runs')"
```
