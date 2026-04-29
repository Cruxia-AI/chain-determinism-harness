"""Embedded held-out OOD queries for chain-determinism measurement.

A 10-query subset of the Sigma-registry held-out OOD benchmark used in the
companion paper. Selected to span 4 query types (depth-1 / depth-2 / depth-3 /
depth-4 reference chains) for query-difficulty diversity. Subset published
under CC-BY-4.0 along with the chain-determinism-bench-v1 dataset.

The full 40-query held-out set is at::

    https://github.com/Cruxia-AI/chain-determinism-harness/tree/main/bench
        (data/phase_1a.jsonl, query_id field for the seeded subset)
"""

QUERIES = [
    {
        "query_id": "heldout::heldout_xenobiology_taxonomy_00::author_productivity::endolithic_autotroph_order",
        "kb_id": "heldout_xenobiology_taxonomy_00",
        "target_term": "endolithic_autotroph_order",
        "query_type": "author_productivity",
        "question": "Of all non-retracted source entries for term 'endolithic_autotroph_order', which author contributed the most entries? Answer with a single author name.",
    },
    {
        "query_id": "heldout::heldout_xenobiology_taxonomy_00::busiest_window::psychrotolerant_genus_revision",
        "kb_id": "heldout_xenobiology_taxonomy_00",
        "target_term": "psychrotolerant_genus_revision",
        "query_type": "busiest_window",
        "question": "What 30-day window has the most non-retracted source entries about term 'psychrotolerant_genus_revision'? Answer with the start date in YYYY-MM-DD format.",
    },
    {
        "query_id": "heldout::heldout_xenobiology_taxonomy_00::deepest_chain::thermoacidophile_kingdom_placement",
        "kb_id": "heldout_xenobiology_taxonomy_00",
        "target_term": "thermoacidophile_kingdom_placement",
        "query_type": "deepest_chain",
        "question": "What is the longest revision chain (REVISES depth) for any source entry about term 'thermoacidophile_kingdom_placement'? Answer with an integer.",
    },
    {
        "query_id": "heldout::heldout_xenobiology_taxonomy_00::orphaned_sources::barophilic_family_reassignment",
        "kb_id": "heldout_xenobiology_taxonomy_00",
        "target_term": "barophilic_family_reassignment",
        "query_type": "orphaned_sources",
        "question": "How many source entries about term 'barophilic_family_reassignment' are non-retracted AND have no successor REVISES (i.e., are current heads)? Answer with an integer.",
    },
    {
        "query_id": "heldout::heldout_quantum_nebula_catalog_00::earliest_contributor::365",
        "kb_id": "heldout_quantum_nebula_catalog_00",
        "target_term": "365",
        "query_type": "earliest_contributor",
        "question": "Who was the first author (by timestamp) to contribute a non-retracted source entry about term '365'? Answer with a single author name.",
    },
    {
        "query_id": "heldout::heldout_quantum_nebula_catalog_00::longest_gap::nebula_42",
        "kb_id": "heldout_quantum_nebula_catalog_00",
        "target_term": "nebula_42",
        "query_type": "longest_gap",
        "question": "What is the longest gap (in days) between consecutive non-retracted source entries about term 'nebula_42'? Answer with an integer.",
    },
    {
        "query_id": "heldout::heldout_quantum_nebula_catalog_00::retract_impact::dark_matter_residual",
        "kb_id": "heldout_quantum_nebula_catalog_00",
        "target_term": "dark_matter_residual",
        "query_type": "retract_impact",
        "question": "How many source entries about term 'dark_matter_residual' have been retracted? Answer with an integer.",
    },
    {
        "query_id": "heldout::heldout_synthetic_biology_index_00::term_leaderboard::CRISPR_v2",
        "kb_id": "heldout_synthetic_biology_index_00",
        "target_term": "CRISPR_v2",
        "query_type": "term_leaderboard",
        "question": "Among non-retracted source entries about term 'CRISPR_v2', which 3 authors contributed the most entries? Answer as a comma-separated list of author names ordered by contribution descending.",
    },
    {
        "query_id": "heldout::heldout_synthetic_biology_index_00::author_productivity::ribozyme_rationale",
        "kb_id": "heldout_synthetic_biology_index_00",
        "target_term": "ribozyme_rationale",
        "query_type": "author_productivity",
        "question": "Of all non-retracted source entries for term 'ribozyme_rationale', which author contributed the most entries? Answer with a single author name.",
    },
    {
        "query_id": "heldout::heldout_synthetic_biology_index_00::deepest_chain::orthogonal_polymerase",
        "kb_id": "heldout_synthetic_biology_index_00",
        "target_term": "orthogonal_polymerase",
        "query_type": "deepest_chain",
        "question": "What is the longest revision chain (REVISES depth) for any source entry about term 'orthogonal_polymerase'? Answer with an integer.",
    },
]


def kb_summary_to_prompt(q: dict) -> str:
    """Build the KB summary prefix sent to the model.

    The model receives the kb_id and target_term and is told to use tool calls
    to inspect contents — same format as the paper's full benchmark.
    """
    parts = [
        f"# Knowledge base id: {q['kb_id']}",
        "(Use tool calls like `all_beliefs()` or `filter_beliefs(term=...)` "
        "to inspect contents.)",
    ]
    if q.get("target_term"):
        parts.append(f"Target term mentioned in the question: '{q['target_term']}'")
    return "\n".join(parts)
