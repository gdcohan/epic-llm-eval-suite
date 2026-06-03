"""Pluggable LLM providers behind a single complete_json() interface.

Ships OpenAI + Anthropic adapters (so spanning vendors is one config change) plus
a deterministic Stub provider so the whole pipeline runs offline with no keys.
SDK imports are lazy: a missing SDK only errors if you actually use that provider.
"""

import os
import json
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def complete_json(self, system, user, model, temperature):
        """Return a parsed JSON object (dict) from the model."""


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        from openai import OpenAI  # lazy

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def complete_json(self, system, user, model, temperature):
        resp = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return json.loads(resp.choices[0].message.content)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self):
        import anthropic  # lazy

        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def complete_json(self, system, user, model, temperature):
        resp = self.client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=temperature,
            system=system + "\n\nRespond with ONLY a single valid JSON object.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return _loads_lenient(text)


class StubProvider(LLMProvider):
    """Deterministic offline provider for demos/tests (no network/keys)."""

    name = "stub"

    def complete_json(self, system, user, model, temperature):
        # Mildly varied but deterministic so aggregation is observable.
        score = 3 + (len(user) + int(temperature * 10)) % 3
        return {
            "score": score,
            "rationale": "[stub verdict] Offline placeholder; wire a real provider/API key for substantive judgments.",
            "supporting_evidence": [],
            "issues": [],
        }


def _loads_lenient(text):
    """Parse JSON, tolerating prose/code-fences around the object."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise


_REGISTRY = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "stub": StubProvider,
}

_CACHE = {}


def get_provider(name):
    """Return a cached provider instance by name ('openai'|'anthropic'|'stub')."""
    if name not in _REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Options: {list(_REGISTRY)}")
    if name not in _CACHE:
        _CACHE[name] = _REGISTRY[name]()
    return _CACHE[name]
