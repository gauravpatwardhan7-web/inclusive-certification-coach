# Inclusive Certification Coach

A multi-agent enterprise learning system for the **Microsoft Agents League — Reasoning Agents** track. It helps organisations run internal certification programmes, designed **accessibility-first** so that employees with disabilities (neurodivergent, cognitive, low-vision) get certification prep that adapts to how they actually work.

> **Status:** work in progress. **Data:** 100% synthetic — no real people, no PII (identifiers like `L-1001`, `EMP-001`, `TEAM-A`).

---

## Why this project

The challenge scenario is an enterprise certification-learning system. Most implementations treat every learner identically. Ours adds two things that matter:

1. **Inclusive by design** — study paths, pacing, and assessments adapt to cognitive load, focus windows, and accessible formats, instead of one-size-fits-all.
2. **A visible reasoning trace** — the UI shows *which agent did what, what it retrieved, what it cited, and why the orchestrator looped or advanced*. The track is about reasoning, so we make the reasoning legible.

---

## Architecture

| Agent | Type | Job | Grounding |
|---|---|---|---|
| Learning Path Curator | workflow step | Map a certification goal to skills + cited learning resources | Foundry IQ |
| Study Plan Generator | workflow step | Turn content into an accommodation-aware study schedule | synthetic work-signal data |
| Assessment Agent | workflow step | Generate grounded, cited practice questions; score readiness | Foundry IQ |
| Orchestrator | reasoning loop | Decide: advance, loop back to weak areas, or escalate | — |

**Microsoft IQ layer:** Foundry IQ (grounded retrieval with citations).

```
Learner goal
   -> Curator (cited learning path)
      -> Study Plan Generator (accommodation-aware schedule)
         -> Assessment Agent (cited questions + readiness score)
            -> Orchestrator: ready? -> advance | not ready? -> loop to weak areas
```

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

All synthetic. See `data/synthetic/` (learner records, work signals, semantic seed) and `data/knowledge_base/` (certification guides used for grounded retrieval). Fabricated for demonstration only.

---

## Responsible AI

- Synthetic data only; no PII.
- Citations required on all grounded answers.
- Human-in-the-loop on advancement decisions.
- Users are told they are interacting with AI.

---

## Evaluation

See `evals/` for the gold test sets and metrics used to validate grounding, citation fidelity, and orchestration decisions.
