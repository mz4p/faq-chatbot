import logging
import threading
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .chat import ChatError, answer
from .config import Settings, get_settings
from .knowledge import load_tenants
from .limits import DailyBudget, RateLimiter, cost_usd
from .llm import LLM, create_llm

logger = logging.getLogger(__name__)

MSG_UNKNOWN_TENANT = "Nie znaleziono konfiguracji."
MSG_TOO_LONG = "Wiadomość jest za długa (maksymalnie {n} znaków)."
MSG_EMPTY = "Wiadomość nie może być pusta."
MSG_RATE_LIMIT = "Zbyt wiele zapytań. Spróbuj ponownie za chwilę."
MSG_BUDGET = "Demo odpoczywa, spróbuj ponownie jutro."
MSG_UPSTREAM = "Asystent jest chwilowo niedostępny. Spróbuj ponownie lub skontaktuj się z firmą."


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    tenant: str = Field(max_length=50)
    message: str
    history: list[HistoryItem] = Field(default_factory=list, max_length=50)


class ChatResponse(BaseModel):
    reply: str


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    settings = settings or get_settings()
    llm = llm or create_llm(settings)
    tenants = load_tenants(settings.knowledge_dir)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    budget = DailyBudget(settings.daily_budget_usd)
    lock = threading.Lock()

    app = FastAPI(title="faq-chatbot")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def client_ip(request: Request) -> str:
        if settings.trust_forwarded_for:
            # Skrajnie lewy wpis wpisuje klient (można go podrobić). Zaufany proxy dopisuje
            # prawdziwy adres na końcu, więc bierzemy ostatni.
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[-1].strip()
        return request.client.host if request.client else "unknown"

    @app.get("/health")
    def health():
        return {"status": "ok", "tenants": sorted(tenants)}

    @app.post("/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, request: Request):
        knowledge = tenants.get(body.tenant)
        if knowledge is None:
            raise HTTPException(404, MSG_UNKNOWN_TENANT)

        message = body.message.strip()
        if not message:
            raise HTTPException(422, MSG_EMPTY)
        if len(message) > settings.max_message_chars:
            raise HTTPException(422, MSG_TOO_LONG.format(n=settings.max_message_chars))

        with lock:
            if not limiter.allow(client_ip(request)):
                raise HTTPException(429, MSG_RATE_LIMIT)
            if not budget.can_spend():
                raise HTTPException(429, MSG_BUDGET)

        try:
            result = answer(
                llm,
                knowledge,
                [h.model_dump() for h in body.history],
                message,
                settings.max_history,
            )
        except ChatError:
            logger.exception("Błąd wywołania modelu (tenant=%s)", body.tenant)
            raise HTTPException(502, MSG_UPSTREAM) from None

        with lock:
            budget.record(cost_usd(result.usage, settings))
        return ChatResponse(reply=result.text)

    demo = settings.widget_dir / "demo.html"
    if settings.widget_dir.is_dir():
        app.mount("/widget", StaticFiles(directory=settings.widget_dir), name="widget")
    if demo.is_file():

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(demo)

    return app
