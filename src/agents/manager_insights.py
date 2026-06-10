"""
Agent 5 - Manager Insights.

Rolls up a team's certification progress for a manager: who is ready, who is at
risk, who needs human support, the team's overall readiness, and recommended
next actions. It reasons over each learner's score history, attempts, weak
areas, and accessibility profile against the readiness threshold - it does not
just sort by latest score.

Hybrid design: the deterministic facts (who meets the threshold, the team
readiness percentage) are computed in Python and handed to the model, so the
LLM spends its reasoning on the qualitative part - trends, support needs, and
manager actions - not on arithmetic it could flake on.

Data is synthetic (data/synthetic/team_records.json). No PII.
"""

import json
from pathlib import Path
from src.foundry_client import chat_json
from src.config import settings

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "team_records.json"

SYSTEM_PROMPT = """You are the Manager Insights agent in an accessibility-first \
enterprise certification system. You produce a fair, supportive team-readiness
rollup for a people manager.

You are given a team's synthetic learner records, the readiness threshold, and
DETERMINISTIC FACTS computed in code (which learners meet the threshold, and
the team readiness percentage). Treat the deterministic facts as ground truth.

For EACH learner, classify status by reasoning over the WHOLE picture, not just
the latest score:
- "ready": the learner is in the deterministic ready set.
- "on_track": below threshold but improving across attempts and close.
- "at_risk": below threshold, stalled or only one low attempt.
- "needs_support": 3+ attempts with little improvement -> recommend a human coach.

Be accommodation-aware and fair: a learner with a stated accessibility profile
who is improving should be framed supportively (more time / lighter pacing),
never penalised. Use plain, respectful language a manager can act on. Do not
expose the accessibility profile as a judgement; reflect it only as a support need.

Output ONLY valid JSON:
{
  "team_id": "<id>",
  "certification": "<id>",
  "team_readiness_pct": <the deterministic percentage you were given>,
  "summary": "<2-3 sentence plain-language overview for the manager>",
  "learners": [
    {
      "learner_id": "<id>",
      "status": "<ready|on_track|at_risk|needs_support>",
      "rationale": "<one sentence on why>",
      "recommended_action": "<concrete next step for the manager>"
    }
  ],
  "team_actions": ["<1-3 prioritised actions across the team>"]
}
No preamble. JSON only."""


def load_team(path: Path = DATA) -> dict:
    return json.loads(path.read_text())


def compute_team_facts(team: dict) -> dict:
    """Deterministic rollup facts - computed in code, not left to the LLM."""
    threshold = team["readiness_threshold_pct"]
    ready = sorted(l["learner_id"] for l in team["learners"]
                   if l["latest_score_pct"] >= threshold)
    pct = round(100 * len(ready) / len(team["learners"]))
    return {"readiness_threshold_pct": threshold,
            "ready_learner_ids": ready,
            "team_readiness_pct": pct}


def team_insights(team: dict | None = None) -> dict:
    """Produce a manager-facing team-readiness rollup."""
    team = team or load_team()
    facts = compute_team_facts(team)
    user_msg = (
        f"DETERMINISTIC FACTS (computed in code - treat as ground truth):\n"
        f"{json.dumps(facts, indent=2)}\n\n"
        f"TEAM RECORDS (synthetic):\n{json.dumps(team, indent=2)}\n\n"
        f"Produce the manager rollup JSON now."
    )
    out = chat_json(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        model=settings.MODEL_REASONING,  # reasoning model: this is an analysis task
    )
    # Hybrid rail: the percentage is arithmetic, so code has the final word.
    out["team_readiness_pct"] = facts["team_readiness_pct"]
    return out


if __name__ == "__main__":
    print(json.dumps(team_insights(), indent=2))
