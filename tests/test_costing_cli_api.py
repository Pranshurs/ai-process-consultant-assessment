from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from procon import heuristic
from procon.api import app
from procon.cli import main
from procon.costing import CostInputs, cost_report

INVOICE = Path("examples/invoice-processing.md")


def test_cost_report_is_arithmetic_on_inputs_only():
    a = heuristic.analyze(INVOICE.read_text())
    r = cost_report(a, CostInputs(items_per_month=120, hourly_cost=30, minutes_per_step={"S2": 5, "S4": 10, "S99": 3}))
    s2 = next(x for x in r.steps if x.step_id == "S2")
    assert (s2.hours_per_month, s2.cost_per_month, s2.automation_candidate) == (10.0, 300.0, "ai")
    assert r.total_hours_per_month == 30.0 and r.unknown_step_ids == ["S99"]
    assert "not a savings estimate" in r.note
    assert not any("saving" in k for k in r.model_dump())


def test_cli_markdown_json_and_costs(capsys):
    assert main(["analyze", str(INVOICE), "--costs", "examples/invoice-processing.costs.json"]) == 0
    out = capsys.readouterr().out
    assert "## Automation candidates" in out and "Current-state cost" in out
    assert main(["analyze", str(INVOICE), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["analyzer"].startswith("heuristic")


def test_cli_empty_input_exits_2(tmp_path, capsys):
    (tmp_path / "e.md").write_text("  \n")
    assert main(["analyze", str(tmp_path / "e.md")]) == 2


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("PROCON_ANALYZER", "")
    return TestClient(app)


def test_api(client):
    assert client.get("/health").json() == {"status": "ok", "default_analyzer": "heuristic"}
    r = client.post("/analyze", json={"text": INVOICE.read_text(),
                                      "costs": {"items_per_month": 10, "hourly_cost": 60, "minutes_per_step": {"S3": 6}}})
    assert r.status_code == 200 and r.json()["cost"]["total_cost_per_month"] == 60.0
    assert client.post("/analyze", json={"text": ""}).status_code == 422
    assert client.post("/analyze", json={"text": "x", "analyzer": "gpt"}).status_code == 422


def test_eval_runs_and_separates_held_out(monkeypatch):
    import runpy

    monkeypatch.setenv("PROCON_ANALYZER", "")
    with pytest.raises(SystemExit) as e:
        runpy.run_path("eval/run_eval.py", run_name="__main__")
    assert e.value.code == 0
    res = json.loads(Path("eval/results.json").read_text())
    assert res["in_sample"]["errors"] == 0 and res["held_out"]["errors"] == 0


def test_any_analyzer_output_is_validated_before_it_is_returned(client, monkeypatch):
    from procon import service
    from procon.schema import Evidence

    real = heuristic.analyze

    def fabricating(text):
        a = real(text)
        a.steps[0].evidence[0] = Evidence(line=1, quote="something the text never says")
        return a

    monkeypatch.setattr(heuristic, "analyze", fabricating)
    with pytest.raises(service.InvalidAnalysis):
        service.run(INVOICE.read_text())
    assert client.post("/analyze", json={"text": INVOICE.read_text()}).status_code == 502
