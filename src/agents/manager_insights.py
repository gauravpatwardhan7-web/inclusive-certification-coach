"""
Agent 5 - Manager Insights.

Rolls up a team's certification progress for a manager: who is ready, who is at
risk, who needs human support, the team's overall readiness, and recommended
next actions. It reasons over each learner's score history, attempts, weak
areas, and accessibility profile against the readiness threshold - it does not
just sort by latest score.

Data is synthetic (data/synthetic/team_records.json). No PII.
"""

import json
from pathlib import Path
from src.foundry_client import chat
from src.config import settings

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "team_records.json"

SYSTEM_PROMPT = """You are the Manager Insights agent in an accessibility-first \
enterprise certification system. You produce a fair, supportive team-readiness
rollup for a people manager.

You are given a team's synthetic learner records and the readiness threshold.
For EACH learner, classify status by reasoning over the WHOLE picture, not just
the latest score:
- "ready": latest score is at or above the threshold.
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
  "team_readiness_pct": <0-100 integer = percent of learners "ready">,
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


def _parse(raw: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def load_team(path: Path = DATA) -> dict:
    return json.loads(path.read_text())


def team_insights(team: dict | None = None) -> dict:
    """Produce a manager-facing team-readiness rollup."""
    team = team or load_team()
    user_msg = (
        f"READINESS THRESHOLD: {team['readiness_threshold_pct']}%\n\n"
        f"TEAM RECORDS (synthetic):\n{json.dumps(team, indent=2)}\n\n"
        f"Produce the manager rollup JSON now."
    )
    return _parse(chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        model=settings.MODEL_REASONING,  # reasoning model: this is an analysis task
    ))


if __name__ == "__main__":
    print(json.dumps(team_insights(), indent=2))
