"""Testy samego mechanizmu ewaluacji (bez wywołań API)."""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

from run_evals import check  # noqa: E402


def test_check_passes_when_expected_fragment_present():
    assert check("Strzyżenie kosztuje 70 zł.", {"expect_any": ["70"]}) == []


def test_check_is_case_insensitive():
    assert check("Płacisz BLIK-iem.", {"expect_any": ["blik"]}) == []


def test_check_fails_without_expected_fragment():
    assert check("Nie wiem.", {"expect_any": ["70"]})


def test_check_fails_on_forbidden_fragment():
    assert check("Stolica to Paryż.", {"forbid": ["Paryż"]})


def test_questions_file_is_well_formed():
    cases = yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text(encoding="utf-8"))
    assert set(cases) == {"salon", "sklep"}
    for questions in cases.values():
        assert len(questions) >= 10
        for case in questions:
            assert case["q"].strip()
            assert case["type"] in {"fact", "outside_docs", "off_topic", "injection"}
            assert case.get("expect_any") or case.get("forbid")
