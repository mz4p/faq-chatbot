# faq-chatbot

Chatbot FAQ dla małych firm: odpowiada klientom na pytania **wyłącznie na podstawie dokumentów firmy**
(cennik, godziny, zasady zwrotów), a gdy czegoś nie wie, mówi to wprost i podaje kontakt do człowieka.
Jeden silnik obsługuje wiele firm, bo każda to osobny katalog z plikami `.md`. W repo są dwie
wymyślone firmy: salon fryzjerski i sklep z butami.

*English summary: a multi-tenant FAQ chatbot (FastAPI + Claude Haiku 5.5 + a single-file JS widget).
Each company is a folder of Markdown files that is placed in the prompt, so no vector database is
needed. Includes rate limiting, a daily spending cap, an eval suite and a Dockerfile.*

## Jak to działa

```
widget/chat.js  ──POST /chat──▶  FastAPI (app/main.py)
                                   ├─ limity: IP + dzienny budżet (app/limits.py)
                                   ├─ wiedza firmy z knowledge/<firma>/*.md (app/knowledge.py)
                                   └─ Claude Haiku 5.5, wiedza w prompcie, cache'owana (app/chat.py)
```

Mała firma ma kilka stron dokumentów, które mieszczą się w prompcie. Dzięki temu odpowiedzi są
dokładniejsze niż przy wyszukiwaniu fragmentów, a całość jest prostsza i tańsza w utrzymaniu.

## Uruchomienie w 5 minut

Wymagania: [uv](https://docs.astral.sh/uv/) i klucz API Anthropic.

```bash
git clone <adres-repo> && cd faq-chatbot
cp .env.example .env          # wpisz ANTHROPIC_API_KEY
uv sync
uv run uvicorn app.main:create_app --factory --reload
```

Otwórz <http://localhost:8000>, wybierz firmę i kliknij dymek czatu.

Docker:

```bash
docker build -t faq-chatbot .
docker run --rm -p 8080:8080 --env-file .env faq-chatbot
```

## Dodanie nowej firmy

1. Utwórz katalog `knowledge/<nazwa>/` (małe litery, cyfry i myślniki).
2. Wrzuć do niego pliki `.md`: cennik, godziny, FAQ, polityka zwrotów, kontakt.
3. Zrestartuj serwer. Firma jest od razu dostępna jako `tenant: "<nazwa>"`.

Dokumenty muszą zawierać **dane kontaktowe**, bo bot odsyła do nich, gdy nie zna odpowiedzi.

## Osadzenie na stronie klienta

```html
<script src="https://twoj-serwer/widget/chat.js" data-tenant="salon"></script>
```

Opcjonalne atrybuty: `data-title`, `data-greeting`, `data-placeholder`, `data-max-chars`,
`data-api` (gdy API jest pod innym adresem niż plik widgetu). Widget działa w Shadow DOM, więc
style strony klienta go nie psują, a tekst wstawia przez `textContent`.

## API

| Metoda | Ścieżka | Opis |
|---|---|---|
| `GET` | `/health` | status i lista firm |
| `POST` | `/chat` | `{"tenant", "message", "history": [{"role", "content"}]}` zwraca `{"reply"}` |

Błędy: `404` nieznana firma, `422` pusta lub za długa wiadomość, `429` limit zapytań albo
dzienny budżet, `502` problem po stronie modelu.

## Konfiguracja (zmienne środowiskowe lub `.env`)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `ANTHROPIC_API_KEY` | brak (wymagana) | bez niej aplikacja nie wystartuje |
| `MODEL` | `claude-haiku-5-5` | model |
| `EFFORT` | `low` | głębokość myślenia modelu |
| `MAX_TOKENS` | `1500` | limit odpowiedzi, myślenie też się wlicza |
| `MAX_MESSAGE_CHARS` | `500` | maksymalna długość pytania |
| `MAX_HISTORY` | `6` | ile ostatnich wymian trafia do modelu |
| `RATE_LIMIT_PER_MINUTE` | `10` | zapytań na IP na minutę |
| `DAILY_BUDGET_USD` | `0.30` | dzienny twardy limit wydatków |
| `TRUST_FORWARDED_FOR` | `false` | włącz za proxy (Fly, Render, nginx), żeby limit liczył IP klienta; bierzemy ostatni wpis `X-Forwarded-For`, który dopisuje proxy |

## Koszty i bezpieczeństwo

- Haiku 5.5 kosztuje $0,10 / $0,50 za milion tokenów (wejście / wyjście). Jedna rozmowa z bazą
  rzędu tysiąca tokenów to ułamek grosza, więc budżet 0,30 USD dziennie wystarcza szacunkowo
  na około tysiąc pytań. Ceny trzymam w konfiguracji, sprawdź je przy zmianie modelu.
- Warstwy ochrony: limit zapytań na IP, limit długości wiadomości i historii, dzienny budżet
  liczony z `usage` odpowiedzi. Dodatkowo ustaw limit wydatków w konsoli Anthropic.
- Klucz API jest tylko w zmiennej środowiskowej, nigdy w repo ani w widgecie.
- Prompt instruuje model, aby traktował wiadomość klienta jako pytanie, a nie polecenie. To
  zmniejsza, ale nie eliminuje ryzyka prompt injection, dlatego bot nie ma dostępu do żadnych
  systemów firmy.
- **Ograniczenie:** limity są w pamięci procesu, więc działają przy jednej instancji. Przy wielu
  instancjach przenieś je do wspólnego magazynu (np. Redis).

## Testy i ewaluacja

```bash
uv run pytest                          # testy jednostkowe i API, bez kosztów
uv run python evals/run_evals.py       # ewaluacja na prawdziwym API (ułamki grosza)
```

Zestaw w `evals/questions.yaml` sprawdza fakty z dokumentów, pytania spoza bazy (bot ma odesłać
do kontaktu), pytania niezwiązane z firmą oraz próby prompt injection.

## Kiedy przejść na embeddingi i bazę wektorową

Obecne podejście (cała wiedza w prompcie) dobrze działa do kilkudziesięciu stron dokumentów.
Przejdź na wyszukiwanie fragmentów (embeddingi plus baza wektorowa), gdy:

- dokumenty firmy przekraczają kilkadziesiąt stron i koszt oraz czas odpowiedzi rosną,
- wiedza zmienia się często i trzeba ją aktualizować bez restartu,
- potrzebujesz cytowania źródeł lub wiedzy z wielu setek plików.

Wtedy `app/knowledge.py` zastępuje się modułem, który po pytaniu zwraca tylko pasujące
fragmenty, a reszta (limity, API, widget) zostaje bez zmian.

## Struktura

```
app/        config, knowledge, limits, chat, main
knowledge/  salon/, sklep/
widget/     chat.js, demo.html
evals/      questions.yaml, run_evals.py
tests/
```
