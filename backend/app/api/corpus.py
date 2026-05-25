from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/themes")
def list_themes(request: Request, language: str = "en") -> dict[str, object]:
    """Return the themes available in the corpus for the given language."""
    corpora = request.app.state.corpora
    corpus = corpora.get(language)
    if corpus is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "language_unsupported",
                    "message": f"No corpus loaded for language {language!r}",
                }
            },
        )
    return {
        "language": corpus.language,
        "themes": [{"id": t.id, "name": t.name, "icon": t.icon} for t in corpus.themes],
    }
