"""chain-determinism-harness — measure trace-structural consistency across replays.

Companion harness for the *Chain-Divergence* paper (under peer review (2026)).
Evaluates any OpenAI-compatible LLM endpoint for chain-divergence: the fraction of
queries on which N replays produce non-identical tool-call sequences.

Quickstart::

    pip install chain-determinism-harness
    export OPENAI_API_KEY=sk-...   # or OPENROUTER_API_KEY, ANTHROPIC_API_KEY

    python -m chain_determinism_harness eval \\
        --model gpt-4.1 \\
        --n-queries 5 --n-replays 10

Outputs chain-divergence rate with Wilson 95% CI.
"""
__version__ = "0.1.0"

from .metrics import chain_divergence_rate, wilson_ci  # noqa: F401
