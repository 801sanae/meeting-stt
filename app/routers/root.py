from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse


router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


BASE_DIR = Path(__file__).resolve().parent.parent  # app/
INDEX_HTML = BASE_DIR / "static" / "html" / "index.html"


@router.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    return FileResponse(INDEX_HTML)
