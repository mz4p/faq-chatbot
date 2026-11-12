from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    # Brak wartości domyślnej: bez klucza aplikacja nie wystartuje.
    anthropic_api_key: str

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

    knowledge_dir: Path = ROOT / "knowledge"
    widget_dir: Path = ROOT / "widget"


def get_settings() -> Settings:
    return Settings()
