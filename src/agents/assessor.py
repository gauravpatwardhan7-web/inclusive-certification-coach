"""
Agent 2 - Assessment Agent.

Generates grounded, cited practice questions from the knowledge base, then
scores a learner's answers and reports readiness + weak skill areas. Every
question cites the source it was drawn from; nothing is invented.

When the orchestrator decides to LOOP, it is re-invoked with focus_areas so
the retake targets ONLY the weak skill areas.
"""

import json
from src.foundry_client import chat_json
from src.retrieval import retrieve_with_context

GENERATE_PROMPT = """You are the Assessment Agent in an accessibility-first \
enterprise certification system. You write REALISTIC practice exam questions
that test whether a learner understands a skill area well enough to pass the
certification.

Each question must test one of the skill areas named in the knowledge base,
but the QUESTION ITSELF should be a genuine, practical exam-style question
about that area's concepts, services, and best practices - the kind that
appears on the real certification.

Hard rules:
- Test real understanding of the skill area (what a service does, when to use
  it, how it works). Write the kind of question a certification exam asks.
- NEVER ask about the study guide's metadata: do NOT ask how many study hours
  are recommended, what a skill area's exam weight/percentage is, how many
  modules there are, or anything about the guide document itself. Those are
  not exam topics - they are trivia about our planning doc.
- If the request lists FOCUS AREAS, every question must test one of those
  skill areas - this is a remediation retake.
- Anchor each question to the skill area it covers and set "source_id" to the
  knowledge-base source for that skill area.
- One clearly correct option and three plausible distractors.
- Use plain, screen-reader-friendly language. No images, no "see figure".
- Keep questions factually correct and uncontroversial for the technology.

Output ONLY valid JSON:
{
  "questions": [
    {
      "id": "Q1",
      "skill_area": "<from KB>",
      "question": "<plain-language question>",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct_option": "<A|B|C|D>",
      "source_id": "<KB source id>"
    }
  ]
}
No preamble. JSON only."""

SCORE_PROMPT = """You are the Assessment Agent scoring a learner's answers.

You are given the questions (with correct options) and the learner's answers.
Score objectively. A skill area is "weak" if the learner got its question wrong.

Output ONLY valid JSON:
{
  "total": <number of questions>,
  "correct": <number correct>,
  "score_pct": <0-100 integer>,
  "per_skill": [{"skill_area": "<...>", "result": "<correct|incorrect>"}],
  "weak_areas": ["<skill areas answered incorrectly>"],
  "ready": <true if score_pct >= 75 else false>
}
No preamble. JSON only."""


def generate_assessment(certification: str, role: str, num_questions: int = 3,
                        focus_areas: list[str] | None = None) -> dict:
    """Produce grounded, cited practice questions (optionally focused on weak areas)."""
    query = f"{certification} {role} skill areas exam topics study hours"
    if focus_areas:
        query += " " + " ".join(focus_areas)
    kb, chunks = retrieve_with_context(query)

    focus_block = ""
    if focus_areas:
        focus_block = (
            "FOCUS AREAS (remediation retake - test ONLY these):\n- "
            + "\n- ".join(focus_areas) + "\n\n"
        )
    user_msg = (
        f"KNOWLEDGE BASE:\n{kb}\n\n"
        f"{focus_block}"
        f"Generate {num_questions} questions for certification {certification} "
        f"(role: {role}). Cover different skill areas. JSON only."
    )
    assessment = chat_json([
        {"role": "system", "content": GENERATE_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    assessment["_retrieval"] = [
        {"source_id": c["source_id"], "score": c["score"],
         "snippet": c["text"][:160]}
        for c in chunks
    ]
    return assessment


def score_assessment(questions: list[dict], answers: dict) -> dict:
    """Score learner answers. answers = {"Q1": "B", "Q2": "A", ...}."""
    user_msg = (
        f"QUESTIONS (with correct options):\n{json.dumps(questions, indent=2)}\n\n"
        f"LEARNER ANSWERS:\n{json.dumps(answers, indent=2)}\n\n"
        f"Score now. JSON only."
    )
    return chat_json([
        {"role": "system", "content": SCORE_PROMPT},
        {"role": "user", "content": user_msg},
    ])


if __name__ == "__main__":
    a = generate_assessment("AZ-204", "Cloud Engineer", num_questions=3)
    print(json.dumps(a, indent=2))
    # Simulate a learner who answers the first wrong, rest correct.
    qs = a["questions"]
    sim = {q["id"]: ("Z" if i == 0 else q["correct_option"]) for i, q in enumerate(qs)}
    print("\nLEARNER ANSWERS:", sim)
    print(json.dumps(score_assessment(qs, sim), indent=2))
