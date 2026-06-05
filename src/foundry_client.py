"""
Thin wrapper around the Azure Foundry (Azure OpenAI v1) chat endpoint.

Every agent calls the model through this one function, so model access,
endpoint, and auth live in a single place.
"""

from openai import OpenAI
from src.config import settings

# The Azure OpenAI "/openai/v1" endpoint is OpenAI-SDK compatible:
# point the standard client at it with the API key.
_client = OpenAI(
    base_url=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_AI_API_KEY,
)


def chat(messages: list[dict], model: str | None = None) -> str:
    """
    Send a list of chat messages to the model and return the text reply.

    messages: e.g. [{"role": "system", "content": "..."},
                    {"role": "user", "content": "..."}]
    model:    deployment name; defaults to the primary model from config.
    """
    settings.validate()
    response = _client.chat.completions.create(
        model=model or settings.MODEL_DEFAULT,
        messages=messages,
    )
    return response.choices[0].message.content or ""
