"""LangChain chat-model factory shared by every FastSME product.

One place builds the ``BaseChatModel`` for all four supported providers, whether
the key comes from an org's BYOK credential or the deployment's house key.
Providers map onto LangChain integrations:

  - xai / openai  -> ``ChatOpenAI`` (xAI uses the OpenAI-compatible endpoint)
  - anthropic     -> ``ChatAnthropic``
  - google        -> ``ChatGoogleGenerativeAI`` (Gemini; optional dependency)

All heavy imports are lazy so ``import byok`` never requires LangChain until an
actual query runs.
"""
from __future__ import annotations

import os

# provider id -> display + defaults. Order defines the settings dropdown order.
PROVIDERS: dict[str, dict] = {
    "xai": {
        "label": "xAI (Grok)",
        "env": "XAI_API_KEY",
        "model": os.getenv("XAI_MODEL", "grok-4-1-fast-reasoning"),
        "base_url": os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
    },
    "openai": {
        "label": "OpenAI",
        "env": "OPENAI_API_KEY",
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "base_url": None,
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "env": "ANTHROPIC_API_KEY",
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        "base_url": None,
    },
    "google": {
        "label": "Google (Gemini)",
        "env": "GOOGLE_API_KEY",
        "model": os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"),
        "base_url": None,
    },
}


def build_chat_model(provider: str, api_key: str, model: str | None = None,
                     temperature: float = 0.3, streaming: bool = True):
    """Return a LangChain ``BaseChatModel`` for the given provider + key."""
    provider = (provider or "xai").lower()
    spec = PROVIDERS.get(provider, PROVIDERS["xai"])
    model = model or spec["model"]

    if provider in ("xai", "openai"):
        from langchain_openai import ChatOpenAI

        kw = dict(model=model, api_key=api_key, temperature=temperature,
                  streaming=streaming, timeout=90)
        if spec["base_url"]:
            kw["base_url"] = spec["base_url"]
        return ChatOpenAI(**kw)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, api_key=api_key, temperature=temperature,
                             streaming=streaming, timeout=90, max_tokens=1500)

    if provider == "google":
        # Gemini is a placeholder provider — supported but its LangChain
        # integration is an optional install.
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "Google/Gemini selected but langchain-google-genai is not installed. "
                "Run: pip install langchain-google-genai"
            ) from e
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key,
                                      temperature=temperature)

    # Unknown provider — fall back to the xAI-compatible client.
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model, api_key=api_key, temperature=temperature,
                      streaming=streaming, base_url=PROVIDERS["xai"]["base_url"],
                      timeout=90)


# --- deployment "house" key helpers ----------------------------------------

def house_provider() -> str:
    return (os.getenv("MODEL_PROVIDER") or os.getenv("LLM_PROVIDER") or "xai").lower()


def house_key(provider: str | None = None) -> str:
    provider = provider or house_provider()
    spec = PROVIDERS.get(provider, PROVIDERS["xai"])
    return os.getenv(spec["env"], "")


def house_model(provider: str | None = None) -> str:
    provider = provider or house_provider()
    # MODEL_NAME mirrors the convention used by the per-app web/ai.py templates.
    return os.getenv("MODEL_NAME") or PROVIDERS.get(provider, PROVIDERS["xai"])["model"]
