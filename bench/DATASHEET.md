# Datasheet for *Chain-Determinism Bench v1*

Following the Datasheet for Datasets template (Gebru et al. 2018, *Communications of the ACM* 64.12 (2021): 86-92). Each section answers the questions specified by the template.

**Dataset:** `chain-determinism-bench-v1`
**Version:** 0.1.0
**Date:** 2026-04-27
**Maintainer:** Mars Ausili, Cruxia-AI (`mars@cruxia.ai`)
**Companion paper:** *Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe for Replay-Attestable LLM Agents* (Ausili 2026, under peer review). See <https://chain-determinism.org/paper> for current status.

---

## 1. Motivation

**For what purpose was the dataset created?**
To enable measurement, replication, and audit of *chain-determinism* — the property that repeated runs of an LLM agent loop on the same input under the same vendor configuration produce identical sequences of tool calls. The dataset supports cross-vendor reproducibility studies, mechanism-attribution analyses, and regulatory replay-attestation work (EU AI Act Art. 86).

**Who created the dataset and on behalf of which entity?**
Mars Ausili, Cruxia-AI. Independent research project; not commissioned.

**Who funded the creation of the dataset?**
Self-funded research. Vendor API costs (~$500–600 in Anthropic, OpenAI, OpenRouter calls) and Modal GPU compute (~$200–300 in A100-80GB:2 hours) were paid by the creator.

**Any other comments?**
The dataset was designed to be **content-free** — per-row hashes preserve auditability without redistributing vendor responses. This design follows the Chain-Receipt protocol's content-addressed-receipt pattern.

---

## 2. Composition

**What do the instances that comprise the dataset represent?**
Each instance is one *replayed agent run* — a single execution of one (vendor, model, temperature, query, replay-index) cell — captured as the prompt text plus SHA-256 hashes of the response, the tool-call sequence, and the final answer. Each row is a chain-receipt: the audit-trail unit emitted by the chain-receipt-sdk (PyPI: `chain-receipt-sdk` 0.1.0+).

**How many instances are there in total?**
31,764 hash-only rows across four splits:

| Split | Rows | Description |
|---|---|---|
| `phase_1a` | 22,000 | T=0 multi-vendor replay (11 models × 40 queries × 50 runs) |
| `phase_1b` | 8,000 | T=1.0 temperature sweep (10 models × 40 queries × 20 runs × 1 alternative T) |
| `phase_2_v2` | 1,600 | Mechanism attribution (Qwen 2.5 72B Instruct, 40 queries × 20 replays × 2 toggles) |
| `phase_3_5_swebench` | 164 | SWE-bench Lite chain-divergence subset (3 models × ~30 instances) |

**Does the dataset contain all possible instances, or is it a sample?**
A *purposive sample* of (vendor, query, replay) cells. The vendor set is the 11 frontier non-reasoning + 1 reasoning LLMs accessible via Anthropic, OpenAI, and OpenRouter direct APIs at the time of measurement (March–April 2026). The query set is a *seeded held-out OOD subset* of the 21-primitive Σ-registry (40 queries: 8 query types × 5 surface variations each, drawn by `seed=2026`); see §3 below for the population. We do not claim the sample is representative of all possible LLM agent-loop workloads — see §9 of the companion paper for explicit scope statements.

**What data does each instance consist of?**
Each instance has the following fields (see `croissant.json` for full schema):
- `row_id` (UUID), `phase`, `vendor` (`anthropic`/`openai`/`openrouter`/`modal-vllm`), `model` (e.g., `claude-sonnet-4-5`)
- `temperature`, `query_id`, `query_type`, `kb_id` (held-out KB identifier)
- `prompt` (full prompt text — synthetic, ours to publish)
- `prompt_hash`, `response_hash`, `tool_calls_hash`, `final_answer_hash` (SHA-256, content-addressed)
- `run_idx`, `n_tool_calls`, `error_category`, `latency_s`, `in_tokens`, `out_tokens`
- (Phase 2 only) `toggle` (`baseline_all_on` / `batch_invariant_proxy`)
- (Phase 3.5 only) `task_id` (SWE-bench Lite instance ID)

**Is there a label or target associated with each instance?**
There is no supervised label. Chain-divergence is a *consistency property across multiple instances* — derived by grouping rows by `(vendor, model, query_id)` and checking whether all `tool_calls_hash` values match. A rate (chain-divergence rate per cell, with Wilson 95% CIs) is reported at the (vendor × query) level rather than per-row.

