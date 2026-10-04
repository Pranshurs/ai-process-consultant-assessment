from __future__ import annotations

from pathlib import Path

import pytest

from procon import heuristic
from procon.validate import issues

EXAMPLES = sorted(Path("examples").glob("*.md"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_produces_a_valid_cited_analysis(path):
    text = path.read_text()
    a = heuristic.analyze(text)
    assert a.steps and issues(a, text) == []
    assert heuristic.analyze(text) == a  # deterministic


def test_invoice_findings():
    a = heuristic.analyze(Path("examples/invoice-processing.md").read_text())
    by_step = {c.step_ids[0]: c for c in a.automation_candidates}
    assert by_step["S2"].approach == "ai" and by_step["S2"].human_review
    assert by_step["S3"].approach == "deterministic"
    assert {"S5", "S6"} <= {s for p in a.approvals for s in p.step_ids}
    assert ("S4", "rework") in {(b.step_ids[0], b.kind) for b in a.bottlenecks}


def test_people_decisions_need_approval_and_carry_fairness_risk():
    a = heuristic.analyze(Path("examples/recruiting.md").read_text())
    assert "S5" in {s for p in a.approvals for s in p.step_ids}
    assert ("S2", "fairness") in {(r.step_ids[0], r.category) for r in a.risks}


def test_words_inside_other_words_do_not_count_as_systems():
    a = heuristic.analyze("1. Analyst checks the information on the platform.\n")
    assert a.steps[0].systems == []


def test_unbulleted_text_uses_one_step_per_line_and_empty_text_is_rejected():
    a = heuristic.analyze("Agent reads the email.\n\nAgent updates the CRM.\n")
    assert [s.id for s in a.steps] == ["S1", "S2"]
    with pytest.raises(ValueError):
        heuristic.analyze("   \n")


def test_no_money_figures_anywhere():
    a = heuristic.analyze(Path("examples/invoice-processing.md").read_text())
    assert "saving" not in a.model_dump_json().lower() and "roi" not in a.model_dump_json().lower()
