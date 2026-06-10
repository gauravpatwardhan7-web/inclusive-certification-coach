"""
Thin wrapper around the Azure Foundry (Azure OpenAI v1) chat endpoint.

Every agent calls the model through this one place, so model access, endpoint,
auth, and JSON reliability (structured output + parse retry) live in a single
module instead of being re-implemented per agent.
"""

import json

from openai import OpenAI
from src.config import settings

# The Azure OpenAI "/openai/v1" endpoint is OpenAI-SDK compatible:
# point the standard client at it with the API key.
_client = OpenAI(
    base_url=settings.AZURE_OPENAI_ENDPOINT,
    api_key=settings.AZURE_AI_API_KEY,
)


def chat(messages: list[dict], model: str | None = None,
         json_mode: bool = False) -> str:
    """
    Send a list of chat messages to the model and return the text reply.

    messages:  e.g. [{"role": "system", "content": "..."},
                     {"role": "user", "content": "..."}]
    model:     deployment name; defaults to the primary model from config.
    json_mode: ask the endpoint to enforce valid-JSON output (structured
               output). Falls back to a plain call if the deployment
               rejects response_format.
    """
    settings.validate()
    kwargs: dict = {
        "model": model or settings.MODEL_DEFAULT,
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
        try:
            response = _client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception:
            # Some deployments reject response_format; degrade to plain text
            # and rely on chat_json's parse-and-retry.
            kwargs.pop("response_format")
    response = _client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _strip_fences(raw: str) -> str:
    return (raw.strip()
            .removeprefix("```json").removeprefix("```")
            .removesuffix("```").strip())


def chat_json(messages: list[dict], model: str | None = None,
              retries: int = 1) -> dict:
    """
    chat() that must return a parsed JSON object.

    Uses structured output where available, strips stray code fences, and on a
    parse failure re-prompts the model once with the error so a single
    malformed reply never crashes a live demo.
    """
    raw = chat(messages, model=model, json_mode=True)
    for attempt in range(retries + 1):
        try:
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError as e:
            if attempt == retries:
                raise
            raw = chat(
                messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user",
                     "content": f"That was not valid JSON ({e.msg} at char {e.pos}). "
                                "Resend the COMPLETE response as valid JSON only - "
                                "no preamble, no code fences."},
                ],
                model=model,
                json_mode=True,
            )
    raise RuntimeError("unreachable")
