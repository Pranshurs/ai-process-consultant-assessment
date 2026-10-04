"""Offline, rule-based analyzer: no model, no network, fully deterministic.

It reads one step per line (numbered or bulleted lines; otherwise each non-empty line)
and applies keyword rules. Every finding cites the line it came from. It is a useful
first pass and a baseline for the LLM analyzer, not a substitute for one: it only knows
the vocabulary below and can't infer anything the text doesn't say in those words.
"""

from __future__ import annotations

import re

from .schema import (
    ApprovalRequirement,
    AutomationCandidate,
    Bottleneck,
    Evidence,
    Integration,
    ManualWork,
    Phase,
    ProcessAnalysis,
    Risk,
    Step,
)

SYSTEMS = {
    "email": ["email", "e-mail", "inbox", "outlook", "gmail"], "spreadsheet": ["spreadsheet", "excel", "google sheet", "csv"],
    "CRM": ["crm", "salesforce", "hubspot"], "helpdesk": ["zendesk", "freshdesk", "helpdesk", "ticketing", "ticket system"],
    "ERP/accounting": ["erp", "sap", "quickbooks", "tally", "xero", "accounting system"],
    "ATS": ["ats", "applicant tracking", "greenhouse", "lever", "workday"], "chat": ["slack", "teams", "whatsapp"],
    "e-signature": ["docusign", "e-sign"], "document store": ["sharepoint", "google drive", "dropbox", "shared drive"],
    "phone": ["phone", "call"], "paper": ["print", "paper", "scan", "fax"], "web form": ["web form", "contact form", "online form", "careers web form"],
    "calendar": ["calendar"], "bank portal": ["bank", "payment portal"],
}
MANUAL = r"\b(manually|by hand|copy|copies|paste|re-?enter|re-?type|types?|enters?|keys? in|prints?|scans?|look(s)? up|checks?|compares?|chases?|follows? up|forwards?|downloads?|uploads?|updates?)\b"
DECISION = r"\b(approves?|approval|decides?|decision|reviews?|verif(y|ies)|whether|if\b|sign(s)? off|screens?|qualif(y|ies))\b"
WAIT = r"\b(waits?|waiting|queue|backlog|until|delay(ed)?|days?|weeks?|follow(s)? up|chases?|reminders?)\b"
REWORK = r"\b(errors?|mistakes?|rework|re-?do|corrections?|mismatch(es)?|missing)\b"
HANDOFF = r"\b(forward(s|ed)?|hands? (it )?(off|over)|passes? (it )?to|sends? (it )?to|escalat(es|ed)|assign(s|ed)?)\b"
UNSTRUCTURED = r"\b(emails?|pdfs?|invoices?|resumes?|cvs?|documents?|contracts?|clauses?|tickets?|messages?|free[- ]text|notes|attachments?|scanned|repl(y|ies)|responses?|form submissions?|knowledge base)\b"
AI_VERBS = r"\b(read(s)?|categori[sz]es?|classif(y|ies)|extracts?|summari[sz]es?|drafts?|writes?|triages?|scores?|(?<!phone[ -])screens?|reviews?|qualif(y|ies)|tags?|understands?)\b"
DETERMINISTIC = r"\b(compares?|match(es)?|reconciles?|copy|copies|paste|re-?enter|re-?type|enters?|keys? in|updates?|notif(y|ies)|reminders?|routes?|routed|assign(s|ed)?|schedules?|moves?|files?|saves?|exports?|imports?|downloads?|uploads?|forwards?|follows? up|chases?)\b"
APPROVAL = r"\b(approves?|approval|sign(s)? off|authori[sz]es?|(schedules?|makes?|issues?|releases?) (the )?(payment|refund)|(sends?|extends?|makes?) (an |the )?offer|hires?|rejects? (the )?candidate|redlines?)\b"
PII = r"\b(customer|personal|resume|cv|candidate|employee|salary|bank|address|phone number|patient|id proof|aadhaar|pan)\b"
MONEY = r"\b(pay|payments?|invoices?|refunds?|amounts?|price|discounts?|credit|bank)\b"
PEOPLE_DECISIONS = r"\b(candidates?|applicants?|hire|hiring|(?<!phone[ -])screens?|shortlist(ed)?|loan|credit score)\b"
ACTOR = r"^(?:the\s+)?((?:[A-Z][\w-]*\s){0,2}(?:agent|team|manager|clerk|recruiter|reviewer|analyst|rep|representative|coordinator|officer|lead|owner|customer|accountant|associate|specialist|admin|assistant|finance|sales|support|hr|legal|ops|operations))\b"

