"""
Agent 1 - Learning Path Curator.

Given a certification goal, a role, and an optional accessibility profile,
it returns a structured, GROUNDED learning path: every module is drawn from
the provided knowledge-base content and cites its source ID. It must not
invent skills or sources that are absent from the grounding context.
"""

import json
from src.foundry_client import chat
from src.knowledge import load_knowledge_base

SYSTEM_PROMPT = """You are the Learning Path Curator in an accessibility-first \
enterprise certification system.

Your job: turn a certification goal + role into a structured learning path,
grounded ONLY in the provided knowledge-base content.

Hard rules:
- Use ONLY skills, hours, and guidance found in the KNOWLEDGE BASE below.
- Never invent a skill area, study hour figure, or source that is not present.
- Every module MUST include a "source_id" copied from the knowledge base.
- If the learner has an accessibility profile, adapt the "accommodation_note"
  for each module using the knowledge base's accessibility guidance.
- If the knowledge base lacks the requested certification, return an empty
  "modules" list and explain in "note".

Output ONLY valid JSON in this shape:
{
  "certification": "<id>",
  "role": "<role>",
  "modules": [
    {
      "skill_area": "<from KB>",
      "recommended_hours": <number from KB>,
      "accommodation_note": "<accessibility-aware guidance>",
      "source_id": "<KB source id>"
    }
  ],
  "total_hours": <sum>,
  "note": "<any caveat, else empty string>"
}
No preamble. JSON only."""


def curate(certification: str, role: str, accessibility_profile: str = "none") -> dict:
    """Produce a grounded, accessibility-aware learning path as a dict."""
    knowledge_base = load_knowledge_base()
    user_msg = (
        f"KNOWLEDGE BASE:\n{knowledge_base}\n\n"
        f"LEARNER REQUEST:\n"
        f"- Certification goal: {certification}\n"
        f"- Role: {role}\n"
        f"- Accessibility profile: {accessibility_profile}\n\n"
        f"Produce the grounded learning path JSON now."
    )
    raw = chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
    )
    # Strip code fences if the model wrapped the JSON.
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


if __name__ == "__main__":
    result = curate(
        certification="AZ-204",
        role="Cloud Engineer",
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
    )
    print(json.dumps(result, indent=2))
