"""Shared knowledge-base loader used by all grounded agents."""

from pathlib import Path

KB_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge_base"


def load_knowledge_base() -> str:
    """Concatenate all knowledge-base documents into one grounding context."""
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        docs.append(f"--- DOCUMENT: {path.name} ---\n{path.read_text()}")
    return "\n\n".join(docs)
