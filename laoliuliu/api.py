"""Authenticated HTTP API for the web application."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from laoliuliu.ai import (
    PROMPT_VERSION,
    AiProviderConfig,
    request_ai_explanation,
    validate_provider_base_url,
)
from laoliuliu.analysis import (
    calculate_latest_transition,
    calculate_transition_for_issue,
    list_historical_analysis_issues,
)
from laoliuliu.auth import (
    SESSION_COOKIE_NAME,
    AuthContext,
    authenticate,
    change_password,
    create_child_user,
    load_session,
    require_admin,
    require_ready,
    revoke_session,
    rotate_csrf,
    set_child_user_status,
    verify_csrf,
)
from laoliuliu.config import Settings, get_settings
from laoliuliu.db import get_db
from laoliuliu.errors import AiServiceError, AppError, AuthorizationError
from laoliuliu.ingestion import synchronize_current, synchronize_history
from laoliuliu.models import (
    AiProvider,
    AnalysisRun,
    AuditLog,
    DrawRecord,
    SourceSyncRun,
    User,
)
from laoliuliu.schemas import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    UpdateAiProviderRequest,
    UpdateUserStatusRequest,
)
from laoliuliu.security import decrypt_api_key, encrypt_api_key
from laoliuliu.source import SourceClient

API_ROUTER = APIRouter(prefix="/api/v1")

Db = Annotated[Session, Depends(get_db)]
RuntimeSettings = Annotated[Settings, Depends(get_settings)]


def _request_id(request: Request) -> str:
    return str(request.state.request_id)


def _success(data: object, request: Request, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "error": None,
            "request_id": _request_id(request),
        },
    )


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
        "must_change_password": user.must_change_password,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat(),
    }


def current_context(
    db: Db,
    settings: RuntimeSettings,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> AuthContext:
    """FastAPI dependency resolving the current opaque session."""

    return load_session(db, session_token, settings)


CurrentContext = Annotated[AuthContext, Depends(current_context)]


def _require_csrf(
    context: AuthContext, csrf_token: str | None, settings: Settings
) -> None:
    verify_csrf(context, csrf_token, settings)


@API_ROUTER.post("/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
) -> JSONResponse:
    result = authenticate(db, payload.username, payload.password, settings)
    response = _success(
        {
            "user": _user_payload(result.context.user),
            "csrf_token": result.csrf_token,
        },
        request,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=result.session_token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return response


@API_ROUTER.get("/auth/me")
def me(
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
) -> JSONResponse:
    csrf_token = rotate_csrf(db, context, settings)
    return _success(
        {"user": _user_payload(context.user), "csrf_token": csrf_token}, request
    )


@API_ROUTER.post("/auth/change-password")
def update_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    _require_csrf(context, csrf_token, settings)
    change_password(db, context, payload.current_password, payload.new_password)
    return _success({"changed": True}, request)


@API_ROUTER.post("/auth/logout")
def logout(
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    _require_csrf(context, csrf_token, settings)
    revoke_session(db, context)
    response = _success({"logged_out": True}, request)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@API_ROUTER.get("/draws")
def list_draws(
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
) -> JSONResponse:
    require_ready(context)
    total = (
        db.scalar(
            select(func.count())
            .select_from(DrawRecord)
            .where(DrawRecord.issue >= settings.data_start_issue_id)
        )
        or 0
    )
    rows = list(
        db.scalars(
            select(DrawRecord)
            .where(DrawRecord.issue >= settings.data_start_issue_id)
            .order_by(DrawRecord.open_time.desc(), DrawRecord.issue.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return _success(
        {
            "items": [
                {
                    "issue": row.issue,
                    "open_time": _iso(row.open_time),
                    "regular_numbers": row.regular_numbers,
                    "special_number": row.special_number,
                    "zodiac_anchor": row.zodiac_anchor,
                }
                for row in rows
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
        },
        request,
    )


@API_ROUTER.get("/analysis/latest")
def latest_analysis(request: Request, db: Db, context: CurrentContext) -> JSONResponse:
    require_ready(context)
    return _success(calculate_latest_transition(db).to_dict(), request)


@API_ROUTER.get("/analysis/history/issues")
def historical_analysis_issues(
    request: Request, db: Db, context: CurrentContext
) -> JSONResponse:
    require_ready(context)
    return _success({"items": list_historical_analysis_issues(db)}, request)


@API_ROUTER.get("/analysis/history/{issue}")
def historical_analysis(
    issue: str, request: Request, db: Db, context: CurrentContext
) -> JSONResponse:
    require_ready(context)
    return _success(calculate_transition_for_issue(db, issue).to_dict(), request)


@API_ROUTER.post("/analysis/ai")
def run_ai_analysis(
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    require_ready(context)
    _require_csrf(context, csrf_token, settings)
    deterministic = calculate_latest_transition(db)
    provider = db.scalar(select(AiProvider).order_by(AiProvider.created_at).limit(1))
    if provider is None or not provider.enabled or provider.encrypted_api_key is None:
        raise AiServiceError("AI_NOT_CONFIGURED", "管理员尚未启用AI服务", 409)
    run = AnalysisRun(
        user_id=context.user.id,
        latest_issue=deterministic.latest_issue,
        special_zodiac=deterministic.latest_special_zodiac.value,
        prompt_version=PROMPT_VERSION,
        deterministic_result=deterministic.to_dict(),
        status="failed",
    )
    db.add(run)
    db.commit()
    try:
        ai_result = request_ai_explanation(
            AiProviderConfig(
                display_name=provider.display_name,
                base_url=provider.base_url,
                model=provider.model,
                api_key=decrypt_api_key(provider.encrypted_api_key, settings),
            ),
            deterministic,
            settings,
        )
    except AiServiceError as error:
        run.error_code = error.code
        db.commit()
        raise
    run.ai_result = ai_result
    run.status = "succeeded"
    run.error_code = None
    db.commit()
    return _success(
        {
            "run_id": run.id,
            "deterministic_result": deterministic.to_dict(),
            "ai_result": ai_result,
        },
        request,
    )


@API_ROUTER.get("/analysis/runs")
def list_analysis_runs(
    request: Request,
    db: Db,
    context: CurrentContext,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> JSONResponse:
    require_ready(context)
    rows = list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.user_id == context.user.id)
            .order_by(AnalysisRun.created_at.desc())
            .limit(limit)
        )
    )
    return _success(
        {
            "items": [
                {
                    "id": row.id,
                    "latest_issue": row.latest_issue,
                    "special_zodiac": row.special_zodiac,
                    "status": row.status,
                    "error_code": row.error_code,
                    "ai_result": row.ai_result,
                    "created_at": _iso(row.created_at),
                }
                for row in rows
            ]
        },
        request,
    )


@API_ROUTER.get("/admin/users")
def list_users(request: Request, db: Db, context: CurrentContext) -> JSONResponse:
    require_admin(context)
    rows = list(db.scalars(select(User).order_by(User.created_at.desc())))
    return _success({"items": [_user_payload(user) for user in rows]}, request)


@API_ROUTER.post("/admin/users")
def create_user(
    payload: CreateUserRequest,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    require_admin(context)
    _require_csrf(context, csrf_token, settings)
    user, temporary_password = create_child_user(db, payload.username)
    _audit(db, request, context.user.id, "admin.user.created", "user", user.id)
    return _success(
        {"user": _user_payload(user), "temporary_password": temporary_password},
        request,
        201,
    )


@API_ROUTER.patch("/admin/users/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: UpdateUserStatusRequest,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    require_admin(context)
    _require_csrf(context, csrf_token, settings)
    user = db.get(User, user_id)
    if user is None:
        raise AuthorizationError("USER_NOT_FOUND", "用户不存在", 404)
    set_child_user_status(db, user, payload.status)
    _audit(
        db,
        request,
        context.user.id,
        "admin.user.status_changed",
        "user",
        user.id,
        {"status": payload.status},
    )
    return _success({"user": _user_payload(user)}, request)


@API_ROUTER.get("/admin/ai-provider")
def get_ai_provider(request: Request, db: Db, context: CurrentContext) -> JSONResponse:
    require_admin(context)
    provider = db.scalar(select(AiProvider).order_by(AiProvider.created_at).limit(1))
    if provider is None:
        return _success({"provider": None, "prompt_version": PROMPT_VERSION}, request)
    return _success(
        {
            "provider": {
                "display_name": provider.display_name,
                "base_url": provider.base_url,
                "model": provider.model,
                "enabled": provider.enabled,
                "has_api_key": provider.encrypted_api_key is not None,
                "updated_at": _iso(provider.updated_at),
            },
            "prompt_version": PROMPT_VERSION,
        },
        request,
    )


@API_ROUTER.put("/admin/ai-provider")
def update_ai_provider(
    payload: UpdateAiProviderRequest,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    require_admin(context)
    _require_csrf(context, csrf_token, settings)
    try:
        base_url = validate_provider_base_url(payload.base_url)
    except ValueError as error:
        raise AuthorizationError("AI_BASE_URL_INVALID", str(error), 422) from error
    provider = db.scalar(select(AiProvider).order_by(AiProvider.created_at).limit(1))
    if provider is None:
        provider = AiProvider(
            display_name=payload.display_name.strip(),
            base_url=base_url,
            model=payload.model.strip(),
        )
        db.add(provider)
    provider.display_name = payload.display_name.strip()
    provider.base_url = base_url
    provider.model = payload.model.strip()
    if payload.clear_api_key:
        provider.encrypted_api_key = None
    elif payload.api_key:
        provider.encrypted_api_key = encrypt_api_key(payload.api_key, settings)
    if payload.enabled and provider.encrypted_api_key is None:
        raise AuthorizationError("AI_KEY_REQUIRED", "启用AI服务前必须配置API Key", 422)
    provider.enabled = payload.enabled
    db.commit()
    _audit(
        db,
        request,
        context.user.id,
        "admin.ai_provider.updated",
        "ai_provider",
        provider.id,
        {"enabled": provider.enabled, "model": provider.model},
    )
    return get_ai_provider(request, db, context)


@API_ROUTER.post("/admin/sync/{sync_kind}")
def run_sync(
    sync_kind: str,
    request: Request,
    db: Db,
    settings: RuntimeSettings,
    context: CurrentContext,
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> JSONResponse:
    require_admin(context)
    _require_csrf(context, csrf_token, settings)
    client = SourceClient(settings)
    if sync_kind == "history":
        result = synchronize_history(db, client, settings)
    elif sync_kind == "current":
        result = synchronize_current(db, client, settings)
    else:
        raise AuthorizationError("SYNC_KIND_INVALID", "同步类型无效", 404)
    _audit(
        db,
        request,
        context.user.id,
        f"admin.sync.{sync_kind}",
        "source_sync_run",
        result.run_id,
        {"inserted": result.inserted, "skipped": result.skipped},
    )
    return _success(result.__dict__, request)


@API_ROUTER.get("/admin/sync-runs")
def list_sync_runs(request: Request, db: Db, context: CurrentContext) -> JSONResponse:
    require_admin(context)
    rows = list(
        db.scalars(
            select(SourceSyncRun).order_by(SourceSyncRun.started_at.desc()).limit(20)
        )
    )
    return _success(
        {
            "items": [
                {
                    "id": row.id,
                    "sync_kind": row.sync_kind,
                    "status": row.status,
                    "fetched_count": row.fetched_count,
                    "inserted_count": row.inserted_count,
                    "skipped_count": row.skipped_count,
                    "error_code": row.error_code,
                    "started_at": _iso(row.started_at),
                    "finished_at": _iso(row.finished_at),
                }
                for row in rows
            ]
        },
        request,
    )


def _audit(
    db: Session,
    request: Request,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str,
    context: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=_request_id(request),
            context=context or {},
        )
    )
    db.commit()


def app_error_response(error: AppError, request_id: str) -> JSONResponse:
    """Return one stable safe error envelope."""

    return JSONResponse(
        status_code=error.status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": error.code, "message": error.message},
            "request_id": request_id,
        },
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
