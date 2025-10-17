"""Utilities for working with the selected LLM (now GitHub Models).

This project previously supported ad-hoc local model names via a custom
registry. We simplify everything to rely on standard, hosted GitHub Models
that are exposed through an OpenAI-compatible API surface.

Environment variables:
  LLM_MODEL         - (optional) model name. Defaults to 'gpt-4.1-mini'.
  OPENAI_API_KEY    - Required. Supply a GitHub personal access token (classic
                       with "models.read" scope) or the GitHub Models token.
  OPENAI_BASE_URL   - (optional) override base URL. Defaults to the GitHub
                       Models inference endpoint.
"""

from typing import Optional
import os
from openai import OpenAI

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


def get_llm_model() -> str:
    # Default to a broadly capable / cost effective model. Users can override.
    return os.getenv("LLM_MODEL", "gpt-4.1-mini")


def query_llm(
    user_message: Optional[str] = None,
    assistant_message: Optional[str] = None,
) -> str:
    """Query the configured GitHub Model via the OpenAI compatible client."""
    messages = []
    if assistant_message:
        messages.append({"role": "assistant", "content": assistant_message})
    if user_message:
        messages.append({"role": "user", "content": user_message})
    if not messages:
        return ""

    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", GITHUB_MODELS_BASE_URL),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    completion = client.chat.completions.create(
        model=get_llm_model(),
        messages=messages,
        temperature=0.7,
    )
    return completion.choices[0].message.content or ""  # type: ignore[attr-defined]
