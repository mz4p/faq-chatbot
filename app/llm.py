"""Cienka warstwa dostawców modelu. Reszta aplikacji zna tylko `LLM.complete`.

Dwie implementacje:
- AnthropicLLM: oficjalne SDK Anthropic.
- OpenAICompatLLM: dowolne API zgodne z OpenAI /chat/completions (np. Nous Portal).
"""

from dataclasses import dataclass
from typing import Protocol

import anthropic
import httpx2

from .config import Settings


class ChatError(Exception):
    """Błąd po stronie API modelu (sieć, timeout, 5xx, niepoprawna odpowiedź)."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class Completion:
    text: str
    refused: bool
    usage: Usage


class LLM(Protocol):
    def complete(self, system: str, messages: list[dict]) -> Completion: ...


class AnthropicLLM:
    def __init__(self, client: anthropic.Anthropic, settings: Settings):
        self.client = client
        self.settings = settings

    def complete(self, system: str, messages: list[dict]) -> Completion:
        try:
            response = self.client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_tokens,
                output_config={"effort": self.settings.effort},
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            )
        except anthropic.APIError as exc:
            raise ChatError(str(exc)) from exc

        u = response.usage
        usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_creation_input_tokens=u.cache_creation_input_tokens or 0,
            cache_read_input_tokens=u.cache_read_input_tokens or 0,
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return Completion(text, response.stop_reason == "refusal", usage)


class OpenAICompatLLM:
    def __init__(self, http: httpx2.Client, settings: Settings):
        self.http = http
        self.settings = settings

    def complete(self, system: str, messages: list[dict]) -> Completion:
        system_content: str | list[dict] = system
        if self.settings.model.startswith("anthropic/"):
            # Modele Anthropic za bramką zgodną z OpenAI przyjmują cache_control w częściach treści.
            system_content = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        body = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "reasoning_effort": self.settings.effort,
            "messages": [{"role": "system", "content": system_content}, *messages],
        }

        data = self._post(body)
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            refused = bool(message.get("refusal")) or choice.get("finish_reason") in (
                "content_filter",
                "refusal",
            )
            return Completion(content.strip(), refused, self._usage(data.get("usage") or {}))
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ChatError(f"Nieoczekiwany format odpowiedzi: {exc!r}") from exc

    def _post(self, body: dict) -> dict:
        last: Exception | None = None
        for _ in range(2):  # jedna ponowna próba przy błędzie sieci lub 5xx
            try:
                response = self.http.post("/chat/completions", json=body)
            except httpx2.HTTPError as exc:
                last = exc
                continue
            if response.status_code >= 500:
                last = ChatError(f"HTTP {response.status_code}")
                continue
            if response.status_code >= 400:
                raise ChatError(f"HTTP {response.status_code}: {response.text[:200]}")
            try:
                return response.json()
            except ValueError as exc:
                raise ChatError("Odpowiedź nie jest poprawnym JSON-em") from exc
        raise ChatError(str(last)) from last

    @staticmethod
    def _usage(raw: dict) -> Usage:
        details = raw.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens") or 0
        written = details.get("cache_write_tokens") or 0
        prompt = raw.get("prompt_tokens") or 0
        # W formacie OpenAI prompt_tokens obejmuje też tokeny z cache'u.
        return Usage(
            input_tokens=max(prompt - cached - written, 0),
            output_tokens=raw.get("completion_tokens") or 0,
            cache_creation_input_tokens=written,
            cache_read_input_tokens=cached,
        )


def create_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "anthropic":
        client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key, max_retries=1, timeout=30.0
        )
        return AnthropicLLM(client, settings)
    http = httpx2.Client(
        base_url=settings.llm_base_url.rstrip("/"),
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        timeout=30.0,
    )
    return OpenAICompatLLM(http, settings)
