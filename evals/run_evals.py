"""Ręczna ewaluacja bota na prawdziwym API.

Uruchomienie (wymaga ANTHROPIC_API_KEY w .env; zestaw ~22 pytań kosztuje ułamki grosza):
    uv run python evals/run_evals.py
    uv run python evals/run_evals.py --tenant salon

Kod wyjścia: 0 gdy wszystko przeszło, 1 gdy któreś pytanie nie przeszło.
"""

import argparse
import sys
from pathlib import Path

import anthropic
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.chat import answer  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.knowledge import load_tenants  # noqa: E402
from app.limits import cost_usd  # noqa: E402


def check(reply: str, case: dict) -> list[str]:
    """Zwraca listę powodów niepowodzenia (pusta lista = pytanie przeszło)."""
    low = reply.lower()
    problems = []
    expect_any = case.get("expect_any")
    if expect_any and not any(e.lower() in low for e in expect_any):
        problems.append(f"brak żadnego z: {expect_any}")
    for bad in case.get("forbid", []):
        if bad.lower() in low:
            problems.append(f"zawiera zakazane: {bad!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", help="uruchom tylko dla jednej firmy")
    args = parser.parse_args()

    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=2, timeout=60.0)
    tenants = load_tenants(settings.knowledge_dir)
    cases = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text(encoding="utf-8"))

    total = passed = 0
    spent = 0.0
    for tenant, questions in cases.items():
        if args.tenant and tenant != args.tenant:
            continue
        print(f"\n== {tenant} ==")
        for case in questions:
            result = answer(client, settings, tenants[tenant], [], case["q"])
            spent += cost_usd(result.usage, settings)
            problems = check(result.text, case)
            total += 1
            passed += not problems
            mark = "PASS" if not problems else "FAIL"
            print(f"[{mark}] ({case['type']}) {case['q']}")
            if problems:
                print(f"       odpowiedź: {result.text!r}")
                for p in problems:
                    print(f"       - {p}")

    print(f"\nWynik: {passed}/{total}. Koszt: ${spent:.4f}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
