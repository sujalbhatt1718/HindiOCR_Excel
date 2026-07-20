"""FastAPI application entry point for HindiOCRExcel."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import export, files, health, process, upload
from app.config import ROOT_DIR, settings
from app.models.schemas import ErrorResponse
from app.services.ocr_service import ocr_service
from app.utils.exceptions import AppError
from app.utils.helpers import cleanup_old_files
from app.utils.logger import configure_logging, logger

FRONTEND_DIR = ROOT_DIR / "frontend"


async def _periodic_cleanup(interval_sec: int = 1800) -> None:
    """Background task that periodically removes stale temp/upload files."""
    while True:
        try:
            await asyncio.sleep(interval_sec)
            await asyncio.to_thread(cleanup_old_files)
        except asyncio.CancelledError:  # pragma: no cover
            break
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cleanup task error: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging, warm up OCR models and start background cleanup."""
    configure_logging()
    settings.ensure_dirs()
    logger.info("Starting {} v{}", settings.app_name, settings.app_version)
    # Warm up OCR models in a worker thread so startup isn't blocked.
    asyncio.create_task(asyncio.to_thread(ocr_service.warmup))
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()
        logger.info("Shutting down {}", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Convert images and PDFs containing tabular data (Hindi / English / "
        "mixed) into editable, formatted Excel files."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Exception handlers -> consistent JSON envelopes
# --------------------------------------------------------------------------- #
@app.exception_handler(AppError)
async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError [{}]: {}", exc.error_code, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.error_code, detail=exc.message).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="validation_error", detail=str(exc.errors())
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: {}", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error", detail="An unexpected error occurred."
        ).model_dump(),
    )


# --------------------------------------------------------------------------- #
# API routes
# --------------------------------------------------------------------------- #
api_prefix = "/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(upload.router, prefix=api_prefix)
app.include_router(process.router, prefix=api_prefix)
app.include_router(export.router, prefix=api_prefix)
app.include_router(files.router, prefix=api_prefix)


# --------------------------------------------------------------------------- #
# Frontend (served by FastAPI StaticFiles)
# --------------------------------------------------------------------------- #
def _serve_page(name: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / name)


if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    async def _home() -> FileResponse:
        return _serve_page("index.html")

    @app.get("/workspace", include_in_schema=False)
    async def _workspace() -> FileResponse:
        return _serve_page("workspace.html")

    @app.get("/about", include_in_schema=False)
    async def _about() -> FileResponse:
        return _serve_page("about.html")

    @app.exception_handler(404)
    async def _not_found(request: Request, _exc) -> FileResponse | JSONResponse:
        # API 404s stay JSON; browser navigation gets the styled 404 page.
        if request.url.path.startswith(api_prefix):
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="not_found", detail="Resource not found."
                ).model_dump(),
            )
        page = FRONTEND_DIR / "404.html"
        return FileResponse(page, status_code=404)


def run() -> None:  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":  # pragma: no cover
    run()
