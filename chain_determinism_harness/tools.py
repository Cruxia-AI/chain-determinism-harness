"""Tool schemas for the Sigma-registry primitive registry.

OpenAI-compatible function-calling schemas for the 21 primitives + final_answer.
Reproduced from the companion paper's measurement harness so that the
self-contained chain-determinism-harness produces canonical sequence keys
matching the chain-determinism-bench-v1 dataset.

Stub-response contract (see `stub_tool_response`): every primitive has an
explicit dispatch entry. Unknown tool names raise `KeyError` rather than
silently falling back to a generic stub — the prior fallback-to-list behavior
masked schema/configuration drift and silently corrupted hashes when a typo or
new tool slipped past review. `final_answer` is intentionally NOT stubbable
(it is the chain-terminal sentinel handled by the agent loop in client.py).
"""
from __future__ import annotations

import json

SYSTEM_PROMPT = (
    "You are a precise analyst answering questions about a structured knowledge "
    "graph of source entries (each with source_id, term, claim_text, timestamp, "
    "author, optional `revises` predecessor pointing to an earlier source_id).\n\n"
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
# `claim_text` matches the canonical schema (the system prompt now uses
# claim_text consistently). Earlier text-only attributes (e.g. "definition")
# are aliases at the harness level only and not part of the public attr enum.
_ATTR_ENUM = ("source_id", "term", "author", "timestamp", "claim_text")


def _attr_enum_list():
    """Defensive copy of the attribute enum so a downstream caller cannot
    mutate the canonical schema in-place."""
    return list(_ATTR_ENUM)


def _build_tool_schemas():
    """Construct the canonical schema list. Used internally only; consumers
    should read `TOOL_SCHEMAS_OPENAI` (a tuple — immutable at the top level)."""
    return [
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
            "Project a belief list onto a single attribute. attr is one of: "
            + ", ".join(_ATTR_ENUM) + ".",
            _obj({"in": _REF,
                  "attr": {"type": "string", "enum": _attr_enum_list()}},
                 ["in", "attr"])),
        _fn("group_by_count",
            "Group a belief list by an attribute and count occurrences. Returns dict value -> count.",
            _obj({"in": _REF,
                  "key": {"type": "string",
                          "enum": ["source_id", "term", "author", "timestamp"]}},
                 ["in", "key"])),
        _fn("sort_by",
            "Sort a belief list by attribute. Default key=timestamp ascending.",
            _obj({"in": _REF,
                  "key": {"type": "string", "default": "timestamp",
                          "enum": _attr_enum_list()},
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
                  "return": {"type": "string", "default": "source_id",
                             "enum": _attr_enum_list()}},
                 ["in"])),
        _fn("pairwise_gaps_days",
            "Given a sorted-by-timestamp belief list, return list of integer day-gaps between consecutive entries.",
            _obj({"in": _REF}, ["in"])),
        _fn("rolling_window_max",
            "Return the max count of beliefs in any rolling `days`-day window (default 90).",
            _obj({"in": _REF,
                  "days": {"type": "integer", "default": 90, "minimum": 1}},
                 ["in"])),
        _fn("provenance_depth",
            "Return the integer length of the REVISES chain rooted at source_id.",
            _obj({"source_id": {"type": "string"}}, ["source_id"])),
        _fn("retract_impact",
            "For a source_id, return the count of belief states it would invalidate if retracted.",
            _obj({"source_id": {"type": "string"}}, ["source_id"])),
        _fn("take", "Take the first n elements of a list.",
            _obj({"in": _REF, "n": {"type": "integer", "minimum": 0}}, ["in", "n"])),
        _fn("take_at", "Return the i-th element (0-indexed) of a list.",
            _obj({"in": _REF, "i": {"type": "integer", "minimum": 0}}, ["in", "i"])),
        _fn("pairwise_diff_attr",
            "Return the list of pairwise differences in a numeric attribute across consecutive entries.",
            _obj({"in": _REF,
                  "attr": {"type": "string", "enum": _attr_enum_list()}},
                 ["in", "attr"])),
        _fn("has_any_pairwise_diff",
            "Return true if any consecutive pair of entries differs in `attr`.",
            _obj({"in": _REF,
                  "attr": {"type": "string", "enum": _attr_enum_list()}},
                 ["in", "attr"])),
        _fn("final_answer",
            "Submit the final answer as a string. Call this exactly once at end.",
            _obj({"answer": {"type": "string"}}, ["answer"])),
    ]


