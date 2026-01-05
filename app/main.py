import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config.db import init_db
from app.config.logging import setup_logging
from app.config.settings import get_settings
from app.routers import meetings, root, admin_stt


setup_logging()

logger = logging.getLogger("meeting-stt")
settings = get_settings()


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(title="Meeting STT API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if settings.enable_metrics:
    Instrumentator(
        excluded_handlers=["/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics enabled at /metrics")


# 정적 파일 (CSS/JS) 서빙
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.exception_handler(HTTPException)
async def http_exception_logger(request: Request, exc: HTTPException):
    if exc.status_code in (429, 502):
        logger.warning("HTTP %s at %s: %s", exc.status_code, request.url.path, exc.detail)
    return await http_exception_handler(request, exc)


app.include_router(root.router)
app.include_router(meetings.router)
app.include_router(admin_stt.router)
