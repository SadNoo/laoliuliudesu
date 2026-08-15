"""Fixed web application asset routes."""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Final

from fastapi import APIRouter
from fastapi.responses import Response

WEB_ROUTER = APIRouter(include_in_schema=False)

_HEADERS: Final[dict[str, str]] = {
    "Cache-Control": "no-store, max-age=0",
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; connect-src 'self'; "
        "font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
        "img-src 'self' data:; script-src 'self'; style-src 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": (
        "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


@lru_cache(maxsize=3)
def _asset(name: str) -> bytes:
    if name not in {"index.html", "app.css", "app.js"}:
        raise ValueError("asset is not registered")
    return files("laoliuliu.web").joinpath("assets", name).read_bytes()


def _response(name: str, media_type: str) -> Response:
    return Response(content=_asset(name), media_type=media_type, headers=dict(_HEADERS))


@WEB_ROUTER.get("/")
def index() -> Response:
    """Return the application shell."""

    return _response("index.html", "text/html; charset=utf-8")


@WEB_ROUTER.get("/assets/app.css")
def stylesheet() -> Response:
    """Return the application stylesheet."""

    return _response("app.css", "text/css; charset=utf-8")


@WEB_ROUTER.get("/assets/app.js")
def javascript() -> Response:
    """Return the application JavaScript."""

    return _response("app.js", "text/javascript; charset=utf-8")
