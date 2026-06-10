"""
Agent 7 - Teach-back Assessor (Socratic mode).

Multiple choice measures recognition; explaining a concept in your own words
measures understanding. In teach-back mode the learner EXPLAINS a skill area
and this agent grades the explanation against the knowledge base:

- which required concepts the explanation covered;
- which it missed (the specific gap, not just "wrong");
- any misconception that needs correcting before it calcifies;
- and ONE Socratic follow-up question aimed at the biggest gap.

The rubric is grounded: concepts come from the KB chunks, not the model's
imagination, and the evaluation carries a source_id like every other grounded
output in the system. The final result converts into the same shape as an
MCQ assessment result, so the Orchestrator reasons over teach-back history
exactly as it does over quiz scores.

This mode is also the accessible one: no grid of options to visually scan,
works typed or dictated, and feedback is plain language.
"""

import json
from src.foundry_client import chat_json
from src.retrieval import retrieve_with_context

EVALUATE_PROMPT = """You are the Teach-back Assessor in an accessibility-first \
enterprise certification system. A learner has explained a skill area in their
own words. Grade the UNDERSTANDING, not the prose.

Ground rules:
- Derive the required concepts ONLY from the provided knowledge base. Do not
  invent requirements the KB does not support.
- Judge meaning, not vocabulary: accept synonyms and plain language. Never
  penalise spelling, grammar, or short sentences - many learners dictate or
  use assistive tech.
- Identify at most ONE misconception: something the learner stated that is
  actually wrong (not merely missing). Empty string if none.
- Ask exactly ONE follow-up question, aimed at the single most important gap
  (or, if nothing is missing, a question that probes one level deeper).
  Plain language, answerable in 2-3 sentences, no trick questions.
- "understanding_pct": 0-100. Full coverage of the KB's core ideas with no
  misconception scores 80+; a fundamentally wrong explanation scores below 30.
- "feedback": 2-3 warm, specific sentences. Lead with what they got RIGHT.

If a PREVIOUS FOLLOW-UP exchange is provided, this is the second round: fold
the follow-up answer into the final grade.

Output ONLY valid JSON:
{
  "skill_area": "<the skill area assessed>",
  "understanding_pct": <0-100 integer>,
  "concepts_covered": ["<concept from the KB the learner explained correctly>"],
  "concepts_missing": ["<concept from the KB the explanation did not cover>"],
  "misconception": "<one sentence, or empty string>",
  "follow_up_question": "<one plain-language question>",
  "feedback": "<2-3 sentences, lead with strengths>",
  "source_id": "<KB source id the rubric came from>"
}
No preamble. JSON only."""


def evaluate_teachback(certification: str, skill_area: str, explanation: str,
                       accessibility_profile: str = "none",
                       follow_up_question: str = "",
                       follow_up_answer: str = "") -> dict:
    """
    Grade a learner's own-words explanation of a skill area against the KB.

    Call once with just the explanation (round 1), then again with the
    follow_up exchange to fold the probe into the final grade (round 2).
    """
    kb, chunks = retrieve_with_context(f"{certification} {skill_area} key concepts")
    follow_block = ""
    if follow_up_question and follow_up_answer:
        follow_block = (
            f"PREVIOUS FOLLOW-UP QUESTION: {follow_up_question}\n"
            f"LEARNER'S FOLLOW-UP ANSWER: {follow_up_answer}\n\n"
        )
    user_msg = (
        f"KNOWLEDGE BASE:\n{kb}\n\n"
        f"CERTIFICATION: {certification}\n"
        f"SKILL AREA BEING EXPLAINED: {skill_area}\n"
        f"ACCESSIBILITY PROFILE: {accessibility_profile}\n\n"
        f"{follow_block}"
        f"LEARNER'S EXPLANATION:\n{explanation}\n\n"
        f"Grade the understanding. JSON only."
    )
    evaluation = chat_json([
        {"role": "system", "content": EVALUATE_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    evaluation["_retrieval"] = [
        {"source_id": c["source_id"], "score": c["score"],
         "snippet": c["text"][:160]}
        for c in chunks
    ]
    return evaluation


def to_assessment_result(evaluation: dict, ready_threshold: int = 75) -> dict:
    """
    Convert a teach-back evaluation into the same shape as an MCQ assessment
    result, so the Orchestrator reasons over it identically.
    """
    pct = int(evaluation.get("understanding_pct", 0))
    skill = evaluation.get("skill_area", "?")
    ready = pct >= ready_threshold
    return {
        "total": 1,
        "correct": 1 if ready else 0,
        "score_pct": pct,
        "per_skill": [{"skill_area": skill,
                       "result": "correct" if ready else "incorrect"}],
        "weak_areas": [] if ready else [skill],
        "ready": ready,
        "mode": "teach-back",
        "concepts_missing": evaluation.get("concepts_missing", []),
        "misconception": evaluation.get("misconception", ""),
    }


if __name__ == "__main__":
    out = evaluate_teachback(
        certification="AZ-204",
        skill_area="Implement Azure security (auth, Key Vault)",
        explanation=(
            "Azure security for apps means you don't put secrets in your code. "
            "You keep connection strings and keys in Key Vault and your app "
            "reads them at runtime."
        ),
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
    )
    print(json.dumps({k: v for k, v in out.items() if k != "_retrieval"}, indent=2))