_BULLET = re.compile(r"^\s*(?:\d+[.)]|[-*•]|step\s+\d+[:.])\s+", re.I)


def _has(pattern: str, s: str) -> bool:
    return re.search(pattern, s, re.I) is not None


def _step_lines(text: str) -> list[tuple[int, str]]:
    lines = [(i, ln.rstrip()) for i, ln in enumerate(text.splitlines(), 1)]
    bullets = [(i, _BULLET.sub("", ln).strip()) for i, ln in lines if _BULLET.match(ln)]
    if bullets:
        return bullets
    return [(i, ln.strip()) for i, ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def _title(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip():
            return ln.strip().lstrip("#").strip()[:80]
    return "Process"


def analyze(text: str) -> ProcessAnalysis:
    if not text.strip():
        raise ValueError("empty process description")
    raw_lines = text.splitlines()
    steps: list[Step] = []
    meta: dict[str, dict] = {}
    for n, (line_no, body) in enumerate(_step_lines(text), 1):
        sid = f"S{n}"
        quote = raw_lines[line_no - 1].strip()
        ev = [Evidence(line=line_no, quote=quote)]
        low = body.lower()
        systems = sorted({name for name, keys in SYSTEMS.items()
                          if any(re.search(rf"(?<![a-z]){re.escape(k)}(?![a-z])", low) for k in keys)})
        m = re.match(ACTOR, body, re.I)
        name = body if len(body) <= 90 else body[:90].rsplit(" ", 1)[0] + "…"
        steps.append(Step(id=sid, name=name, actor=m.group(1).strip() if m else "unspecified", systems=systems,
                          manual=_has(MANUAL, body), decision=_has(DECISION, body), evidence=ev))
        meta[sid] = {"body": body, "ev": ev, "systems": systems}

    bottlenecks, manual, autos, approvals, risks = [], [], [], [], []
    for s in steps:
        body, ev = meta[s.id]["body"], meta[s.id]["ev"]
        if _has(WAIT, body):
            bottlenecks.append(Bottleneck(step_ids=[s.id], kind="approval_queue" if _has(APPROVAL, body) else "waiting",
                                          description=f"Time is spent waiting or chasing in: {body[:80]}", evidence=ev))
        if _has(REWORK, body):
            bottlenecks.append(Bottleneck(step_ids=[s.id], kind="rework",
                                          description=f"Errors or corrections are mentioned in: {body[:80]}", evidence=ev))
        if _has(HANDOFF, body):
            bottlenecks.append(Bottleneck(step_ids=[s.id], kind="handoff",
                                          description=f"Work changes hands in: {body[:80]}", evidence=ev))
        if s.manual:
            manual.append(ManualWork(step_ids=[s.id], description=body[:120], evidence=ev,
                                     repetitive=_has(r"\b(each|every|all|daily|weekly)\b", body) or _has(DETERMINISTIC, body)))
        people_decision = s.decision and _has(PEOPLE_DECISIONS, body)
        needs_approval = _has(APPROVAL, body) or (people_decision and _has(r"\b(decides?|whether|invite|offer|reject)\b", body))
        if needs_approval:
            approvals.append(ApprovalRequirement(step_ids=[s.id], reason=f"Commits money, people or legal terms: {body[:80]}",
                                                 approver=s.actor if s.decision and s.actor != "unspecified" else "unspecified",
                                                 evidence=ev))
        scheduling = _has(r"\b(schedules?|follows? up|sends? (confirmations?|reminders?))\b", body)
        interpretive = _has(r"\b(read(s)?|categori[sz]es?|classif(y|ies)|extracts?|summari[sz]es?|drafts?|scores?|(?<!phone[ -])screens?)\b", body)
        if _has(UNSTRUCTURED, body) and _has(AI_VERBS, body) and (interpretive or not scheduling):
            autos.append(AutomationCandidate(
                step_ids=[s.id], approach="ai", technique="LLM extraction/classification with structured output",
                rationale="The input is unstructured text or documents and the step interprets it.",
                human_review=True, evidence=ev))
        elif _has(DETERMINISTIC, body) and (len(s.systems) >= 1 or s.manual):
            autos.append(AutomationCandidate(
                step_ids=[s.id], approach="deterministic",
                technique="API integration / rule-based workflow" if s.systems else "scripted workflow",
                rationale="Moves or updates data, or sends notifications, by a fixed rule.",
                human_review=needs_approval, evidence=ev))
        if _has(PII, body):
            risks.append(Risk(step_ids=[s.id], category="data_privacy", severity="medium",
                              description="Handles personal data; automation widens who and what can access it.",
                              mitigation="Least-privilege service accounts, redaction before any model call, retention limits."))
        if _has(MONEY, body):
            risks.append(Risk(step_ids=[s.id], category="financial", severity="high" if needs_approval else "medium",
                              description="Errors here move or misstate money.",
                              mitigation="Keep human approval; reconcile automatically against the source record."))
        if _has(r"\b(contracts?|clauses?|legal|compliance|regulat\w*|governing law)\b", body):
            risks.append(Risk(step_ids=[s.id], category="compliance", severity="medium",
                              description="Legal or contractual content; a wrong reading creates obligations.",
                              mitigation="Model output is advisory; a qualified reviewer signs off; keep the source clause linked."))
        if _has(PEOPLE_DECISIONS, body):
            risks.append(Risk(step_ids=[s.id], category="fairness", severity="high",
                              description="Decisions about people; automated screening can encode bias.",
                              mitigation="Assistive only, with a human decision; audit outcomes by group; document criteria."))
    for c in autos:
        if c.approach == "ai":
            risks.append(Risk(step_ids=c.step_ids, category="model_error", severity="medium",
                              description="A model can misread or invent fields.",
                              mitigation="Schema-validated output, confidence thresholds, and human review of low-confidence items."))

    integrations = []
    for name in sorted({x for s in steps for x in s.systems}):
        if name in {"paper", "phone"}:
            continue
        integrations.append(Integration(system=name, purpose="read/write data used by the automated steps",
                                        step_ids=[s.id for s in steps if name in s.systems]))

    det = sorted({sid for c in autos if c.approach == "deterministic" for sid in c.step_ids}, key=lambda x: int(x[1:]))
    ai = sorted({sid for c in autos if c.approach == "ai" for sid in c.step_ids}, key=lambda x: int(x[1:]))
    gated = sorted({sid for a in approvals for sid in a.step_ids}, key=lambda x: int(x[1:]))
    phases: list[Phase] = []
    for title, ids, deliverable in (
        ("Deterministic quick wins", det, "Integrations and rule-based automation for data movement and notifications"),
        ("AI-assisted steps with human review", ai, "Model-backed extraction/classification behind a review queue"),
        ("Approval workflow and monitoring", gated, "Explicit approval UI, audit log, and outcome monitoring"),
    ):
        if ids:
            phases.append(Phase(order=len(phases) + 1, title=title, step_ids=ids, deliverable=deliverable,
                                depends_on=[p.order for p in phases]))

    return ProcessAnalysis(
        process_name=_title(text), summary=(
            f"{len(steps)} steps; {sum(s.manual for s in steps)} manual, {len(bottlenecks)} bottleneck signals, "
            f"{len(det)} deterministic and {len(ai)} AI automation candidates, {len(gated)} steps needing approval. "
            "Produced by the offline rule-based analyzer."),
        steps=steps, bottlenecks=bottlenecks, manual_work=manual, automation_candidates=autos, approvals=approvals,
        risks=risks, integrations=integrations, implementation_sequence=phases,
        assumptions=["One step per numbered/bulleted line (or per line).",
                     "Findings come from keyword rules; anything not phrased in that vocabulary is missed."],
        open_questions=["How many items per month go through this process, and how long does each step take?",
                        "Which systems have APIs or exports available?",
                        "Who owns approval for each gated step, and what are the thresholds?"],
    )
