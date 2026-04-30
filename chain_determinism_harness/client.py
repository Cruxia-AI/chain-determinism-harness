"""Async OpenAI-compatible client for chain-determinism replay.

Supports any endpoint exposing the OpenAI Chat Completions API:
- OpenAI direct (`https://api.openai.com/v1`)
- OpenRouter (`https://openrouter.ai/api/v1`)
- Together AI (`https://api.together.xyz/v1`)
- vLLM (`http://localhost:8000/v1` for local serving)
- Modal vLLM (your-app.modal.run/v1)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Optional

from openai import AsyncOpenAI


_SECRET_PATTERNS = [
    # OpenAI/OpenRouter-style keys: sk-, sk-proj-, sk-or-, sk-ant- (+ ≥10 trailing chars)
    (re.compile(r"sk-[A-Za-z0-9_\-]{10,}"), "sk-<REDACTED>"),
    # Bearer tokens
    (re.compile(r"(?i)(bearer)\s+[A-Za-z0-9_\-\.=]+"), r"\1 <REDACTED>"),
    # Generic Authorization header values (key=value or key: value forms)
    (re.compile(
        r"(?i)(authorization|api[_\-]?key|x-api-key)"
        r"(\s*[:=]\s*[\"\']?)([^\s\"\',<>]+)"
    ), r"\1\2<REDACTED>"),
]


def _scrub_secrets(text: str) -> str:
    """Best-effort scrub of API keys / bearer tokens from error strings before
    they enter attestation Receipts. Patterns cover OpenAI, OpenRouter, generic
    Bearer, and `authorization=`/`x-api-key=` headers.

    Reviewers should treat error_category as untrusted: this is defense-in-depth
    against credential exfiltration via Receipt logs, not a substitute for
    redacting at the logging layer.
    """
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _resolve_api_key(model: str, explicit: Optional[str] = None) -> str:
    """Pick an API key for the OpenAI-compatible endpoint.

    Provider-aware: only returns keys that match the resolved base URL's
    provider family. Explicit ANTHROPIC_API_KEY fallthrough has been removed
    (Anthropic keys are not OpenAI-compatible and routing them to OpenAI/
    OpenRouter/vLLM endpoints is a credential-leak vector).
    """
    if explicit:
        return explicit
    base_url = (os.environ.get("CHAIN_DET_BASE_URL") or "").lower()
    if "openrouter" in base_url:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise RuntimeError(
                "OpenRouter base URL detected but OPENROUTER_API_KEY is not set"
            )
        return key
    # Default OpenAI / Together / vLLM / Modal — accept OpenAI key, fall back
    # to OpenRouter (some users serve via OpenRouter without setting the env).
    # ANTHROPIC_API_KEY is intentionally NOT considered: it is incompatible
    # with OpenAI-format endpoints and forwarding it would leak the credential
    # to a non-Anthropic backend.
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "No OpenAI-compatible API key found. Set OPENAI_API_KEY (default) "
            "or OPENROUTER_API_KEY."
        )
    return key


def _resolve_base_url(model: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    if os.environ.get("CHAIN_DET_BASE_URL"):
        return os.environ["CHAIN_DET_BASE_URL"]
    # Default to OpenRouter if OPENROUTER_API_KEY is set and OpenAI key isn't
    if os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        return "https://openrouter.ai/api/v1"
    # Heuristic for openrouter-style model identifiers (e.g.
    # "qwen/qwen-2.5-72b-instruct"). Whitelist exclusions: OpenAI fine-tunes
    # ("ft:gpt-..."), `gpt-*` direct, and `o1`/`o3` reasoning models stay on
    # the OpenAI default.
    if (
        "/" in model
        and not model.startswith(("gpt-", "ft:gpt-", "o1", "o3"))
    ):
        return "https://openrouter.ai/api/v1"
    return None  # default OpenAI


async def run_one_replay(
    client: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    tools: list,
    *,
    temperature: float = 0.0,
    max_tool_calls: int = 10,
    max_tokens: int = 1024,
    stub_tool_response,
) -> dict:
    """Run one agent replay; collect tool-call sequence + final answer.

    Contract:
      - Each tool call emitted by the model is recorded in `tool_call_sequence`
        in arrival order, even if the same assistant message contains both
        regular tool calls and a final_answer call (the receipt is complete).
      - Malformed tool-call argument JSON is recorded with an explicit
        `args_malformed=True` marker; the chain-attestation receipt does NOT
        silently coerce malformed args to `{}`.
      - error_category strings are scrubbed of API keys / bearer tokens before
        return (defense-in-depth against credential leaks via Receipt logs).
      - The agent loop runs at most `max_tool_calls` *iterations* (full
        chat-completion turns); the historical "+4" magic constant is removed.
    """
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    tool_call_sequence: list[dict] = []
    final_answer: Optional[str] = None
    error_category: Optional[str] = None
    rationale_chunks: list[str] = []

    for _ in range(max_tool_calls):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                tool_choice="auto",
            )
        except Exception as e:  # noqa: BLE001 — exception class varies by provider
            error_category = _scrub_secrets(
                f"api_error: {type(e).__name__}: {str(e)[:160]}"
            )
            break

        # Defensive: providers can return empty `choices` on rate-limit or
        # content-policy hits; surface as a clean error rather than IndexError.
        if not getattr(resp, "choices", None):
            error_category = "empty_choices"
            break

        msg = resp.choices[0].message
        if msg.content:
            rationale_chunks.append(msg.content)

        if not msg.tool_calls:
            # Model emitted text without tool call — record as last-turn rationale
            break

        # Append assistant message (with tool_calls) to history
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [{
                "id": tc.id, "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            } for tc in msg.tool_calls],
        })

        # Process each tool call. We record EVERY tool call into the receipt
        # in arrival order (including those after a final_answer in the same
        # turn) so the attestation is complete. Termination is deferred until
        # after the per-message loop completes.
        terminal = False
        for tc in msg.tool_calls:
            args_malformed = False
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
                if not isinstance(args, dict):
                    # OpenAI tool-call args must be a JSON object; non-object
                    # is itself an attestation-relevant anomaly.
                    args_malformed = True
                    args = {"_raw_value_repr": repr(args)[:120]}
            except json.JSONDecodeError:
                args_malformed = True
                args = {"_raw_arguments_len": len(raw_args), "_raw_arguments_head": raw_args[:80]}

            entry: dict = {
                "name": tc.function.name,
                "args": args,
                "tool_call_id": tc.id,
            }
            if args_malformed:
                # Surfaced explicitly so a hostile/buggy model cannot erase
                # argument evidence by emitting malformed JSON. Receipts
                # MUST flag this rather than silently coerce to `{}`.
                entry["args_malformed"] = True
            tool_call_sequence.append(entry)

            if tc.function.name == "final_answer":
                final_answer = args.get("answer", "") if not args_malformed else ""
                terminal = True
                # Continue iterating: any further tool calls in this same
                # message must still be recorded in the receipt for
                # completeness. We break out of the OUTER loop after the
                # inner one finishes.
                continue

            # Stub response (non-final-answer)
            stub = stub_tool_response(tc.function.name)
            messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": stub,
            })

        if terminal:
            break

    return {
        "tool_call_sequence": tool_call_sequence,
        "final_answer": final_answer,
        "rationale": "\n".join(rationale_chunks),
        "n_tool_calls": len(tool_call_sequence),
        "error_category": error_category,
    }


async def run_query(
    client: AsyncOpenAI,
    model: str,
    query: dict,
    *,
    n_replays: int,
    temperature: float,
    system_prompt: str,
    tools: list,
    stub_tool_response,
    concurrency: int = 5,
) -> list[dict]:
    """Run N replays of a single query, collecting tool-call sequences.

    Uses `asyncio.gather(..., return_exceptions=True)` so a single replay's
    failure does not cancel the entire batch; failed replays are recorded
    with an explicit `error_category` field per the run_one_replay contract.
    """
    from .queries import kb_summary_to_prompt
    user = (
        f"{kb_summary_to_prompt(query)}\n\n"
        f"Question: {query['question']}\n\n"
        f"Use the primitive tools to compute the answer; then call final_answer "
        f"with just the value."
    )

    sem = asyncio.Semaphore(concurrency)

    async def one(idx: int):
        async with sem:
            r = await run_one_replay(
                client, model, system_prompt, user, tools,
                temperature=temperature,
                stub_tool_response=stub_tool_response,
            )
            r["query_id"] = query["query_id"]
            r["query_type"] = query["query_type"]
            r["run_idx"] = idx
            return r

    results = await asyncio.gather(
        *[one(i) for i in range(n_replays)],
        return_exceptions=True,
    )
    # Convert any exception placeholders into structured error rows so that
    # downstream metrics see a consistent dict shape (n_tool_calls=0,
    # error_category set) instead of an Exception object.
    cleaned: list[dict] = []
    for i, r in enumerate(results):
        if isinstance(r, BaseException):
            cleaned.append({
                "query_id": query["query_id"],
                "query_type": query["query_type"],
                "run_idx": i,
                "tool_call_sequence": [],
                "final_answer": None,
                "rationale": "",
                "n_tool_calls": 0,
                "error_category": _scrub_secrets(
                    f"replay_exception: {type(r).__name__}: {str(r)[:160]}"
                ),
            })
        else:
            cleaned.append(r)
    return cleaned


def make_client(base_url: Optional[str] = None, api_key: Optional[str] = None,
                timeout: float = 60.0) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=_resolve_api_key("", api_key),
        base_url=_resolve_base_url("", base_url),
        timeout=timeout,
    )
