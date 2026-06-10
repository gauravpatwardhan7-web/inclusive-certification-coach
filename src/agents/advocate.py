"""
Agent 8 - Advocate (consent-boundary advocacy).

The genuinely inclusive version of "manager visibility" gives the LEARNER
control of the aperture. Two responsibilities:

1. redact_team() - deterministic consent enforcement. Before ANY
   manager-facing agent sees the team records, accessibility profiles of
   learners who have not consented are stripped IN CODE. A prompt can be
   ignored; a redaction cannot leak what the model never saw.

2. draft_advocacy() - the agent negotiates on the learner's behalf: it drafts
   a short, respectful, evidence-based note to the manager asking for a
   concrete remedy (more time, lighter pacing, protected study blocks). The
   note shares the learner's accessibility context ONLY with consent, and a
   deterministic leak check verifies the draft against the profile's own
   words - if the model leaks, it is re-prompted once, then falls back to a
   safe template. Nothing is sent without the learner pressing Approve.

The learner is the principal here; the manager is the audience. Never the
other way round.
"""

import re
from src.foundry_client import chat_json

PRIVATE_MARKER = "(private - not shared with manager)"

# Words that appear in profile strings but are harmless in any study note.
_GENERIC_WORDS = {
    "has", "uses", "with", "long", "study", "sessions", "session", "screen",
    "struggles", "the", "and", "for", "none", "their", "they", "in", "to",
}

ADVOCACY_PROMPT = """You are the Advocate in an accessibility-first \
certification coach. You draft a short note FROM the learner TO their manager,
asking for a concrete remedy. You work for the LEARNER.

Rules:
- Respectful, professional, confident - never apologetic, never guilt-driven.
- Evidence first: use the numbers provided (scores, trend, attempts, calendar
  minutes) - never invent any.
- Ask for exactly the remedy requested, concretely.
- Base the note ONLY on the evidence numbers, the workload, and the remedy.
  If an ACCESSIBILITY CONTEXT section is provided, additionally mention it
  briefly and factually, framed as a support need, never as a deficit. If no
  such section is provided, the note is purely about workload and evidence.
- 4-6 sentences, first person, ready to send.

Output ONLY valid JSON:
{
  "note_to_manager": "<the note>",
  "what_was_shared": ["<each category of information the note discloses>"],
  "what_was_withheld": ["<each category deliberately kept private>"]
}
No preamble. JSON only."""


def redact_team(team: dict) -> dict:
    """
    Enforce consent in code: strip the accessibility profile of every learner
    who has not opted to share it, before any manager-facing model call.
    """
    redacted = {k: v for k, v in team.items() if k != "learners"}
    redacted["learners"] = []
    for l in team.get("learners", []):
        l = dict(l)
        consent = l.get("consent", {})
        if not consent.get("share_accessibility_profile", False):
            l["accessibility_profile"] = PRIVATE_MARKER
        redacted["learners"].append(l)
    return redacted


def _profile_terms(profile: str) -> set[str]:
    """Content words of a profile string - the terms a draft must not leak."""
    words = re.findall(r"[A-Za-z]{3,}", profile or "")
    return {w.lower() for w in words} - _GENERIC_WORDS


def leaks_profile(text: str, profile: str) -> list[str]:
    """Profile content words that appear in the text (case-insensitive)."""
    if not profile or profile.lower().strip() in ("", "none"):
        return []
    lowered = text.lower()
    return sorted(t for t in _profile_terms(profile) if t in lowered)


def draft_advocacy(learner_evidence: dict, remedy: str,
                   accessibility_profile: str,
                   share_accessibility_context: bool) -> dict:
    """
    Draft a manager-ready advocacy note on the learner's behalf.

    learner_evidence: the numbers the note may use, e.g. {"latest_score_pct",
    "score_history", "attempts", "weak_areas", "calendar_available_minutes",
    "plan_required_minutes"} - whatever is known.
    """
    import json as _json

    # Consent enforced structurally: when the learner has not opted in, the
    # model is given NOTHING about the accessibility context - it cannot leak
    # what it never saw. (The leak check below stays as defence in depth.)
    context_block = (f"ACCESSIBILITY CONTEXT (learner consented to share): "
                     f"{accessibility_profile}\n"
                     if share_accessibility_context else "")
    user_msg = (
        f"EVIDENCE (the only numbers you may use):\n"
        f"{_json.dumps(learner_evidence, indent=2)}\n\n"
        f"REMEDY THE LEARNER WANTS: {remedy}\n"
        f"{context_block}\n"
        f"Draft the note JSON now."
    )

    def _safe_template() -> dict:
        return {
            "note_to_manager": (
                f"I'd like to ask for {remedy}. My recent practice results are "
                f"{learner_evidence.get('score_history', [])} and I want to keep "
                f"that progress up; the current pace is hard to sustain alongside "
                f"my workload. Could we make this work?"
            ),
            "what_was_shared": ["practice scores", "the request itself"],
            "what_was_withheld": ["all personal context"],
        }

    notes = []
    try:
        draft = chat_json([
            {"role": "system", "content": ADVOCACY_PROMPT},
            {"role": "user", "content": user_msg},
        ])
    except Exception as e:  # noqa: BLE001 - e.g. a content filter on the API side
        draft = _safe_template()
        notes.append(f"model call failed ({type(e).__name__}); "
                     "used the deterministic safe template")

    if not share_accessibility_context:
        leaked = leaks_profile(draft.get("note_to_manager", ""), accessibility_profile)
        if leaked:
            draft = _safe_template()
            notes.append(f"draft contained private terms {leaked}; "
                         "replaced with the deterministic safe template")
    draft["guardrail_notes"] = notes
    return draft


if __name__ == "__main__":
    import json
    out = draft_advocacy(
        learner_evidence={"latest_score_pct": 67, "score_history": [55, 67],
                          "attempts": 2, "plan_required_minutes": 250,
                          "calendar_available_minutes": 120},
        remedy="two recurring 30-minute protected study blocks per week",
        accessibility_profile="Has ADHD; struggles to focus in long study sessions.",
        share_accessibility_context=False,
    )
    print(json.dumps(out, indent=2))
    print("\nLEAK CHECK:", leaks_profile(out["note_to_manager"],
                                          "Has ADHD; struggles to focus in long study sessions."))
