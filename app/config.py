from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Brak wartości domyślnej i min_length=1: ani brak klucza, ani pusty wpis z .env.example
    # (ANTHROPIC_API_KEY=) nie pozwolą aplikacji wystartować.
    anthropic_api_key: str = Field(min_length=1)

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


def get_settings() -> Settings:
    return Settings()
