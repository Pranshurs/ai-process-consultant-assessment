"""Markdown rendering of an analysis (and optional cost report)."""

from __future__ import annotations

from .costing import CostReport
from .schema import ProcessAnalysis


def _ids(ids: list[str]) -> str:
    return ", ".join(ids) or "—"


def _ev(evidence) -> str:
    return "; ".join(f"L{e.line}" for e in evidence) or "—"


def markdown(a: ProcessAnalysis, analyzer: str, cost: CostReport | None = None) -> str:
    out = [f"# {a.process_name}", "", f"_Analyzer: {analyzer}_", "", a.summary, "", "## Process map", "",
           "| Step | Action | Actor | Systems | Manual | Decision | Source |", "|---|---|---|---|---|---|---|"]
    for s in a.steps:
        out.append(f"| {s.id} | {s.name} | {s.actor} | {', '.join(s.systems) or '—'} | {'yes' if s.manual else ''} "
                   f"| {'yes' if s.decision else ''} | {_ev(s.evidence)} |")
    sections = [
        ("Bottlenecks", a.bottlenecks, lambda b: f"**{b.kind}** ({_ids(b.step_ids)}): {b.description} [{_ev(b.evidence)}]"),
        ("Manual and repetitive work", a.manual_work,
         lambda m: f"({_ids(m.step_ids)}) {m.description}{' — repetitive' if m.repetitive else ''} [{_ev(m.evidence)}]"),
        ("Automation candidates", a.automation_candidates,
         lambda c: f"**{c.approach}** ({_ids(c.step_ids)}): {c.technique}. {c.rationale}"
                   f"{' Human review required.' if c.human_review else ''} [{_ev(c.evidence)}]"),
        ("Human approval required", a.approvals, lambda p: f"({_ids(p.step_ids)}) {p.reason}; approver: {p.approver}"),
        ("Risks", a.risks, lambda r: f"**{r.severity} / {r.category}** ({_ids(r.step_ids)}): {r.description} "
                                     f"Mitigation: {r.mitigation}"),
        ("Integrations", a.integrations, lambda g: f"**{g.system}** ({_ids(g.step_ids)}): {g.purpose}"),
        ("Implementation sequence", a.implementation_sequence,
         lambda p: f"{p.order}. **{p.title}** ({_ids(p.step_ids)}): {p.deliverable}"
                   + (f" (after {', '.join(map(str, p.depends_on))})" if p.depends_on else "")),
        ("Assumptions", a.assumptions, lambda x: x),
        ("Open questions", a.open_questions, lambda x: x),
    ]
    for title, items, fmt in sections:
        out += ["", f"## {title}", ""] + ([f"- {fmt(i)}" for i in items] or ["- none found"])
    if cost:
        out += ["", "## Current-state cost (from your inputs)", "",
                f"| Step | Hours/month | Cost/month ({cost.currency}) | Candidate |", "|---|---|---|---|"]
        out += [f"| {r.step_id} | {r.hours_per_month} | {r.cost_per_month} | {r.automation_candidate or '—'} |" for r in cost.steps]
        out += ["", f"Total: {cost.total_hours_per_month} h, {cost.total_cost_per_month} {cost.currency}/month. "
                    f"In candidate steps: {cost.hours_in_candidate_steps} h, {cost.cost_in_candidate_steps} {cost.currency}.",
                "", f"_{cost.note}_"]
    return "\n".join(out) + "\n"