# Public name: tuple (top-level immutable). The OpenAI SDK accepts any
# iterable for `tools=`, so the public API is unchanged for the common case
# (`tools=TOOL_SCHEMAS_OPENAI`); mutation via `.append(...)` now raises
# AttributeError instead of silently corrupting the shared schema. The dicts
# within remain mutable; consumers who need a deep-copy should call
# `copy.deepcopy(TOOL_SCHEMAS_OPENAI)` themselves.
TOOL_SCHEMAS_OPENAI = tuple(_build_tool_schemas())


# ---------------------------------------------------------------------------
# Stub-response dispatch table.
#
# Contract: every primitive in TOOL_SCHEMAS_OPENAI() (except `final_answer`)
# MUST have an explicit entry. `final_answer` is intentionally absent — it is
# handled by the agent loop in client.py as the chain-terminal sentinel and
# is never stubbed. Tools whose declared return type is boolean return
# ``{"kind": "bool", "value": ...}``; tools returning ints or single values
# follow the same pattern; lists are returned with the canonical
# ``{"kind": "list", ...}`` shape. The strings are produced via
# ``json.dumps(..., sort_keys=True)`` so the canonical-JSON property holds
# byte-for-byte across Python versions and editors.
# ---------------------------------------------------------------------------

_STUB_RESPONSES_RAW: dict[str, dict] = {
    "all_beliefs":             {"kind": "beliefs", "len": 5, "sample": ["b1", "b2", "b3"]},
    "filter_beliefs":          {"kind": "beliefs", "len": 5, "sample": ["b1", "b2", "b3"]},
    "filter_not_retracted":    {"kind": "list",   "len": 5, "sample": ["b1", "b2", "b3"]},
    "filter_author":           {"kind": "list",   "len": 4, "sample": ["b1", "b2"]},
    "filter_by_term_subset":   {"kind": "list",   "len": 4, "sample": ["b1", "b2"]},
    "filter_orphans":          {"kind": "list",   "len": 3, "sample": ["b1", "b2"]},
    "project":                 {"kind": "list",   "len": 4, "sample": ["a", "b"]},
    "group_by_count":          {"kind": "dict",   "items": {"alice": 3, "bob": 2}},
    "sort_by":                 {"kind": "list",   "len": 5, "sample": ["b1", "b2"]},
    "count":                   {"kind": "int",    "value": 5},
    "max_value":               {"kind": "int",    "value": 30},
    "argmax_by_value":         {"kind": "string", "value": "alice"},
    "argmin_by_timestamp":     {"kind": "string", "value": "alice"},
    "pairwise_gaps_days":      {"kind": "list",   "values": [3, 7, 14, 30]},
    "rolling_window_max":      {"kind": "int",    "value": 4},
    "provenance_depth":        {"kind": "int",    "value": 2},
    "retract_impact":          {"kind": "int",    "value": 1},
    "take":                    {"kind": "list",   "len": 3, "sample": ["b1", "b2"]},
    "take_at":                 {"kind": "string", "value": "b1"},
    "pairwise_diff_attr":      {"kind": "list",   "values": [1, 2, 3]},
    "has_any_pairwise_diff":   {"kind": "bool",   "value": True},
    # `final_answer` is intentionally absent — see contract above.
}


def stub_tool_response(name: str) -> str:
    """Return a deterministic stub response for a primitive tool call.

    The harness measures *chain-divergence under non-informative feedback* —
    the agent receives a deterministic stub for every non-`final_answer` tool
    call. This isolates exploration-strategy non-determinism (the agent
    deciding which tool to call next) from data-path non-determinism (which
    requires a live KG and is the regime measured by Phase 1a in the paper).

    Raises:
        KeyError: if `name` is not a known primitive (or is `final_answer`,
            which is handled by the agent loop, not by stubbing).
    """
    if name == "final_answer":
        raise KeyError(
            "stub_tool_response: 'final_answer' is the chain-terminal sentinel "
            "and is not stubbable. The agent loop in client.py handles it; "
            "the harness should never reach this path with name='final_answer'."
        )
    if name not in _STUB_RESPONSES_RAW:
        raise KeyError(
            f"stub_tool_response: unknown primitive {name!r}. The chain hash "
            f"would silently change if a fallback stub were returned. "
            f"Add an entry to _STUB_RESPONSES_RAW or fix the tool name."
        )
    # json.dumps with sort_keys=True so the byte representation is stable
    # across Python versions / editors.
    return json.dumps(_STUB_RESPONSES_RAW[name], sort_keys=True, separators=(", ", ": "))
