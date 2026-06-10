"""
Orchestrator - the reasoning loop.

Coordinates the workflow agents (Curator, Study Plan, Assessment) and makes
the genuinely agentic decision: given the assessment result, the weak areas,
and the learner's history, decide whether to ADVANCE, LOOP back to weak areas,
or ESCALATE to a human. It reasons over the signals rather than using a
hardcoded threshold, and records a step-by-step trace so the UI can show the
reasoning.

Two safety properties:
- The LLM's decision passes through deterministic guardrails (_apply_guardrails)
  so safety-critical invariants hold even if the model misfires.
- run() executes a REAL bounded loop: a "loop" decision re-curates only the
  weak areas, re-plans lighter, re-assesses, and feeds the grown history back
  into the next decision - capped at max_attempts.
"""

import json
from src.foundry_client import chat_json
from src.config import settings
from src.agents.curator import curate
from src.agents.study_planner import generate_study_plan
from src.agents.assessor import generate_assessment, score_assessment

VALID_ACTIONS = {"advance", "loop", "escalate"}

DECISION_PROMPT = """You are the Orchestrator of an accessibility-first \
certification coach. Decide the learner's next step.

Inputs: the assessment result (score, weak areas, ready flag), the learner's
attempt history, and their accessibility profile.

Decide ONE action:
- "advance": learner is ready; recommend the next step.
- "loop": learner is not ready; send them back to study ONLY the weak areas.
- "escalate": learner has made 3+ attempts with little improvement, or shows a
  pattern that needs a human coach.

Be accommodation-aware: if the learner's profile notes focus/cognitive
difficulties and they are close or clearly improving, prefer a supportive
"loop" with lighter pacing over "escalate".

Output ONLY valid JSON:
{
  "action": "<advance|loop|escalate>",
  "reason": "<one or two sentences explaining the decision>",
  "signals_considered": ["<3-5 short bullets: the evidence you weighed, e.g.
                          'score 67% is below the 75% readiness target',
                          'improving trend: 60 -> 67 across 2 attempts'>"],
  "alternatives_rejected": ["<for each action you did NOT take, one short
                             clause on why not>"],
  "focus_next": ["<weak skill areas to revisit, empty if advancing>"],
  "message_to_learner": "<short, plain-language, encouraging>"
}
No preamble. JSON only."""


def _stalled(history: list[dict]) -> bool:
    """3+ attempts with little improvement across the last three scores."""
    if len(history) < 3:
        return False
    scores = [h.get("score_pct", 0) for h in history[-3:]]
    return scores[-1] - scores[0] < 10


def _apply_guardrails(decision: dict, assessment_result: dict,
                      history: list[dict]) -> dict:
    """
    Deterministic rails around the LLM decision. The model reasons freely, but
    these invariants must hold no matter what it returns:
      1. action is a valid enum value;
      2. a stalled learner (3+ attempts, little improvement, not ready) always
         reaches a human - never silently loops forever;
      3. advancing leaves nothing to revisit; looping always names what to
         revisit (falling back to the scored weak areas).
    Any correction is recorded in "guardrail_notes" so it stays visible.
    """
    notes = []
    ready = bool(assessment_result.get("ready"))
    weak = assessment_result.get("weak_areas", [])

    action = decision.get("action")
    if action not in VALID_ACTIONS:
        decision["action"] = "advance" if ready else "loop"
        notes.append(f"invalid action {action!r} from model; "
                     f"defaulted to {decision['action']!r}")

    if not ready and _stalled(history) and decision["action"] != "escalate":
        notes.append(f"overrode {decision['action']!r}: 3+ attempts with "
                     "little improvement must reach a human coach")
        decision["action"] = "escalate"

    if decision["action"] == "advance" and decision.get("focus_next"):
        decision["focus_next"] = []
        notes.append("cleared focus_next: advancing learners have nothing to revisit")
    if decision["action"] == "loop" and not decision.get("focus_next"):
        decision["focus_next"] = list(weak)
        notes.append("focus_next was empty on a loop; filled from scored weak areas")

    decision.setdefault("signals_considered", [])
    decision.setdefault("alternatives_rejected", [])
    decision["guardrail_notes"] = notes
    return decision


