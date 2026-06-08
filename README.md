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
| Learning Path Curator | workflow step | Map a certification goal to skills + cited modules, with per-module accommodation notes | Foundry IQ |
| Assessment Agent | workflow step | Generate grounded, cited practice questions; score readiness; report weak areas | Foundry IQ |
| Orchestrator | reasoning loop | Reason over score, weak areas, history, and accessibility profile to decide: advance, loop back to weak areas, or escalate to a human | — |

The Curator already emits accommodation-aware pacing per module, so a separate
Study Plan Generator agent is a planned stretch, not part of the current loop.

**Microsoft IQ layer:** Foundry IQ (Azure AI Search), grounded retrieval with citations.

```
Learner goal (cert + role + accessibility profile)
   -> Curator        : Foundry IQ retrieval -> cited, accommodation-aware learning path
      -> Assessment  : Foundry IQ retrieval -> cited questions -> score + weak areas
         -> Orchestrator (reasoning model): given score + weak areas + attempt
            history + accessibility profile, decide
               advance         (ready)
               loop            (not ready -> revisit only the weak areas)
               escalate        (repeated failure -> human coach)
   -> every step appended to a visible reasoning trace shown in the UI
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

All synthetic. `data/knowledge_base/` holds the certification guides used for grounded retrieval via Foundry IQ (e.g. `az204_enablement_guide.md`, source id `KB-AZ204-001`). Identifiers like `L-1001` / `EMP-001` / `TEAM-A` are fabricated for demonstration only. No real people, no PII.

---

## Responsible AI

- Synthetic data only; no PII.
- Citations required on all grounded answers.
- Human-in-the-loop on advancement decisions.
- Users are told they are interacting with AI.

---

## Evaluation

Gold-set evals validate the two things that matter on the Reasoning track:

- **`decisions`** — orchestrator reasoning accuracy across 6 gold cases (advance / loop / escalate, including the accommodation-aware supportive-loop branch). Currently **6/6**.
- **`groundedness`** — citation fidelity: agents emit only KB-backed skill areas and study hours, every grounded item cited. Currently **7/7**.

```bash
python -m evals.run_evals             # both suites
python -m evals.run_evals --suite decisions   # no Search resource needed
```

See [`evals/README.md`](evals/README.md) for details; results land in `evals/results/latest.json`.