**Is any information missing from individual instances?**
- **Raw vendor responses are intentionally not included** (legal/redistribution reasons; see §6).
- For Phase 1b (8,000 rows), the original evaluation script did not capture latency or token-count fields; those columns are absent from this split.
- For Phase 2 v2, raw rationales and final-answer text exist locally with the dataset creator but are not redistributed; only hashes and prompt text are released.

**Are relationships between individual instances made explicit?**
Yes. Rows can be grouped by `(model, query_id, temperature)` to form replay clusters; within each cluster, the `tool_calls_hash` agreement defines chain-determinism. The `phase_2_v2` split additionally has paired structure: each `(query_id, run_idx)` index appears under both `toggle = baseline_all_on` and `toggle = batch_invariant_proxy`, supporting paired-comparison analyses (e.g., McNemar test).

**Are there recommended data splits?**
Yes — by `phase`. The four splits correspond to four distinct experimental phases and should be analyzed separately: Phase 1a for the universal-measurement claim, Phase 1b for temperature sensitivity, Phase 2 v2 for mechanism attribution, Phase 3.5 for stub-environment SWE-bench preliminary.

**Are there any errors, sources of noise, or redundancies?**
- *OpenRouter routing variance*: Phase 1a / 1b rows for open-weights models (Llama 3.1/3.3, Qwen 2.5, DeepSeek V3.1, Mistral Large) were routed via OpenRouter, which load-balances across multiple backend serving providers. Provider routing was not pinned and contributes to chain-divergence as a confound (transparently disclosed in §3.4 of the paper).
- *Error rows*: For high-error vendors (Llama 3.1 70B at 56.1% error rate, Llama 3.3 70B at 34.5%, Mistral Large 2411 at 27.4%), error rows are included with `error_category` set; downstream chain-divergence calculation excludes them (see Phase 1a methodology in §3.2 of the paper).
- *Reasoning-model temperature*: o3 and gpt-5.4-turbo silently reject `temperature` parameters at the API; their rows in Phase 1a record the requested T=0 but the model actually ran at default ~T=1.0. We mark these explicitly in the paper §9.

**Is the dataset self-contained, or does it link to or otherwise rely on external resources?**
The hashes are byte-identical to those produced by `chain-receipt-sdk` (PyPI), which is required to *replay* a chain-receipt (re-run the prompt and verify). The dataset itself is self-contained for analysis; replay requires the SDK and vendor API keys. Vendor model snapshots may drift over time (see §9 of paper for the model-version-stability caveat).

**Does the dataset contain data that might be considered confidential?**
No. Prompts are synthetic and authored by the creator; responses are not redistributed.

**Does the dataset contain data that, if viewed directly, might be offensive, insulting, threatening, or otherwise cause anxiety?**
No. The Σ-registry queries are factual database-style questions on synthetic knowledge bases (e.g., "find the busiest contributor on a synthetic biology corpus"). No content has been flagged as sensitive.

**Does the dataset relate to people?**
No.

---

## 3. Collection process

**How was the data associated with each instance acquired?**
Each row was generated by executing one agent run via:
- Anthropic Messages API (Claude Sonnet 4.5, Claude Opus 4.6) for the Anthropic stream
- OpenAI Chat Completions API (GPT-4.1, GPT-5.4, o3) for the OpenAI stream
- OpenRouter (with default routing) for open-weights vendors (Llama 3.1 70B, Llama 3.3 70B, Qwen 2.5 72B, DeepSeek V3.1, Mistral Large 2411, Gemini 2.5 Flash)
- Modal vLLM A100-80GB:2 (Phase 2 v2 only, Qwen 2.5 72B Instruct)

Source code: `scripts/paper5_multivendor_replay.py` (Phase 1), `scripts/paper5_mechanism_modal.py` (Phase 2), `scripts/paper5_swebench_lite_chain_div.py` (Phase 3.5). Random seed `2026` is used throughout.

**What mechanisms or procedures were used to collect the data?**
Direct API calls in batched mode with `concurrency=10` for Phase 1 streams and serial single-toggle runs for Phase 2 (to ensure controlled-stack measurement). All runs at T=0 unless explicitly noted (Phase 1b T=1.0; o3/gpt-5.4 default T~1.0).

