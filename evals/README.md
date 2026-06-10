# Evaluation

Gold-set evals that validate the two things judges care about most on the
Reasoning track: **does the orchestrator reason correctly**, and **does the
system stay grounded (no hallucinated facts, every claim cited)**.

```bash
source .venv/bin/activate
python -m evals.run_evals                  # all suites
python -m evals.run_evals --repeat 3       # decisions: 3 runs per case, all must pass
python -m evals.run_evals --suite decisions
python -m evals.run_evals --suite groundedness
python -m evals.run_evals --suite manager
```

Each run prints a pass/fail scorecard and writes machine-readable results to
`evals/results/latest.json`.

## Suites

### `decisions` — orchestrator reasoning accuracy

Gold set: [`gold/orchestrator_decisions.json`](gold/orchestrator_decisions.json) (9 cases).

For each case we fix the assessment result, the attempt history, and the
accessibility profile, then assert the orchestrator's decision
(`advance` | `loop` | `escalate`) and the shape of `focus_next`. Cases cover:

| Case | What it tests |
|---|---|
| D1, D5, D6 | Ready learners advance; `focus_next` is empty when advancing |
| D2 | A failing first attempt loops back to weak areas (not escalate) |
| D3 | Three stalled attempts escalate to a human coach |
| D4 | **Accommodation-aware branch**: a learner who is close, on attempt 2, with a focus disability gets a supportive `loop`, not an `escalate` |
| D7 | **Adversarial**: scores decline across attempts but stay above threshold → still `advance` (no over-penalising a harmless trend) |
| D8 | **Adversarial**: third attempt, but improving strongly (40→60→72) with a focus disability → supportive `loop`, not a blunt 3-attempts-means-escalate |
| D9 | **Adversarial**: a 0% score on the FIRST attempt → `loop`, never escalate someone who has tried once |

With `--repeat N`, every case runs N times and passes only if **all** runs
pass — the honest reliability metric for a stochastic decision-maker.

Note that the decision passes through deterministic guardrails
(`src/orchestrator.py:_apply_guardrails`) before being asserted: the eval
therefore validates the system's behaviour (LLM + rails), which is what a
learner actually experiences.

This suite calls only the reasoning model, so it runs even after the Azure AI
Search resource is torn down. Metric: **decision accuracy** (cases passed / total).

### `groundedness` — citation fidelity

Gold facts: [`gold/kb_facts.json`](gold/kb_facts.json), extracted from
`data/knowledge_base/az204_enablement_guide.md`.

Runs the Curator, Study Plan Generator, and Assessment agents end-to-end and checks that:

- every Curator module's `recommended_hours` is a value that actually appears in the KB (no invented hours);
- every Curator module, Study Plan session, and Assessment question names a skill area that exists in the KB (no invented skills);
- every Study Plan day stays within the schedule's own stated daily-minutes cap (accommodation honoured, not just claimed);
- every grounded item carries a non-empty `source_id` (nothing uncited);
- **negative case**: asking for a certification that is NOT in the knowledge base (`DP-900`) must return an empty module list with an explanatory note — the agent refuses to hallucinate a path.

This suite needs the full pipeline including **Foundry IQ retrieval (Azure AI
Search)**. If that resource has been torn down post-submission, run
`--suite decisions` and `--suite manager` (neither needs Search). Metric:
**citation fidelity** (checks passed / total).

### `manager` — team-readiness rollup correctness

Runs the Manager Insights agent over the synthetic `TEAM-A`
(`data/synthetic/team_records.json`) and checks that:

- every learner in the team appears in the rollup;
- every status is one of `ready | on_track | at_risk | needs_support`;
- the set of learners marked `ready` exactly matches those whose latest score meets the 75% threshold, and `team_readiness_pct` equals that fraction;
- the learner with 3 stalled attempts is flagged `needs_support` (human handoff).

Reasoning model only — no Search resource needed. Metric: **team rollup accuracy**.

### `accessibility` — spoken output is screen-reader friendly

Runs the Accessibility Narrator on a fixed sample learning path and checks the
spoken script is safe to read aloud: non-empty, no markdown/markup characters,
no raw `%` symbol (spelled "percent"), no markdown links, and the cert code is
spelled out rather than printed as `AZ-204`.

Reasoning model only — no Search resource needed. Metric: **spoken output quality**.

## Latest results

All suites pass: `decisions` 9/9 with `--repeat 3` (27/27 individual runs),
`groundedness` 13/13 (incl. the unknown-cert refusal), `manager` 5/5,
`accessibility` 5/5. See
`results/latest.json` for the most recent run (per-suite pass/fail + aggregate
metrics, written on every invocation).

## Notes

- Decisions are made by an LLM, so re-runs can vary on borderline cases. The
  gold cases are written with clear-cut signals so the expected action is
  unambiguous; flakiness here is itself a reliability signal worth watching.
- Groundedness uses tolerant skill-name matching (key-phrase overlap) because
  agents may shorten a skill label; hours and citation presence are exact.
