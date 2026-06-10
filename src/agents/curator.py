"""
Agent 1 - Learning Path Curator.

Given a certification goal, a role, and an optional accessibility profile,
it returns a structured, GROUNDED learning path: every module is drawn from
the provided knowledge-base content and cites its source ID. It must not
invent skills or sources that are absent from the grounding context.

When the orchestrator decides to LOOP, the curator is re-invoked with
focus_areas so the remediation path covers ONLY the weak skill areas.
"""

from src.foundry_client import chat_json
from src.retrieval import retrieve_with_context

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
- If the request lists FOCUS AREAS, include ONLY modules for those skill
  areas - this is a remediation path after a failed assessment.
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


def curate(certification: str, role: str, accessibility_profile: str = "none",
           focus_areas: list[str] | None = None) -> dict:
    """
    Produce a grounded, accessibility-aware learning path as a dict.

    focus_areas: when set (a remediation loop), restrict the path to only
    these weak skill areas.
    """
    # Foundry IQ retrieval: pull only the chunks relevant to this request.
    query = f"{certification} {role} skill areas recommended study hours accessibility guidance"
    if focus_areas:
        query += " " + " ".join(focus_areas)
    knowledge_base, chunks = retrieve_with_context(query)

    focus_block = ""
    if focus_areas:
        focus_block = (
            "FOCUS AREAS (remediation - include ONLY these skill areas):\n- "
            + "\n- ".join(focus_areas) + "\n\n"
        )
    user_msg = (
        f"KNOWLEDGE BASE:\n{knowledge_base}\n\n"
        f"{focus_block}"
        f"LEARNER REQUEST:\n"
        f"- Certification goal: {certification}\n"
        f"- Role: {role}\n"
        f"- Accessibility profile: {accessibility_profile}\n\n"
        f"Produce the grounded learning path JSON now."
    )
    path = chat_json([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    # Surface what was retrieved so the UI can show it in the reasoning trace.
    # Underscore-prefixed keys are metadata: stripped before narration.
    path["_retrieval"] = [
        {"source_id": c["source_id"], "score": c["score"],
         "snippet": c["text"][:160]}
        for c in chunks
    ]
    return path


if __name__ == "__main__":
    import json
    result = curate(
        certification="AZ-204",
        role="Cloud Engineer",
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
    )
    print(json.dumps(result, indent=2))
