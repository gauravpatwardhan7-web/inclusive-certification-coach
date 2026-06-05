"""
Grounded retrieval via Foundry IQ (Azure AI Search).

This replaces the naive "dump the whole document into the prompt" approach.
Given a query, it asks the Foundry IQ index for only the most relevant chunks
and returns them with their source IDs, so agents can ground + cite precisely.
"""

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from src.config import settings

_client = SearchClient(
    endpoint=settings.SEARCH_ENDPOINT,
    index_name=settings.SEARCH_INDEX,
    credential=AzureKeyCredential(settings.SEARCH_KEY),
)


def retrieve(query: str, top: int = 4) -> list[dict]:
    """
    Return the top relevant chunks for a query.

    Each result: {"text": <chunk text>, "source_id": <citation id>, "score": <relevance>}
    """
    results = _client.search(search_text=query, top=top)
    chunks = []
    for r in results:
        text = r.get("snippet") or r.get("content") or r.get("text") or ""
        source = r.get("snippet_parent_id") or r.get("uid") or "unknown-source"
        chunks.append({
            "text": text,
            "source_id": source,
            "score": r.get("@search.score", 0.0),
        })
    return chunks


def retrieve_as_context(query: str, top: int = 4) -> str:
    """Format retrieved chunks as a grounding block for a prompt."""
    chunks = retrieve(query, top=top)
    blocks = [
        f"[source_id: {c['source_id']}]\n{c['text']}"
        for c in chunks
    ]
    return "\n\n".join(blocks) if blocks else "(no relevant knowledge found)"


if __name__ == "__main__":
    for c in retrieve("AZ-204 storage recommended study hours", top=2):
        print(round(c["score"], 2), c["source_id"], "::", c["text"][:120].replace("\n", " "))
