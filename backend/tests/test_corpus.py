import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.corpus.loader import load_corpus, normalise
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def test_themes_endpoint_returns_english_themes() -> None:
    with TestClient(app) as client:
        r = client.get("/api/corpus/themes?language=en")
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "en"
        ids = {t["id"] for t in data["themes"]}
        assert {"sport", "nature", "technology"}.issubset(ids)


def test_themes_endpoint_returns_russian_themes() -> None:
    with TestClient(app) as client:
        r = client.get("/api/corpus/themes?language=ru")
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "ru"


def test_themes_endpoint_404_for_unknown_language() -> None:
    with TestClient(app) as client:
        r = client.get("/api/corpus/themes?language=zz")
        assert r.status_code == 404
        assert r.json()["detail"]["error"]["code"] == "language_unsupported"


def test_sample_corpus_has_all_difficulties_per_theme() -> None:
    corpus = load_corpus(DATA_DIR / "words.sample.en.json")
    for theme in corpus.themes:
        diffs = {w.difficulty for w in theme.words}
        assert diffs == {1, 2, 3, 4, 5}, f"theme {theme.id!r} missing difficulties: {diffs}"


def test_normalise_collapses_punctuation_and_case() -> None:
    assert normalise("Café!") == "cafe"
    assert normalise("Ice-Cream") == "ice cream"
    assert normalise("Привет, мир!") == "привет мир"
    assert normalise("  trailing  spaces  ") == "trailing spaces"


def test_normalise_handles_diacritics_in_cyrillic() -> None:
    # ё decomposes to е + combining diaeresis; we strip the combining mark,
    # so "кёрлинг" matches "керлинг" — handy because Russians often type one
    # or the other interchangeably.
    assert normalise("Кёрлинг") == "керлинг"
    assert normalise("Керлинг") == "керлинг"


def test_validator_rejects_hint_containing_target(tmp_path: Path) -> None:
    bad = {
        "version": 1,
        "language": "en",
        "themes": [
            {
                "id": "test",
                "name": "Test",
                "words": [
                    {"id": "ball", "text": "ball", "difficulty": 1, "hint": "a ball that bounces"},
                    {
                        "id": "lake",
                        "text": "lake",
                        "difficulty": 2,
                        "hint": "a body of fresh water",
                    },
                    {"id": "run", "text": "run", "difficulty": 3, "hint": "fast movement"},
                    {"id": "tennis", "text": "tennis", "difficulty": 4, "hint": "racket sport"},
                    {"id": "kerling", "text": "kerling", "difficulty": 5, "hint": "stones on ice"},
                ],
            }
        ],
    }
    path = tmp_path / "words.bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="contains target"):
        load_corpus(path)


def test_validator_rejects_missing_difficulty(tmp_path: Path) -> None:
    bad = {
        "version": 1,
        "language": "en",
        "themes": [
            {
                "id": "test",
                "name": "Test",
                "words": [
                    {"id": "a", "text": "a", "difficulty": 1, "hint": "first letter"},
                    {"id": "b", "text": "b", "difficulty": 2, "hint": "second letter"},
                    {"id": "c", "text": "c", "difficulty": 3, "hint": "third letter"},
                    {"id": "d", "text": "d", "difficulty": 4, "hint": "fourth letter"},
                    # missing difficulty 5
                ],
            }
        ],
    }
    path = tmp_path / "words.bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="difficulty 5"):
        load_corpus(path)
