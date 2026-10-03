"""One entry point for the CLI and the API: pick an analyzer, analyze, validate."""

from __future__ import annotations

import os

from . import heuristic
from .schema import ProcessAnalysis
from .validate import issues

MAX_CHARS = 30_000


class InvalidAnalysis(RuntimeError):
    pass


def default_analyzer() -> str:
    """``claude`` only when PROCON_ANALYZER=claude; the offline heuristic otherwise."""
    return (os.getenv("PROCON_ANALYZER") or "heuristic").strip().lower()


def run(text: str, analyzer: str | None = None) -> tuple[ProcessAnalysis, str]:
    if not text.strip():
        raise ValueError("empty process description")
    if len(text) > MAX_CHARS:
        raise ValueError(f"process description over {MAX_CHARS} characters; split it")
    name = analyzer or default_analyzer()
    if name == "heuristic":
        analysis, label = heuristic.analyze(text), "heuristic (offline, rule-based)"
    elif name == "claude":
        from .llm import MODEL, ClaudeAnalyzer

        analysis, label = ClaudeAnalyzer().analyze(text), f"claude ({MODEL})"
    else:
        raise ValueError(f"unknown analyzer {name!r}; use heuristic or claude")
    problems = issues(analysis, text)
    if problems:  # the Claude path already enforces this; the heuristic must meet the same bar
        raise InvalidAnalysis("; ".join(problems))
    return analysis, label
