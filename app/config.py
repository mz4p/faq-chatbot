from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # "anthropic": SDK Anthropic (ANTHROPIC_API_KEY).
    # "openai_compatible": dowolne API zgodne z OpenAI /chat/completions, np. Nous Portal
    # (LLM_BASE_URL + LLM_API_KEY, model w formacie "anthropic/claude-haiku-5.5").
    llm_provider: Literal["anthropic", "openai_compatible"] = "anthropic"
    anthropic_api_key: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""

    model: str = "claude-haiku-5-5"
    # Myślenie adaptacyjne też zużywa max_tokens, więc zapas jest większy niż sama odpowiedź.
    max_tokens: int = 1500
    effort: str = "low"

    max_message_chars: int = 500
    max_history: int = 6
    rate_limit_per_minute: int = 10
    daily_budget_usd: float = 0.30

    # Ceny USD za 1 mln tokenów (Haiku 5.5, prompty do 100K tokenów). Sprawdź przy zmianie modelu.
    price_input_per_mtok: float = 0.10
    price_output_per_mtok: float = 0.50
    # Mnożniki cache'u promptu względem ceny wejścia.
    cache_write_multiplier: float = 1.25
    cache_read_multiplier: float = 0.10

    # Włącz tylko za zaufanym proxy (Fly, Render, nginx): wtedy IP klienta bierzemy z X-Forwarded-For.
    trust_forwarded_for: bool = False

    knowledge_dir: Path = ROOT / "knowledge"
    widget_dir: Path = ROOT / "widget"

    @model_validator(mode="after")
    def _require_credentials(self):
        # Pusty klucz (np. skopiowany .env.example) ma zatrzymać start, a nie dawać 502 przy każdym pytaniu.
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError("Ustaw ANTHROPIC_API_KEY (dla LLM_PROVIDER=anthropic)")
        elif not (self.llm_api_key and self.llm_base_url):
            raise ValueError("Ustaw LLM_API_KEY i LLM_BASE_URL (dla LLM_PROVIDER=openai_compatible)")
        return self


def get_settings() -> Settings:
    return Settings()
