"""Deterministic checks on any analysis, whichever analyzer produced it.

Hard rules (an analysis that breaks one is rejected):
  * every evidence line exists, and its quote appears on that line (whitespace and case
    normalised), so evidence can't be invented;
  * every step id that is referenced is defined, and step ids are unique;
  * every step, bottleneck, manual-work item, automation candidate and approval cites
    evidence;
  * implementation phases are numbered 1..n, and each depends only on earlier phases;
  * an automation candidate on a step that needs approval must keep a human in review.
"""

from __future__ import annotations

import re

from .schema import ProcessAnalysis


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def issues(analysis: ProcessAnalysis, text: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    ids = [s.id for s in analysis.steps]
    if len(ids) != len(set(ids)):
        out.append("duplicate step ids")
    known = set(ids)

    def check_evidence(where: str, evidence) -> None:
        if not evidence:
            out.append(f"{where}: no evidence")
        for ev in evidence:
            if not 1 <= ev.line <= len(lines):
                out.append(f"{where}: evidence line {ev.line} does not exist")
            elif not _norm(ev.quote) or _norm(ev.quote) not in _norm(lines[ev.line - 1]):
                out.append(f"{where}: quote not found on line {ev.line}: {ev.quote[:60]!r}")

    def check_refs(where: str, step_ids) -> None:
        missing = [s for s in step_ids if s not in known]
        if missing:
            out.append(f"{where}: unknown step ids {missing}")

    for s in analysis.steps:
        check_evidence(f"step {s.id}", s.evidence)
    for kind, items in (("bottleneck", analysis.bottlenecks), ("manual_work", analysis.manual_work),
                        ("automation", analysis.automation_candidates), ("approval", analysis.approvals)):
        for i, item in enumerate(items, 1):
            check_refs(f"{kind} {i}", item.step_ids)
            check_evidence(f"{kind} {i}", item.evidence)
    for i, r in enumerate(analysis.risks, 1):
        check_refs(f"risk {i}", r.step_ids)
    for i, g in enumerate(analysis.integrations, 1):
        check_refs(f"integration {i}", g.step_ids)

    orders = [p.order for p in analysis.implementation_sequence]
    if orders != list(range(1, len(orders) + 1)):
        out.append(f"phases must be numbered 1..n in order, got {orders}")
    for p in analysis.implementation_sequence:
        check_refs(f"phase {p.order}", p.step_ids)
        if any(d >= p.order for d in p.depends_on):
            out.append(f"phase {p.order} depends on a later phase {p.depends_on}")

    needs_approval = {s for a in analysis.approvals for s in a.step_ids}
    for i, c in enumerate(analysis.automation_candidates, 1):
        if set(c.step_ids) & needs_approval and not c.human_review:
            out.append(f"automation {i} automates an approval step without human review")
    return out
