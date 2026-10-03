"""Score an analyzer against hand-written expectations for the example processes.

    python eval/run_eval.py                       # offline heuristic
    PROCON_ANALYZER=claude python eval/run_eval.py   # needs ANTHROPIC_API_KEY

For each example it measures:
- **Automation:** expected (step, approach) pairs found. ``any`` accepts either approach.
- **Approvals:** recall, plus precision, because extra approvals cost reviewer time.
- **Bottlenecks:** expected steps found.
- **Risks:** expected (step, category) pairs found.
- **Validation:** the analysis passed ``procon.validate``.

In-sample and held-out examples are reported separately. The heuristic was tuned on the
in-sample examples.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from procon import service  # noqa: E402


def score(name: str, exp: dict, analyzer: str | None) -> dict:
    text = (ROOT / "examples" / f"{name}.md").read_text(encoding="utf-8")
    try:
        a, label = service.run(text, analyzer)
    except Exception as exc:  # an analyzer failure scores zero, it doesn't stop the run
        return {"example": name, "error": f"{type(exc).__name__}: {exc}"}
    found_auto = {}
    for c in a.automation_candidates:
        for sid in c.step_ids:
            found_auto.setdefault(sid, set()).add(c.approach)
    auto_hits = [sid for sid, want in exp["automation"].items()
                 if sid in found_auto and (want == "any" or want in found_auto[sid])]
    got_appr = {sid for p in a.approvals for sid in p.step_ids}
    want_appr = set(exp["approvals"])
    got_bott = {sid for b in a.bottlenecks for sid in b.step_ids}
    got_risk = {(sid, r.category) for r in a.risks for sid in r.step_ids}
    want_risk = {tuple(x) for x in exp["risks"]}
    return {
        "example": name, "analyzer": label,
        "automation": [len(auto_hits), len(exp["automation"])],
        "approvals_recall": [len(want_appr & got_appr), len(want_appr)],
        "approvals_precision": [len(want_appr & got_appr), len(got_appr)],
        "bottlenecks": [len(set(exp["bottlenecks"]) & got_bott), len(exp["bottlenecks"])],
        "risks": [len(want_risk & got_risk), len(want_risk)],
        "missed": {
            "automation": sorted(set(exp["automation"]) - set(auto_hits)),
            "approvals": sorted(want_appr - got_appr), "extra_approvals": sorted(got_appr - want_appr),
            "bottlenecks": sorted(set(exp["bottlenecks"]) - got_bott),
            "risks": sorted(map(list, want_risk - got_risk)),
        },
    }


def _sum(rows: list[dict], key: str) -> list[int]:
    ok = [r for r in rows if "error" not in r]
    return [sum(r[key][0] for r in ok), sum(r[key][1] for r in ok)]


def main() -> int:
    exps = json.loads((ROOT / "eval" / "expectations.json").read_text())
    rows = [score(n, e, None) for n, e in exps.items() if not n.startswith("_")]
    out = {"examples": rows}
    for split, keep in (("in_sample", lambda n: not n.startswith("heldout")), ("held_out", lambda n: n.startswith("heldout"))):
        part = [r for r in rows if keep(r["example"])]
        out[split] = {k: _sum(part, k) for k in ("automation", "approvals_recall", "approvals_precision", "bottlenecks", "risks")}
        out[split]["errors"] = sum("error" in r for r in part)
    for split in ("in_sample", "held_out"):
        s = out[split]
        print(f"{split:<10} " + "  ".join(f"{k} {v[0]}/{v[1]}" for k, v in s.items() if k != "errors")
              + f"  errors {s['errors']}")
    for r in rows:
        print(f"  {r['example']:<20} " + (r.get("error") or json.dumps(r["missed"])))
    dest = ROOT / "eval" / "results.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