def decide(assessment_result: dict, history: list[dict],
           accessibility_profile: str) -> dict:
    """The orchestrator's reasoning decision, with deterministic guardrails."""
    user_msg = (
        f"ASSESSMENT RESULT:\n{json.dumps(assessment_result, indent=2)}\n\n"
        f"ATTEMPT HISTORY:\n{json.dumps(history, indent=2)}\n\n"
        f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
        f"Decide the next action. JSON only."
    )
    decision = chat_json(
        [
            {"role": "system", "content": DECISION_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        model=settings.MODEL_REASONING,  # use the reasoning model for the decision
    )
    return _apply_guardrails(decision, assessment_result, history)


def run(certification: str, role: str, accessibility_profile: str,
        answer_fn, history: list[dict] | None = None,
        max_attempts: int = 3) -> dict:
    """
    Run the FULL reasoning loop until the orchestrator advances, escalates,
    or max_attempts is reached.

    answer_fn(questions) -> {"Q1": "B", ...}: supplies the learner's answers
    for each assessment round (a UI would gather these interactively; the CLI
    demo simulates them).

    Returns the final state plus a step-by-step reasoning trace covering every
    iteration, so the loop itself is legible.
    """
    history = list(history or [])
    trace = []
    focus_areas: list[str] | None = None
    decision = path = study_plan = assessment = result = None

    for attempt in range(len(history) + 1, max_attempts + 1):
        loop_tag = f"attempt {attempt}" + (f", focused on {focus_areas}" if focus_areas else "")

        # Step 1 - Curator (full path first time; weak areas only on a loop)
        path = curate(certification, role, accessibility_profile, focus_areas=focus_areas)
        trace.append({"agent": "Learning Path Curator",
                      "did": f"[{loop_tag}] Built a {path.get('total_hours', 0)}h grounded path "
                             f"({len(path.get('modules', []))} modules), cited to source docs.",
                      "retrieved": path.get("_retrieval", [])})

        # Step 2 - Study Plan Generator: schedule it, accommodation-aware
        study_plan = generate_study_plan(path, accessibility_profile,
                                         remediation=focus_areas is not None)
        trace.append({"agent": "Study Plan Generator",
                      "did": f"[{loop_tag}] Scheduled {len(study_plan.get('sessions', []))} sessions "
                             f"over {study_plan.get('total_days', '?')} days "
                             f"({study_plan.get('block_minutes', '?')}-min blocks).",
                      "retrieved": study_plan.get("_retrieval", [])})

        # Step 3 - Assessment: generate + score
        assessment = generate_assessment(certification, role, num_questions=3,
                                         focus_areas=focus_areas)
        result = score_assessment(assessment["questions"], answer_fn(assessment["questions"]))
        trace.append({"agent": "Assessment Agent",
                      "did": f"[{loop_tag}] Scored learner: {result.get('score_pct')}% "
                             f"(ready={result.get('ready')}), weak areas: {result.get('weak_areas')}.",
                      "retrieved": assessment.get("_retrieval", [])})

        # Step 4 - Orchestrator decision (the reasoning step)
        history.append({"attempt": attempt, "score_pct": result.get("score_pct")})
        decision = decide(result, history, accessibility_profile)
        trace.append({"agent": "Orchestrator (reasoning)",
                      "did": f"[{loop_tag}] Decision: {decision['action'].upper()} — {decision['reason']}",
                      "decision_detail": decision})

        if decision["action"] != "loop":
            break
        focus_areas = decision["focus_next"] or None  # next iteration: weak areas only

    return {
        "learning_path": path,
        "study_plan": study_plan,
        "assessment": assessment,
        "result": result,
        "decision": decision,
        "history": history,
        "trace": trace,
    }


if __name__ == "__main__":
    # Demo: a learner with ADHD who improves each round - watch the loop run.
    _round = {"n": 0}

    def improving_learner(questions):
        """Round 1: two wrong. Round 2: one wrong. Round 3: all correct."""
        _round["n"] += 1
        wrong = max(0, 3 - _round["n"])
        return {q["id"]: ("Z" if i < wrong else q["correct_option"])
                for i, q in enumerate(questions)}

    out = run(
        certification="AZ-204",
        role="Cloud Engineer",
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
        answer_fn=improving_learner,
    )

    print("=== REASONING TRACE ===")
    for i, step in enumerate(out["trace"], 1):
        print(f"{i}. [{step['agent']}] {step['did']}")
    print("\n=== FINAL DECISION ===")
    print(json.dumps(out["decision"], indent=2))
