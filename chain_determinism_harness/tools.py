"""Tool schemas for the Sigma-registry primitive registry.

OpenAI-compatible function-calling schemas for the 21 primitives + final_answer.
Reproduced verbatim from the companion paper's measurement harness so that the
self-contained chain-determinism-harness produces hashes byte-identical to the
chain-determinism-bench-v1 dataset.
"""

SYSTEM_PROMPT = (
    "You are a precise analyst answering questions about a structured knowledge "
    "graph of source entries (each with source_id, term, definition, timestamp, "
    "author, optional `revises` predecessor).\n\n"
    "You have access to 21 primitive tool functions that operate on the knowledge "
    "graph. To answer a question:\n"
    "1. Compose primitives by passing the variable name of a previous step's result "
    "(e.g., \"v1\") as the `in` argument of a later primitive.\n"
    "2. Each tool result will be returned to you with a step variable name "
    "(v1, v2, ...).\n"
    "3. After at most 10 tool calls, you MUST invoke `final_answer(answer=\"...\")` "
    "with a concise final answer.\n\n"
    "The graders are deterministic and exact-match: emit exact source_ids, integer "
    "counts, or yes/no when relevant. Avoid prose explanations in the final answer; "
    "just give the value(s).\n\n"
    "Compose primitives carefully — do NOT try to read the KB and answer directly. "
    "Use tool calls to compute the answer."
)


def _fn(name, description, parameters):
    return {"type": "function", "function": {
        "name": name, "description": description, "parameters": parameters,
    }}


def _obj(props, required=None, additional=False):
    p = {"type": "object", "additionalProperties": additional, "properties": props}
    if required:
        p["required"] = required
    return p


_REF = {"type": "string", "description": "ref to a prior step var, e.g. 'v1'"}
_ATTR_ENUM = ["source_id", "term", "author", "timestamp", "claim_text"]


TOOL_SCHEMAS_OPENAI = [
    _fn("all_beliefs", "Return all non-retracted beliefs in the knowledge graph as a list.",
        _obj({})),
    _fn("filter_beliefs",
        "Return all non-retracted beliefs whose `term` field matches the given string.",
        _obj({"term": {"type": "string"}}, ["term"])),
    _fn("filter_not_retracted",
        "Filter a previous belief list to only non-retracted beliefs.",
        _obj({"in": _REF}, ["in"])),
    _fn("filter_author",
        "Filter a belief list to those by a given author.",
        _obj({"in": _REF, "author": {"type": "string"}}, ["in", "author"])),
    _fn("filter_by_term_subset",
        "Filter a belief list to those whose term is in the given subset.",
        _obj({"in": _REF, "terms": {"type": "array", "items": {"type": "string"}}},
             ["in", "terms"])),
    _fn("filter_orphans",
        "Of a belief list, keep only beliefs that are NOT superseded by any REVISES edge.",
        _obj({"in": _REF}, ["in"])),
    _fn("project",
        "Project a belief list onto a single attribute. attr is one of: source_id, term, author, timestamp, claim_text.",
        _obj({"in": _REF,
              "attr": {"type": "string", "enum": _ATTR_ENUM}},
             ["in", "attr"])),
    _fn("group_by_count",
        "Group a belief list by an attribute and count occurrences. Returns dict value -> count.",
        _obj({"in": _REF,
              "key": {"type": "string", "enum": ["source_id", "term", "author", "timestamp"]}},
             ["in", "key"])),
    _fn("sort_by",
        "Sort a belief list by attribute. Default key=timestamp ascending.",
        _obj({"in": _REF, "key": {"type": "string", "default": "timestamp"},
              "desc": {"type": "boolean", "default": False}}, ["in"])),
    _fn("count", "Return the integer length / count of a list or dict.",
        _obj({"in": _REF}, ["in"])),
    _fn("max_value", "Return the maximum value (over a list of numbers or values of a dict).",
        _obj({"in": _REF}, ["in"])),
    _fn("argmax_by_value",
        "Given a dict (e.g., from group_by_count), return the key with the highest value.",
        _obj({"in": _REF}, ["in"])),
    _fn("argmin_by_timestamp",
        "Of a non-empty belief list, return an attribute (default: source_id) of the earliest one.",
        _obj({"in": _REF,
              "return": {"type": "string", "default": "source_id", "enum": _ATTR_ENUM}},
             ["in"])),
    _fn("pairwise_gaps_days",
        "Given a sorted-by-timestamp belief list, return list of integer day-gaps between consecutive entries.",
        _obj({"in": _REF}, ["in"])),
    _fn("rolling_window_max",
        "Return the max count of beliefs in any rolling `days`-day window (default 90).",
        _obj({"in": _REF, "days": {"type": "integer", "default": 90}}, ["in"])),
    _fn("provenance_depth",
        "Return the integer length of the REVISES chain rooted at source_id.",
        _obj({"source_id": {"type": "string"}}, ["source_id"])),
    _fn("retract_impact",
        "For a source_id, return the count of belief states it would invalidate if retracted.",
        _obj({"source_id": {"type": "string"}}, ["source_id"])),
    _fn("take", "Take the first n elements of a list.",
        _obj({"in": _REF, "n": {"type": "integer"}}, ["in", "n"])),
    _fn("take_at", "Return the i-th element (0-indexed) of a list.",
        _obj({"in": _REF, "i": {"type": "integer"}}, ["in", "i"])),
    _fn("pairwise_diff_attr",
        "Return the list of pairwise differences in a numeric attribute across consecutive entries.",
        _obj({"in": _REF, "attr": {"type": "string"}}, ["in", "attr"])),
    _fn("has_any_pairwise_diff",
        "Return true if any consecutive pair of entries differs in `attr`.",
        _obj({"in": _REF, "attr": {"type": "string"}}, ["in", "attr"])),
    _fn("final_answer",
        "Submit the final answer as a string. Call this exactly once at end.",
        _obj({"answer": {"type": "string"}}, ["answer"])),
]


def stub_tool_response(name: str) -> str:
    """Return a generic stub tool response.

    The harness measures *chain-divergence under non-informative feedback* — the
    agent receives a deterministic stub response for every non-`final_answer`
    tool call. This isolates exploration-strategy non-determinism (the agent
    deciding which tool to call next) from data-path non-determinism (which
    requires a live KG and is the regime measured by Phase 1a in the paper).

    Same scope as the paper's §3.5 SWE-bench Lite stub-environment preliminary.
    """
    if name == "count":
        return '{"kind": "int", "value": 5}'
    if name == "all_beliefs" or name == "filter_beliefs":
        return '{"kind": "beliefs", "len": 5, "sample": ["b1", "b2", "b3"]}'
    if name == "argmax_by_value" or name == "argmin_by_timestamp":
        return '{"kind": "string", "value": "alice"}'
    if name == "group_by_count":
        return '{"kind": "dict", "items": {"alice": 3, "bob": 2}}'
    if name == "max_value":
        return '{"kind": "int", "value": 30}'
    if name == "rolling_window_max":
        return '{"kind": "int", "value": 4}'
    if name == "provenance_depth":
        return '{"kind": "int", "value": 2}'
    if name == "retract_impact":
        return '{"kind": "int", "value": 1}'
    if name == "pairwise_gaps_days":
        return '{"kind": "list", "values": [3, 7, 14, 30]}'
    return '{"kind": "list", "len": 4, "sample": ["item1", "item2"]}'
