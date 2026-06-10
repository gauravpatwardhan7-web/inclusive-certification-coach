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
python -m evals.run_evals --suite calendar
python -m evals.run_evals --suite teachback
python -m evals.run_evals --suite mastery     # pure code, instant, no LLM
python -m evals.run_evals --suite advocacy
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

### `calendar` — negotiation correctness

Fixture: [`gold/calendar_fixture.json`](gold/calendar_fixture.json) (a fixed
5-day, 300-minute study plan) run against both synthetic calendars.

- **Light week** (plenty of gaps): every required minute must be booked,
  no block may overlap a meeting or fall outside work hours, no day may
  exceed the accommodation daily cap, every block carries its `source_id`.
- **Packed week** (~120 usable minutes): the agent must declare the week
  infeasible, detect the shortfall, produce a non-empty evidence-based
  `message_to_manager`, and offer at least two trade-off options.

Gap-finding and slot allocation are deterministic code; the LLM contributes
the pacing policy and the negotiation narrative, both behind deterministic
rails. Metric: **negotiation correctness**. LLM only — no Search needed.

### `teachback` — grading quality

Gold set: [`gold/teachback_cases.json`](gold/teachback_cases.json) (3 fixed
learner explanations of an AZ-204 skill area).

- A **complete** explanation scores ≥ 60 with no misconception flagged;
- an **incomplete** one names the missing concepts;
- a **wrong** one gets its misconception flagged and scores ≤ 45;
- every grade asks exactly one follow-up question and cites a KB source;
- and the complete explanation must **outscore** the incomplete one — a
  relative check that stays robust however strict the grader feels that day.

Needs Foundry IQ retrieval (AZ-204 content). Metric: **grading quality**.

### `mastery` — decay-model correctness

Pure code, no LLM, no Search — runs in milliseconds. Asserts the memory
model's math: mastery halves after one half-life; more reviews mean slower
decay (the spacing effect); review results blend with retained mastery and
clamp to [0, 100]; and due-refresher logic flags learned-then-forgotten
skills only (never-mastered skills belong to the remediation loop, fresh
skills aren't nagged). Metric: **decay-model correctness**.

### `advocacy` — consent-boundary integrity

The learner controls what the manager sees; this suite proves the boundary
holds:

- **redaction (deterministic)**: a non-consenting learner's accessibility
  profile is replaced with the private marker before any manager-facing model
  call; a consenting learner's profile passes through; performance evidence
  (scores, attempts) is never touched by redaction;
- **leak detector (deterministic)**: catches profile content-words in a
  draft, passes clean text, and treats a "none" profile as unleakable;
- **advocacy draft (LLM + rails)**: with consent off, the drafted
  manager note contains zero profile terms (structurally guaranteed - the
  model is never shown the context - plus the leak check as defence in
  depth), is substantive, and carries its disclosure ledger
  (`what_was_shared` / `what_was_withheld`).

Metric: **consent-boundary integrity**. LLM only — no Search needed.

## Latest results

All suites pass — 72/72 checks: `decisions` 9/9 with `--repeat 3` (27/27
individual runs), `groundedness` 13/13 (incl. the unknown-cert refusal),
`manager` 5/5, `accessibility` 5/5, `calendar` 10/10, `teachback` 12/12,
`mastery` 9/9, `advocacy` 9/9. See
`results/latest.json` for the most recent run (per-suite pass/fail + aggregate
metrics, written on every invocation).

## Notes

- Decisions are made by an LLM, so re-runs can vary on borderline cases. The
  gold cases are written with clear-cut signals so the expected action is
  unambiguous; flakiness here is itself a reliability signal worth watching.
- Groundedness uses tolerant skill-name matching (key-phrase overlap) because
  agents may shorten a skill label; hours and citation presence are exact.
