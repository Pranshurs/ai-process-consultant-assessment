from __future__ import annotations

import pytest

from procon import heuristic
from procon.schema import AutomationCandidate, Evidence, Phase
from procon.validate import issues

TEXT = "1. Clerk reads each invoice PDF.\n2. Clerk re-enters it into QuickBooks.\n3. Manager approves the payment.\n"


@pytest.fixture()
def good():
    a = heuristic.analyze(TEXT)
    assert issues(a, TEXT) == []
    return a


def test_invented_quote_is_rejected(good):
    good.steps[0].evidence[0] = Evidence(line=1, quote="Clerk wires money to an offshore account")
    assert any("quote not found" in p for p in issues(good, TEXT))


def test_missing_line_is_rejected(good):
    good.steps[1].evidence[0] = Evidence(line=40, quote="x")
    assert any("line 40 does not exist" in p for p in issues(good, TEXT))


def test_unknown_step_reference_is_rejected(good):
    good.bottlenecks.append(good.bottlenecks[0].model_copy(update={"step_ids": ["S9"]}) if good.bottlenecks else
                            heuristic.Bottleneck(step_ids=["S9"], kind="other", description="x",
                                                 evidence=[Evidence(line=1, quote="Clerk")]))
    assert any("unknown step ids ['S9']" in p for p in issues(good, TEXT))


def test_automating_an_approval_without_review_is_rejected(good):
    good.automation_candidates.append(AutomationCandidate(
        step_ids=["S3"], approach="ai", technique="auto-approve", rationale="x", human_review=False,
        evidence=[Evidence(line=3, quote="approves the payment")]))
    assert any("without human review" in p for p in issues(good, TEXT))


def test_phase_order_and_dependencies(good):
    good.implementation_sequence = [Phase(order=1, title="a", step_ids=["S1"], deliverable="d", depends_on=[2])]
    assert any("depends on a later phase" in p for p in issues(good, TEXT))
    good.implementation_sequence = [Phase(order=2, title="a", step_ids=["S1"], deliverable="d", depends_on=[])]
    assert any("numbered 1..n" in p for p in issues(good, TEXT))


def test_quotes_tolerate_whitespace_and_case(good):
    good.steps[0].evidence[0] = Evidence(line=1, quote="  clerk   READS each invoice ")
    assert issues(good, TEXT) == []
