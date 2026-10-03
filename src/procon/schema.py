"""The structured process analysis every analyzer must return.

Every finding cites evidence: a 1-based line number in the submitted process text, plus a
verbatim quote from that line. ``procon.validate`` checks those citations against the
input, so an analysis can't contain a step, bottleneck or risk the input never mentions
without being flagged.

The schema deliberately has no ROI or savings fields. Cost figures come only from
``procon.costing``, from numbers the user supplies.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_M):
    line: int = Field(description="1-based line number in the submitted process text")
    quote: str = Field(description="Verbatim excerpt copied from that line")


class Step(_M):
    id: str = Field(description='Step id, "S1", "S2", ... in process order')
    name: str
    actor: str = Field(description='Who performs it, or "unspecified"')
    systems: list[str] = Field(description="Tools/systems used in this step, as named in the text")
    manual: bool = Field(description="Performed by a person by hand (typing, copying, checking, chasing)")
    decision: bool = Field(description="Involves a judgement or approval")
    evidence: list[Evidence]


class Bottleneck(_M):
    step_ids: list[str]
    kind: Literal["waiting", "handoff", "rework", "manual_volume", "approval_queue", "other"]
    description: str
    evidence: list[Evidence]


class ManualWork(_M):
    step_ids: list[str]
    description: str
    repetitive: bool = Field(description="Done the same way for every item")
    evidence: list[Evidence]


class AutomationCandidate(_M):
    step_ids: list[str]
    approach: Literal["deterministic", "ai"] = Field(
        description="deterministic = rules/integration/scripts; ai = needs a model (unstructured input, judgement)")
    technique: str = Field(description='e.g. "API integration", "rule-based routing", "LLM field extraction"')
    rationale: str
    human_review: bool = Field(description="A person must review or approve the automated output")
    evidence: list[Evidence]


class ApprovalRequirement(_M):
    step_ids: list[str]
    reason: str
    approver: str = Field(description='Role that must approve, or "unspecified"')
    evidence: list[Evidence]


class Risk(_M):
    step_ids: list[str]
    category: Literal["data_privacy", "financial", "compliance", "fairness", "model_error", "operational", "security"]
    severity: Literal["low", "medium", "high"]
    description: str
    mitigation: str


class Integration(_M):
    system: str
    purpose: str
    step_ids: list[str]


class Phase(_M):
    order: int
    title: str
    step_ids: list[str]
    deliverable: str
    depends_on: list[int] = Field(description="orders of earlier phases this one needs")


class ProcessAnalysis(_M):
    process_name: str
    summary: str
    steps: list[Step]
    bottlenecks: list[Bottleneck]
    manual_work: list[ManualWork]
    automation_candidates: list[AutomationCandidate]
    approvals: list[ApprovalRequirement]
    risks: list[Risk]
    integrations: list[Integration]
    implementation_sequence: list[Phase]
    assumptions: list[str] = Field(description="Things inferred rather than stated in the text")
    open_questions: list[str] = Field(description="What a consultant would need to ask before building")
