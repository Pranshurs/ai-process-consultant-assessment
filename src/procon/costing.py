"""Current-state cost, computed only from numbers the user provides.

Nothing here estimates savings or ROI. Given monthly volume, minutes per step and an
hourly cost, it reports what each step costs today, and how much of that sits in steps
flagged as automation candidates. That's the ceiling a project could address, not a
forecast of what it would save.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .schema import ProcessAnalysis


class CostInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items_per_month: float = Field(gt=0)
    hourly_cost: float = Field(gt=0)
    currency: str = "USD"
    minutes_per_step: dict[str, float] = Field(description="step id -> minutes of human time per item")


class StepCost(BaseModel):
    step_id: str
    hours_per_month: float
    cost_per_month: float
    automation_candidate: str | None


class CostReport(BaseModel):
    currency: str
    steps: list[StepCost]
    total_hours_per_month: float
    total_cost_per_month: float
    hours_in_candidate_steps: float
    cost_in_candidate_steps: float
    unknown_step_ids: list[str]
    note: str = ("Current-state cost from the inputs given. Cost in candidate steps is the most a project "
                 "could address, not a savings estimate.")


def cost_report(analysis: ProcessAnalysis, inputs: CostInputs) -> CostReport:
    known = {s.id for s in analysis.steps}
    approach = {}
    for c in analysis.automation_candidates:
        for sid in c.step_ids:
            approach.setdefault(sid, c.approach)
    rows = []
    for sid, minutes in sorted(inputs.minutes_per_step.items(), key=lambda kv: (len(kv[0]), kv[0])):
        if sid not in known or minutes < 0:
            continue
        hours = inputs.items_per_month * minutes / 60
        rows.append(StepCost(step_id=sid, hours_per_month=round(hours, 2), cost_per_month=round(hours * inputs.hourly_cost, 2),
                             automation_candidate=approach.get(sid)))
    cand = [r for r in rows if r.automation_candidate]
    return CostReport(
        currency=inputs.currency, steps=rows,
        total_hours_per_month=round(sum(r.hours_per_month for r in rows), 2),
        total_cost_per_month=round(sum(r.cost_per_month for r in rows), 2),
        hours_in_candidate_steps=round(sum(r.hours_per_month for r in cand), 2),
        cost_in_candidate_steps=round(sum(r.cost_per_month for r in cand), 2),
        unknown_step_ids=sorted(set(inputs.minutes_per_step) - known),
    )
