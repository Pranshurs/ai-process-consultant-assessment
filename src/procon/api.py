"""HTTP API: ``uvicorn procon.api:app``. POST /analyze, GET /health."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import service
from .costing import CostInputs, CostReport, cost_report
from .schema import ProcessAnalysis

app = FastAPI(title="procon", version="0.1.0")


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=service.MAX_CHARS)
    analyzer: Optional[Literal["heuristic", "claude"]] = None
    costs: Optional[CostInputs] = None


class AnalyzeResponse(BaseModel):
    analyzer: str
    analysis: ProcessAnalysis
    cost: Optional[CostReport] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_analyzer": service.default_analyzer()}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        analysis, label = service.run(req.text, req.analyzer)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except service.InvalidAnalysis as exc:
        raise HTTPException(502, f"analysis failed validation: {exc}") from exc
    return AnalyzeResponse(analyzer=label, analysis=analysis,
                           cost=cost_report(analysis, req.costs) if req.costs else None)
