# Maintenance Plan — chain-determinism artifact bundle

**Purpose:** Document the maintenance commitments for the Paper 5 artifact bundle (`chain-determinism-bench-v1`, `chain-determinism-harness`, `chain-receipt-sdk`, `chain-receipt-core`, `chain-receipt-browser`, `chain-determinism.org` verifier endpoint). Required by NeurIPS ED Track 2026 datasheet expectations and addresses the "maintenance plan vague" reviewer critique surfaced during murder-board iteration.

## Maintainer

**Owner:** Mars Ausili (Cruxia-AI / solo unaffiliated researcher)
**Contact:** mars@cruxia.ai
**GitHub:** github.com/Cruxia-AI (current host until full org restoration)

## Repository structure

| Repo / Package | URL | Purpose | License |
|---|---|---|---|
| Paper source + Lean theorems | `github.com/.../sagrada-engine` (`formal/lean/Sagrada/`) | Reproducible build of Lean axiom inventory | MIT |
| Reference harness | `github.com/.../chain-determinism-harness` | Measurement protocol implementation | MIT |
| Receipt SDK | `pip install chain-receipt-sdk` | LangChain-compatible Receipt emission | MIT |
| Receipt schema + Core | `pip install chain-receipt-core` (Python+TS) | Schema validation, hash chain, signature verification | MIT |
| Browser extension | `github.com/.../chain-receipt-browser` (MV3) | Live Receipt emission on Claude.ai/ChatGPT | MIT |
| Cloudflare verifier | `chain-determinism.org/verify/{hash}` | Public receipt resolution endpoint | Free, rate-limited |
| Benchmark dataset | `huggingface.co/datasets/cruxia/chain-determinism-bench-v1` | 31,764 hash-only Receipts | CC-BY-4.0 |

## Versioning + DOI

**Versioning:** Semantic versioning (`MAJOR.MINOR.PATCH`).
- `MAJOR` bump for any backwards-incompatible Receipt schema change
- `MINOR` bump for new vendor support, new Receipt fields (additive)
- `PATCH` bump for bug fixes and documentation updates

**DOI:** Each tagged release on GitHub auto-archives to Zenodo with a stable DOI.
- Initial release: `10.5281/zenodo.XXXXXXX` (placeholder; real DOI assigned at submission)
- DOI listed in dataset Croissant metadata (`chain_determinism_bench/croissant.json`)

**CHANGELOG:** Maintained at `CHANGELOG.md` in each repository root, following [Keep a Changelog](https://keepachangelog.com/) format.

## Uptime + sunset commitments

- **Verifier endpoint** (`chain-determinism.org/verify/{hash}`): Cloudflare Workers + KV; budget covered for **24 months minimum** from initial release. Free-tier sufficient at projected query volumes.
- **HuggingFace dataset**: HuggingFace's persistent storage; dataset will remain available indefinitely modulo HuggingFace policy.
- **PyPI packages**: published packages remain available indefinitely modulo PyPI policy. New versions released as bug fixes / vendor support warrants.
- **GitHub repositories**: maintainer commits to responding to issues within 14 days for the **first 12 months** post-publication; community PRs welcomed; longer-term maintenance as time permits.

**Sunset policy:** If maintenance becomes infeasible, the maintainer will:
1. Post a deprecation notice ≥3 months in advance
2. Tag the final stable release
3. Archive all data + receipts to a permanent academic-archive (Internet Archive, Zenodo) with public access
4. Document an alternative verifier path (e.g., `cruxia.github.io/chain-determinism-verifier/` static fallback)

## Errata + correction process

If errors are discovered post-publication:
1. Open a GitHub issue tagged `errata`
2. Maintainer triages and confirms within 14 days
3. Errata is documented in `ERRATA.md` of the affected repository with date, severity, and fix description
4. If errata affects a paper-cited claim, an `arxiv` revision is queued at the next scheduled update (≤90 days)
5. Major errata (claim-invalidating) prompts immediate notification to the venue and an `arxiv` revision

## Data integrity

All released Receipts are content-addressed via SHA-256 hash. Tampering is detectable by anyone running `chain-receipt verify <hash>` against the public verifier endpoint or against a local copy. Periodic Merkle anchoring of the Receipt corpus to a public Git log provides additional tamper-evidence; a Merkle root snapshot is published in each tagged release.

## Reviewer access

For NeurIPS ED Track 2026 review:
- All packages installable via standard `pip install` from PyPI
- Verifier endpoint accessible without authentication
- Quickstart in Appendix G of the paper completes in <2 minutes on a clean Python 3.10+ environment
- Reviewer questions: open a GitHub issue or contact the maintainer directly

## Known limitations + roadmap

See `ROADMAP.md` (in each repo) for planned future work, including:
- BFCL / τ-bench / AgentBench convergent-validity replications
- 70B-class non-Qwen model mechanism replication
- Provider-pinned cross-stack controls
- Quantitative T-CD-NC bound (channel-valued Lean lift)
- Genuine batch-invariant kernel test (port of He 2025 batch-invariant-ops to Modal vLLM)
