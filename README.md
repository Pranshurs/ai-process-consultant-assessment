# procon: evidence-cited process analysis for automation

[![tests](https://github.com/Pranshurs/ai-process-consultant-assessment/actions/workflows/ci.yml/badge.svg)](https://github.com/Pranshurs/ai-process-consultant-assessment/actions/workflows/ci.yml)

You give `procon` a business process or SOP as plain text. It returns a typed analysis
with these parts:
- process map
- bottlenecks
- manual and repetitive work
- deterministic and AI automation candidates
- required human approvals
- risks
- integrations
- implementation sequence
- assumptions and open questions

Every finding cites the line of the input it came from, and the citations are checked.

> **Origin.** This repository first held a job-assessment submission for an AI Process
> Consultant role. The submission document itself was never committed. In October 2026
> the repository was turned into this small working application.

## Two analyzers, one contract

| Analyzer | What it is | Needs |
|---|---|---|
| `heuristic` (default) | Deterministic keyword and pattern rules (`src/procon/heuristic.py`). A transparent baseline. | Nothing; works offline |
| `claude` | Claude (`claude-opus-5-5` by default) with structured output into the same `ProcessAnalysis` schema | `pip install ".[claude]"` and an Anthropic API key |

Both produce the same pydantic `ProcessAnalysis` (`src/procon/schema.py`), and both pass
through the same checks (`src/procon/validate.py`) before anything is returned:
- every evidence line exists, and its quote appears on that line, so a finding can't cite
  text the input doesn't contain;
- referenced steps exist, and implementation phases only depend on earlier phases;
- any automation of a step that needs approval keeps a human reviewer.

How the Claude path handles problems:
- **Validation failure:** the model gets the list of problems once and can correct its
  answer. If it fails again, the analysis is rejected, not returned.
- **Refusal or truncated output:** these are errors, never empty results.
- **Prompt injection:** the input is sent as numbered data inside `<process>` tags, and the
  model is told not to follow instructions found in it.
- **Fallback, timeouts and retries:** server-side refusal fallback (`fallbacks="default"`)
  is enabled, and the client has a timeout and retries.

**Not verified:** the Claude analyzer is tested against a fake client, which covers the
request shape, the correction round, refusals and truncation. It hasn't been run against
the live API in this repository, so no Claude results are claimed below.

**No ROI.** The analysis never estimates savings. If you supply monthly volume, minutes
per step and an hourly cost, `--costs` reports what each step costs today and how much of
that sits in automation-candidate steps. That figure is a ceiling, not a forecast.

## Quick start

```bash
pip install -e ".[dev]"
procon analyze examples/invoice-processing.md                      # Markdown report, offline
procon analyze examples/invoice-processing.md --json
procon analyze examples/invoice-processing.md --costs examples/invoice-processing.costs.json
PROCON_ANALYZER=claude procon analyze examples/support.md          # needs ANTHROPIC_API_KEY
uvicorn procon.api:app                                             # POST /analyze {"text": ..., "costs": ...}
pytest -q
python eval/run_eval.py
```

The examples are illustrative processes written for this repository:
- support tickets
- invoice processing
- recruiting
- lead qualification
- contract review
- two held-out cases: onboarding and expenses

## How good is the heuristic?

`eval/run_eval.py` scores an analyzer against hand-written expectations
(`eval/expectations.json`). For each example it lists the automation candidates,
approvals, bottlenecks and risks a reviewer should expect. The heuristic's rules were
tuned on the five in-sample examples. The two held-out examples, and their expectations,
were written before the heuristic was run on them, and the rules weren't changed
afterwards.

| Check | In-sample (5 examples) | Held-out (2 examples) |
|---|---|---|
| Automation candidates found (with the right approach) | 19/20 | 3/7 |
| Approval steps found (recall) | 7/7 | 3/3 |
| Approval precision | 7/8 | 3/4 |
| Bottleneck steps found | 6/6 | 4/4 |
| Risks found | 9/9 | 1/4 |

The drop from in-sample to held-out is the point: keyword rules overfit to the phrasing
they were tuned on. In the held-out cases they miss:
- **Automation candidates:**
  - emailing IT for a laptop (onboarding S3)
  - creating accounts by hand (onboarding S4)
  - reading photographed receipts (expenses S2)
  - checking claims against the travel policy (expenses S3)
- **Risks:**
  - permissions (security, onboarding S5)
  - misreading receipts (expenses S2)
  - the money in the claim approval (expenses S5)

Treat the heuristic as a cited first pass. Use the `claude` analyzer, through the same
eval, for real analysis. `PROCON_ANALYZER=claude python eval/run_eval.py` runs that eval,
but it has not been run here.

## Limitations

- The heuristic reads one step per line. It only knows the vocabulary in
  `heuristic.py`, so it misses steps phrased differently.
- Citations prove that a finding points at real input text, not that the finding is
  right. A human still reviews the analysis.
- There's no multi-document input, no diagram output, and no cost modelling beyond the
  arithmetic above.

MIT licensed.