**If the dataset is a sample from a larger set, what was the sampling strategy?**
*Vendors*: convenience sample of all frontier non-reasoning LLMs accessible via the three direct APIs at measurement time. *Queries*: seeded purposive sample (`seed=2026`) of 40 queries from the 21-primitive Σ-registry held-out OOD generator (`lab/.../build_held_out_ood`), structured as 8 query types × 5 surface variations. The Σ-registry was not publicly released prior to this dataset.

**Who was involved in the data collection process?**
Mars Ausili (creator) and automated agents (in some pipeline phases). No human annotators or labelers.

**Over what timeframe was the data collected?**
Phase 1a: March 2026 (first sweep) and April 2026 (re-sweep after harness bug fix). Phase 1b: April 2026. Phase 2 v2: April 2026 (after harness bug discovered and fixed mid-month — see paper §9). Phase 3.5: April 2026.

**Were any ethical review processes conducted?**
No formal ethics review (the dataset does not relate to human subjects). The creator self-assessed for dual-use risks; see §5 below.

---

## 4. Preprocessing / cleaning / labeling

**Was any preprocessing/cleaning/labeling of the data done?**
- Tool-call sequences are hashed via the same `compute_tool_calls_hash` helper used by `chain-receipt-sdk`, ensuring byte-identical hashes between dataset rows and SDK-emitted Receipts.
- Final-answer text is normalized to NFC Unicode and lowercased before hashing.
- Error rows are kept (with `error_category` field set) but excluded from chain-divergence calculation per the paper's Phase 1a methodology.
- For Phase 2 v2: raw runs were captured at `/tmp/p2_qwen-2.5-72b_*.jsonl` during the original Modal Phase 2 run; backfilled to the public dataset on 2026-04-27 via `chain_determinism_bench/backfill_phase2.py`.

**Was the "raw" data saved in addition to the preprocessed/cleaned/labeled data?**
Raw vendor responses are retained locally with the dataset creator but not redistributed (see Composition §2). The hash-only public dataset is intentionally *not* a lossless representation of the original responses; it is content-addressed audit data.

**Is the software that was used to preprocess/clean/label the data available?**
Yes:
- `chain_determinism_bench/prepare.py` (Phase 1a, 1b, 3.5 build)
- `chain_determinism_bench/backfill_phase2.py` (Phase 2 v2 backfill)
- `chain_receipt_core` (PyPI, hash helpers)

---

## 5. Uses

**Has the dataset been used for any tasks already?**
Yes. The companion paper uses this dataset for:
- Universal-measurement claim across 9 vendors (§3 of paper)
- Architectural-family clustering with Wilson CIs and Welch ANOVA (§3.2)
- Phase 1b temperature monotonicity (§3.3)
- Phase 2 mechanism-attribution McNemar test (§4)
- SWE-bench Lite stub-environment preliminary (§3.5)

**Is there a repository that links to any or all papers or systems that use the dataset?**
The companion paper is the principal use. We will maintain a list of subsequent works at the dataset's HuggingFace page.

**What (other) tasks could the dataset be used for?**
- Chain-determinism measurement of new vendors (replication of Phase 1a methodology with `chain-receipt-sdk`)
- Cross-temperature reproducibility benchmarks (Phase 1b)
- Mechanism-attribution research on serving-stack non-determinism (Phase 2)
- Audit-trail-protocol research (using `chain-receipt-sdk` replay machinery)

**Is there anything about the composition of the dataset or the way it was collected that might impact future uses?**
- *Vendor model versions are not pinned in the dataset.* OpenAI snapshot IDs and Anthropic API versions drift; rates published here may not reproduce on later snapshots.
- *OpenRouter routing was not pinned* for open-weights vendors; rates conflate model-level and serving-infrastructure-level non-determinism.
- *Σ-registry training contamination is unverifiable*; if a frontier vendor's pretraining corpus included material similar to the registry, chain-divergence rates may be artificially low for that vendor.
- *The 40-query held-out subset is structured as 8 templates × 5 surface variations*; treat statistical analyses with effective sample size n_eff ≤ 8 on the query-template axis.

**Are there tasks for which the dataset should not be used?**
- **Vendor reputation rankings.** The chain-divergence rates published here measure trace-structural consistency under a specific synthetic benchmark; they should not be used to rank vendors on overall agent quality, factuality, helpfulness, or any other capability dimension.
- **Regulatory compliance assessment.** Chain-determinism is a *technical precondition* for replay attestation; compliance with EU AI Act, GDPR, or other regulations is a legal determination requiring qualified counsel.
- **Adversarial robustness benchmarks.** The metric rewards superficial template-locking and does not measure semantic determinism (see §9 of paper).

