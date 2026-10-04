"""``procon analyze process.md [--analyzer heuristic|claude] [--costs costs.json] [--json]``"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import service
from .costing import CostInputs, cost_report
from .render import markdown


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="procon", description="Structured analysis of a business process.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("file", help="process / SOP text file, or - for stdin")
    a.add_argument("--analyzer", choices=["heuristic", "claude"], default=None,
                   help="default: PROCON_ANALYZER or heuristic")
    a.add_argument("--costs", help="JSON with items_per_month, hourly_cost, minutes_per_step (optional)")
    a.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    args = ap.parse_args(argv)

    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    try:
        analysis, label = service.run(text, args.analyzer)
    except (ValueError, service.InvalidAnalysis) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    cost = cost_report(analysis, CostInputs.model_validate_json(Path(args.costs).read_text())) if args.costs else None
    if args.json:
        print(json.dumps({"analyzer": label, "analysis": analysis.model_dump(),
                          "cost": cost.model_dump() if cost else None}, indent=2))
    else:
        print(markdown(analysis, label, cost), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
