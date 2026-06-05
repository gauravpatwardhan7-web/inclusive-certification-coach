"""
Central configuration loader.

Reads secrets and settings from the .env file (never hardcoded, never committed)
and exposes them to the rest of the app through a single Settings object.
"""

import os
from dotenv import load_dotenv

# Load variables from .env into the environment.
load_dotenv()


class Settings:
    """Typed access to environment configuration."""

    # Azure Foundry / OpenAI endpoints + key
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_AI_API_KEY: str = os.getenv("AZURE_AI_API_KEY", "")
    AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

    # Model deployment names (must match what is deployed in Foundry)
    MODEL_DEFAULT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
    MODEL_REASONING: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_REASONING", "o4-mini")

    # Foundry IQ / Azure AI Search (grounded retrieval)
    SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    SEARCH_KEY: str = os.getenv("AZURE_SEARCH_KEY", "")
    SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "cert-guides-index")

    def validate(self) -> None:
        """Fail loudly at startup if required secrets are missing."""
        missing = [
            name
            for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_AI_API_KEY")
            if not getattr(self, name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required config: {', '.join(missing)}. "
                "Copy .env.example to .env and fill in your Foundry values."
            )


settings = Settings()