---

## 6. Distribution

**Will the dataset be distributed to third parties outside of the entity on behalf of which the dataset was created?**
Yes. Public release.

**How will the dataset be distributed?**
- GitHub: <https://github.com/Cruxia-AI/chain-determinism-harness/tree/main/bench>
- Croissant ML metadata: `croissant.json` in the dataset root (validated against `cr:1.0`)
- DOI: pending Zenodo submission at camera-ready

**When will the dataset be distributed?**
v0.1.0 released 2026-04-27 alongside the companion paper submission (under peer review).

**Will the dataset be distributed under a copyright or other intellectual property (IP) license?**
- *Dataset content* (prompts, hashes, schema): CC-BY-4.0 (Attribution 4.0 International). Required citation:

  ```
  @unpublished{ausili2026chaindivergence,
    title  = {Chain-Divergence: A Cross-Vendor Benchmark and Mechanism Probe for Replay-Attestable LLM Agents},
    author = {Ausili, Mars},
    year   = {2026},
    note   = {Under peer review. Companion dataset: chain-determinism-bench-v1,
              https://github.com/Cruxia-AI/chain-determinism-harness/tree/main/bench}
  }
  ```
- *Source code* (`prepare.py`, `backfill_phase2.py`): Apache-2.0.
- *Vendor responses are not included*; their hashes are derivative observations and do not carry vendor IP.

**Have any third parties imposed IP-based or other restrictions on the data associated with the instances?**
The Σ-registry queries are authored by the creator; no third-party restrictions. Vendor responses (not redistributed) remain subject to each vendor's terms of service.

**Do any export controls or other regulatory restrictions apply to the dataset or to individual instances?**
None known. The dataset is publishable internationally under CC-BY-4.0.

---

## 7. Maintenance

**Who will be supporting/hosting/maintaining the dataset?**
Mars Ausili (`mars@cruxia.ai`), Cruxia-AI. Single maintainer; no backup maintainer named at v0.1.0.

**How can the owner/curator/manager of the dataset be contacted?**
- Email: `mars@cruxia.ai`
- HuggingFace: `cruxia/chain-determinism-bench-v1` (Discussions tab)
- GitHub Issues: Cruxia personal account repository

**Is there an erratum?**
Not at v0.1.0. Errata will be tracked in `CHANGELOG.md` in the dataset root.

**Will the dataset be updated?**
Yes. Planned updates:
- v0.2: BFCL convergent-validity triangulation rows, real-Docker SWE-bench Verified Phase 2b rows, additional cross-model Phase 2 verification (Mistral, Llama).
- Subsequent versions: provider-pinned open-weights replication, longer-term deployment-drift longitudinal data.

**Will the dataset be updated to reflect changes in the underlying instances?**
No. Vendor model snapshots referenced by `model` in the rows are *as-of measurement time*; changes in vendor stacks after that time are out of scope. Each release pins a model-snapshot date in the README.

**If the dataset relates to people, are there applicable limits on the retention of the data associated with the instances?**
Not applicable; no people in the data.

**Will older versions of the dataset continue to be supported/hosted/maintained?**
Yes. v0.1.0 will remain accessible at the HuggingFace Datasets endpoint for at least 5 years. Future versions are additive (new rows, new splits) rather than replacing v0.1.0.

**If others want to extend/augment/build on/contribute to the dataset, is there a mechanism for them to do so?**
Yes. Contributions accepted via:
- HuggingFace Datasets pull requests (recommended for additional measurement rows)
- GitHub issues / pull requests on the Cruxia personal-account repo
- Email to the maintainer for new-vendor measurement contributions

We particularly welcome:
- Additional vendors not in our 11-vendor sample
- Provider-pinned open-weights replications (Together AI only, Fireworks only, etc.)
- Convergent-validity measurements on external benchmarks (BFCL, τ-bench, ToolBench)
- Real-Docker SWE-bench Verified Phase 2b runs

---

*This datasheet was prepared 2026-04-27 in response to a pre-submission audit that flagged the absence of a Gebru-template datasheet for chain-determinism-bench-v1 (the existing on-disk datasheet was for AGM-Bench / Paper 4, a different dataset). Errata, additions, and corrections will be appended as the dataset evolves.*
