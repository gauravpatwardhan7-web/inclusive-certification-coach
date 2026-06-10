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

    Raises if the index returns a chunk without a usable source id - the whole
    system's promise is "every claim cited", so an uncitable chunk means the
    index is misconfigured and we fail loudly rather than ground on it.
    """
    results = _client.search(search_text=query, top=top)
    chunks = []
    for r in results:
        text = r.get("snippet") or r.get("content") or r.get("text") or ""
        source = r.get("snippet_parent_id") or r.get("uid")
        if not source:
            raise RuntimeError(
                "Retrieved a chunk with no source id - the search index is "
                "missing citation fields (snippet_parent_id / uid). "
                f"Chunk text starts: {text[:80]!r}"
            )
        chunks.append({
            "text": text,
            "source_id": source,
            "score": round(float(r.get("@search.score", 0.0)), 3),
        })
    return chunks


def retrieve_with_context(query: str, top: int = 4) -> tuple[str, list[dict]]:
    """
    Retrieve chunks and also format them as a grounding block for a prompt.

    Returns (context_text, chunks) so agents can both ground the model AND
    surface what was retrieved in the visible reasoning trace.
    """
    chunks = retrieve(query, top=top)
    blocks = [f"[source_id: {c['source_id']}]\n{c['text']}" for c in chunks]
    context = "\n\n".join(blocks) if blocks else "(no relevant knowledge found)"
    return context, chunks


def retrieve_as_context(query: str, top: int = 4) -> str:
    """Format retrieved chunks as a grounding block for a prompt."""
    return retrieve_with_context(query, top=top)[0]


if __name__ == "__main__":
    for c in retrieve("AZ-204 storage recommended study hours", top=2):
        print(c["score"], c["source_id"], "::", c["text"][:120].replace("\n", " "))
