# Inclusive Certification Coach

A multi-agent enterprise learning system for the **Microsoft Agents League — Reasoning Agents** track. It helps organisations run internal certification programmes, designed **accessibility-first** so that employees with disabilities (neurodivergent, cognitive, low-vision) get certification prep that adapts to how they actually work.

> **Status:** all 5 agents built, grounded via Foundry IQ, with a visible reasoning trace, screen-reader-first spoken output with browser read-aloud, a Streamlit demo, and gold-set evals. **Data:** 100% synthetic — no real people, no PII (identifiers like `L-1001`, `EMP-001`, `TEAM-A`).

---

## Why this project

The challenge scenario is an enterprise certification-learning system. Most implementations treat every learner identically. Ours adds two things that matter:

1. **Inclusive by design** — study paths, pacing, and assessments adapt to cognitive load, focus windows, and accessible formats, instead of one-size-fits-all.
2. **A visible reasoning trace** — the UI shows *which agent did what, what it retrieved, what it cited, and why the orchestrator looped or advanced*. The track is about reasoning, so we make the reasoning legible.

---

## Architecture

Five agents: four in the per-learner reasoning loop, plus a team-level
Manager Insights agent.

| Agent | Type | Job | Grounding |
|---|---|---|---|
| Learning Path Curator | workflow step | Map a certification goal to skills + cited modules, with per-module accommodation notes | Foundry IQ |
| Study Plan Generator | workflow step | Turn the cited path into an accommodation-aware day-by-day schedule (block sizes, breaks, checkpoints) | Foundry IQ (pacing rules) |
| Assessment Agent | workflow step | Generate grounded, cited practice questions; score readiness; report weak areas | Foundry IQ |
| Orchestrator | reasoning loop | Reason over score, weak areas, history, and accessibility profile to decide: advance, loop back to weak areas, or escalate to a human | — |
| Manager Insights | reasoning / analytics | Roll up a team's progress: per-learner status, team readiness %, recommended actions | synthetic team records |

**Microsoft IQ layer:** Foundry IQ (Azure AI Search), grounded retrieval with citations.

**Reasoning patterns used:** grounded retrieval (every answer cited to Foundry IQ sources), an orchestrated decision loop (the Orchestrator reasons over score, weak areas, attempt history, and accessibility profile to choose advance / loop-to-weak-areas / escalate), human-in-the-loop escalation on repeated failure, and team-level reasoning (Manager Insights rolls per-learner state up to a readiness verdict). The reasoning model (o4-mini) surfaces its step-by-step trace in the UI rather than hiding it.

```
Learner goal (cert + role + accessibility profile)
   -> Curator         : Foundry IQ retrieval -> cited, accommodation-aware learning path
      -> Study Plan   : Foundry IQ pacing rules -> accommodation-aware schedule
         -> Assessment: Foundry IQ retrieval -> cited questions -> score + weak areas
            -> Orchestrator (reasoning model): given score + weak areas + attempt
               history + accessibility profile, decide
                  advance      (ready)
                  loop         (not ready -> revisit only the weak areas)
                  escalate     (repeated failure -> human coach)
   -> every step appended to a visible reasoning trace shown in the UI

Manager Insights (team view): reasons over synthetic team records (TEAM-A)
   -> per-learner status (ready / on_track / at_risk / needs_support)
      + team readiness % + recommended manager actions
```

### Accessibility & voice

Inclusion is the whole point, so output is not text-only-on-a-screen:

- **Accessibility Narrator** (`src/accessibility.py`) converts any agent's
  structured output into a **screen-reader-first spoken script** — linear plain
  text, no tables or markdown, abbreviations spelled out (`AZ-204` -> "A Z two oh
  four"), symbols read as words ("75 percent"), adapted to the learner's profile.
- **Read aloud in the UI** plays that script using the browser's Web Speech API
  (`SpeechSynthesis`) — client-side, free, no audio model.

This respects the hard model constraint (the reasoning models are text-only;
multimodal is out of scope here): the *speech* is produced in the browser, the
*text* is produced by the model, so nothing depends on an audio model. Voice
**input** (dictation) is a documented next step.

---

## Setup

```bash
git clone <this-repo>
cd inclusive-certification-coach

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then fill in your Foundry values
```

Run the demo UI:

```bash
streamlit run app/streamlit_app.py
```

---

## Data sources

All synthetic.

- `data/knowledge_base/` — certification guides used for grounded retrieval via Foundry IQ (e.g. `az204_enablement_guide.md`, source id `KB-AZ204-001`).
- `data/synthetic/team_records.json` — fabricated team (`TEAM-A`) of learner records (`L-1001` / `EMP-001` …) consumed by the Manager Insights agent.

Identifiers are fabricated for demonstration only. No real people, no PII.

---

## Responsible AI

- Synthetic data only; no PII.
- Citations required on all grounded answers.
- Human-in-the-loop on advancement decisions.
- Users are told they are interacting with AI.

---

## Evaluation

Gold-set evals validate what matters on the Reasoning track:

- **`decisions`** — orchestrator reasoning accuracy across 6 gold cases (advance / loop / escalate, including the accommodation-aware supportive-loop branch).
- **`groundedness`** — citation fidelity for Curator, Study Plan Generator, and Assessment: agents emit only KB-backed skill areas / study hours, schedules respect the stated daily load, every grounded item cited.
- **`manager`** — Manager Insights team rollup: every learner covered, valid statuses, the ready set and team readiness % match the threshold ground truth, stalled learners flagged for human support.
- **`accessibility`** — the Accessibility Narrator's spoken output is screen-reader friendly: no markdown/tables, no raw `%`, abbreviations spelled out.

```bash
python -m evals.run_evals                       # all suites
python -m evals.run_evals --suite decisions     # reasoning only, no Search resource needed
python -m evals.run_evals --suite manager       # reasoning only, no Search resource needed
```

See [`evals/README.md`](evals/README.md) for details; results land in `evals/results/latest.json`.
