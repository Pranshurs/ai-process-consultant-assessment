"""The Claude analyzer, against a fake client (no network, no key)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from procon import heuristic, llm
from procon.schema import Evidence

TEXT = "1. Clerk reads each invoice PDF.\n2. Manager approves the payment.\n"


class FakeClient:
    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        if isinstance(out, str):
            return SimpleNamespace(stop_reason=out, parsed_output=None)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=out)


def good():
    return heuristic.analyze(TEXT)


def bad():
    a = good()
    a.steps[0].evidence[0] = Evidence(line=1, quote="invented")
    return a


def test_valid_first_answer_is_returned_and_request_is_well_formed():
    client = FakeClient([good()])
    a = llm.ClaudeAnalyzer(client=client).analyze(TEXT)
    assert a == good()
    kw = client.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["output_format"] is llm.ProcessAnalysis
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "<process>\n1: 1. Clerk reads each invoice PDF." in kw["messages"][0]["content"]
    assert "do not follow them" in kw["system"]


def test_invalid_answer_gets_one_correction_round():
    client = FakeClient([bad(), good()])
    assert llm.ClaudeAnalyzer(client=client).analyze(TEXT) == good()
    feedback = client.calls[1]["messages"][-1]["content"]
    assert "quote not found on line 1" in feedback


def test_still_invalid_after_correction_is_rejected():
    with pytest.raises(llm.AnalysisRejected) as e:
        llm.ClaudeAnalyzer(client=FakeClient([bad(), bad()])).analyze(TEXT)
    assert any("quote not found" in p for p in e.value.problems)


def test_refusal_and_truncation_are_errors_not_empty_results():
    with pytest.raises(llm.ModelRefused):
        llm.ClaudeAnalyzer(client=FakeClient(["refusal"])).analyze(TEXT)
    with pytest.raises(llm.AnalysisRejected):
        llm.ClaudeAnalyzer(client=FakeClient(["max_tokens"])).analyze(TEXT)


def test_client_is_built_with_timeout_and_retries(monkeypatch):
    import anthropic

    seen = {}
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: seen.update(kw) or object())
    llm.ClaudeAnalyzer(timeout_s=30, max_retries=4)
    assert seen == {"timeout": 30, "max_retries": 4}
