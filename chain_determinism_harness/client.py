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
from typing import Optional

from openai import AsyncOpenAI


def _resolve_api_key(model: str, explicit: Optional[str] = None) -> str:
    if explicit:
        return explicit
    # Try in order:
    if "openrouter" in (os.environ.get("CHAIN_DET_BASE_URL", "")).lower():
        return os.environ.get("OPENROUTER_API_KEY", "")
    for env in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        if os.environ.get(env):
            return os.environ[env]
    return ""


def _resolve_base_url(model: str, explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    # Default to OpenRouter if OPENROUTER_API_KEY is set and OpenAI key isn't
    if os.environ.get("OPENROUTER_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        return "https://openrouter.ai/api/v1"
    if "/" in model and not model.startswith("gpt-"):
        # heuristic: model like "qwen/qwen-2.5-72b-instruct" → OpenRouter
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
    """Run one agent replay; collect tool-call sequence + final answer."""
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    tool_call_sequence: list[dict] = []
    final_answer: Optional[str] = None
    error_category: Optional[str] = None
    rationale_chunks: list[str] = []

    for _ in range(max_tool_calls + 4):
        try:
            resp = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                tool_choice="auto",
            )
        except Exception as e:
            error_category = f"api_error: {type(e).__name__}: {str(e)[:160]}"
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

        # Process each tool call
        terminal = False
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_call_sequence.append({
                "name": tc.function.name,
                "args": args,
                "tool_call_id": tc.id,
            })

            if tc.function.name == "final_answer":
                final_answer = args.get("answer", "")
                terminal = True
                break

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
    """Run N replays of a single query, collecting tool-call sequences."""
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

    return await asyncio.gather(*[one(i) for i in range(n_replays)])


def make_client(base_url: Optional[str] = None, api_key: Optional[str] = None,
                timeout: float = 60.0) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=_resolve_api_key("", api_key),
        base_url=_resolve_base_url("", base_url),
        timeout=timeout,
    )
