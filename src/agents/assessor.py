"""
Agent 2 - Assessment Agent.

Generates grounded, cited practice questions from the knowledge base, then
scores a learner's answers and reports readiness + weak skill areas. Every
question cites the source it was drawn from; nothing is invented.
"""

import json
from src.foundry_client import chat
from src.knowledge import load_knowledge_base

GENERATE_PROMPT = """You are the Assessment Agent in an accessibility-first \
enterprise certification system.

Generate practice questions grounded ONLY in the provided knowledge base.

Hard rules:
- Each question must test a skill area that appears in the knowledge base.
- Each question must include the correct answer and the "source_id" it came from.
- Use plain, screen-reader-friendly language. No images, no "see figure".
- Do not invent facts beyond the knowledge base.

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


def _parse(raw: str) -> dict:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def generate_assessment(certification: str, role: str, num_questions: int = 3) -> dict:
    """Produce grounded, cited practice questions."""
    kb = load_knowledge_base()
    user_msg = (
        f"KNOWLEDGE BASE:\n{kb}\n\n"
        f"Generate {num_questions} questions for certification {certification} "
        f"(role: {role}). Cover different skill areas. JSON only."
    )
    return _parse(chat([
        {"role": "system", "content": GENERATE_PROMPT},
        {"role": "user", "content": user_msg},
    ]))


def score_assessment(questions: list[dict], answers: dict) -> dict:
    """Score learner answers. answers = {"Q1": "B", "Q2": "A", ...}."""
    user_msg = (
        f"QUESTIONS (with correct options):\n{json.dumps(questions, indent=2)}\n\n"
        f"LEARNER ANSWERS:\n{json.dumps(answers, indent=2)}\n\n"
        f"Score now. JSON only."
    )
    return _parse(chat([
        {"role": "system", "content": SCORE_PROMPT},
        {"role": "user", "content": user_msg},
    ]))


if __name__ == "__main__":
    a = generate_assessment("AZ-204", "Cloud Engineer", num_questions=3)
    print(json.dumps(a, indent=2))
    # Simulate a learner who answers the first wrong, rest correct.
    qs = a["questions"]
    sim = {q["id"]: ("Z" if i == 0 else q["correct_option"]) for i, q in enumerate(qs)}
    print("\nLEARNER ANSWERS:", sim)
    print(json.dumps(score_assessment(qs, sim), indent=2))
