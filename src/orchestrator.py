"""
Orchestrator - the reasoning loop.

Coordinates the workflow agents (Curator, Assessment) and makes the one
genuinely agentic decision: given the assessment result, the weak areas, and
the learner's history, decide whether to ADVANCE, LOOP back to weak areas, or
ESCALATE to a human. It reasons over the signals rather than using a hardcoded
threshold, and records a step-by-step trace so the UI can show the reasoning.
"""

import json
from src.foundry_client import chat
from src.config import settings
from src.agents.curator import curate
from src.agents.assessor import generate_assessment, score_assessment

DECISION_PROMPT = """You are the Orchestrator of an accessibility-first \
certification coach. Decide the learner's next step.

Inputs: the assessment result (score, weak areas, ready flag), the learner's
attempt history, and their accessibility profile.

Decide ONE action:
- "advance": learner is ready; recommend the next step.
- "loop": learner is not ready; send them back to study ONLY the weak areas.
- "escalate": learner has failed repeatedly (3+ attempts) or shows a pattern
  that needs a human coach.

Be accommodation-aware: if the learner's profile notes focus/cognitive
difficulties and they are close, prefer a supportive "loop" with lighter pacing
over "escalate".

Output ONLY valid JSON:
{
  "action": "<advance|loop|escalate>",
  "reason": "<one or two sentences explaining the decision>",
  "focus_next": ["<weak skill areas to revisit, empty if advancing>"],
  "message_to_learner": "<short, plain-language, encouraging>"
}
No preamble. JSON only."""


def _decide(assessment_result: dict, history: list[dict], accessibility_profile: str) -> dict:
    user_msg = (
        f"ASSESSMENT RESULT:\n{json.dumps(assessment_result, indent=2)}\n\n"
        f"ATTEMPT HISTORY:\n{json.dumps(history, indent=2)}\n\n"
        f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
        f"Decide the next action. JSON only."
    )
    raw = chat(
        [
            {"role": "system", "content": DECISION_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        model=settings.MODEL_REASONING,  # use the reasoning model for the decision
    )
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def run(certification: str, role: str, accessibility_profile: str,
        learner_answers: dict, history: list[dict] | None = None) -> dict:
    """
    Run one full cycle and return the result plus a step-by-step reasoning trace.
    """
    history = history or []
    trace = []

    # Step 1 - Curator
    path = curate(certification, role, accessibility_profile)
    trace.append({"agent": "Learning Path Curator",
                  "did": f"Built a {path['total_hours']}h grounded learning path "
                         f"({len(path['modules'])} modules), cited to source docs."})

    # Step 2 - Assessment: generate
    assessment = generate_assessment(certification, role, num_questions=3)
    trace.append({"agent": "Assessment Agent",
                  "did": f"Generated {len(assessment['questions'])} grounded, cited questions."})

    # Step 3 - Assessment: score
    result = score_assessment(assessment["questions"], learner_answers)
    trace.append({"agent": "Assessment Agent",
                  "did": f"Scored learner: {result['score_pct']}% "
                         f"(ready={result['ready']}), weak areas: {result['weak_areas']}."})

    # Step 4 - Orchestrator decision (the reasoning step)
    history = history + [{"attempt": len(history) + 1, "score_pct": result["score_pct"]}]
    decision = _decide(result, history, accessibility_profile)
    trace.append({"agent": "Orchestrator (reasoning)",
                  "did": f"Decision: {decision['action'].upper()} — {decision['reason']}"})

    return {
        "learning_path": path,
        "assessment": assessment,
        "result": result,
        "decision": decision,
        "history": history,
        "trace": trace,
    }


if __name__ == "__main__":
    # Demo: a learner with ADHD who gets the first question wrong -> should LOOP.
    a = generate_assessment("AZ-204", "Cloud Engineer", num_questions=3)
    qs = a["questions"]
    answers = {q["id"]: ("Z" if i == 0 else q["correct_option"]) for i, q in enumerate(qs)}

    out = run(
        certification="AZ-204",
        role="Cloud Engineer",
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
        learner_answers=answers,
    )

    print("=== REASONING TRACE ===")
    for i, step in enumerate(out["trace"], 1):
        print(f"{i}. [{step['agent']}] {step['did']}")
    print("\n=== DECISION ===")
    print(json.dumps(out["decision"], indent=2))
