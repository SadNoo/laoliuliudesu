"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from laoliuliu import __version__
from laoliuliu.api import API_ROUTER, app_error_response
from laoliuliu.config import get_settings
from laoliuliu.db import SessionLocal
from laoliuliu.errors import AppError
from laoliuliu.web.routes import WEB_ROUTER

logger = logging.getLogger("laoliuliu")


def create_app() -> FastAPI:
    """Build the API and same-origin web application."""

    app = FastAPI(
        title="laoliuliu",
        version=__version__,
        docs_url=None if get_settings().env == "production" else "/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        )
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, error: AppError) -> JSONResponse:
        return app_error_response(error, str(request.state.request_id))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "data": None,
                "error": {"code": "REQUEST_INVALID", "message": "请求参数无效"},
                "request_id": str(request.state.request_id),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, error: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled request error",
            extra={"request_id": str(request.state.request_id)},
        )
        del error
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"},
                "request_id": str(request.state.request_id),
            },
        )

    @app.get("/health/live", include_in_schema=False)
    def live() -> dict[str, object]:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready", include_in_schema=False)
    def ready() -> dict[str, object]:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready", "version": __version__}

    app.include_router(API_ROUTER)
    app.include_router(WEB_ROUTER)
    return app


app = create_app()


def run() -> None:
    """Run the production ASGI server."""

    uvicorn.run("laoliuliu.main:app", host="0.0.0.0", port=8000, proxy_headers=True)


if __name__ == "__main__":
    run()
