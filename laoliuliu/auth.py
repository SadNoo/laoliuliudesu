"""Server-side browser authentication and child-user authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from laoliuliu.config import Settings
from laoliuliu.errors import AuthenticationError, AuthorizationError
from laoliuliu.models import User, WebSession, utc_now
from laoliuliu.security import (
    digest_secret,
    generate_password,
    generate_token,
    hash_password,
    normalize_username,
    secrets_match,
    verify_password,
)

SESSION_COOKIE_NAME = "laoliuliu_session"
_DUMMY_PASSWORD_HASH = hash_password("Dummy-password-483920")


@dataclass(frozen=True)
class AuthContext:
    """Authenticated request identity."""

    user: User
    session: WebSession


@dataclass(frozen=True)
class LoginResult:
    """New opaque session and in-memory CSRF token."""

    context: AuthContext
    session_token: str
    csrf_token: str


def authenticate(
    db: Session, username: str, password: str, settings: Settings
) -> LoginResult:
    """Authenticate a user and create a new server-side session."""

    try:
        canonical = normalize_username(username)
    except ValueError:
        canonical = "invalid"
    user = db.scalar(select(User).where(User.username == canonical))
    now = utc_now()
    if user is None:
        verify_password(_DUMMY_PASSWORD_HASH, password)
        raise AuthenticationError("INVALID_CREDENTIALS", "用户名或密码错误", 401)
    if user.locked_until is not None and _aware(user.locked_until) > now:
        raise AuthenticationError(
            "ACCOUNT_TEMPORARILY_LOCKED", "登录失败次数过多，请稍后重试", 429
        )
    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_count = 0
        db.commit()
        raise AuthenticationError("INVALID_CREDENTIALS", "用户名或密码错误", 401)
    if user.status != "active":
        raise AuthenticationError("ACCOUNT_DISABLED", "账号已停用", 403)

    raw_token = generate_token()
    raw_csrf = generate_token()
    browser_session = WebSession(
        user_id=user.id,
        token_hash=digest_secret(raw_token, settings),
        csrf_hash=digest_secret(raw_csrf, settings),
        expires_at=now + timedelta(hours=settings.session_hours),
    )
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    db.add(browser_session)
    db.commit()
    db.refresh(browser_session)
    return LoginResult(
        context=AuthContext(user=user, session=browser_session),
        session_token=raw_token,
        csrf_token=raw_csrf,
    )


def load_session(db: Session, raw_token: str | None, settings: Settings) -> AuthContext:
    """Resolve and validate an opaque browser session."""

    if not raw_token:
        raise AuthenticationError("AUTHENTICATION_REQUIRED", "请先登录", 401)
    token_hash = digest_secret(raw_token, settings)
    browser_session = db.scalar(
        select(WebSession).where(WebSession.token_hash == token_hash)
    )
    now = utc_now()
    if (
        browser_session is None
        or browser_session.revoked_at is not None
        or _aware(browser_session.expires_at) <= now
    ):
        raise AuthenticationError("SESSION_EXPIRED", "登录状态已过期", 401)
    user = db.get(User, browser_session.user_id)
    if user is None or user.status != "active":
        raise AuthenticationError("ACCOUNT_DISABLED", "账号已停用", 403)
    browser_session.last_seen_at = now
    db.commit()
    return AuthContext(user=user, session=browser_session)


def rotate_csrf(db: Session, context: AuthContext, settings: Settings) -> str:
    """Issue a new in-memory CSRF token for the current session."""

    raw_csrf = generate_token()
    context.session.csrf_hash = digest_secret(raw_csrf, settings)
    db.commit()
    return raw_csrf


def verify_csrf(context: AuthContext, raw_csrf: str | None, settings: Settings) -> None:
    """Reject a state-changing request without the current CSRF token."""

    if not raw_csrf or not secrets_match(raw_csrf, context.session.csrf_hash, settings):
        raise AuthorizationError("CSRF_INVALID", "页面安全令牌已过期，请刷新", 403)


def require_ready(context: AuthContext) -> AuthContext:
    """Require completion of the first-login password change."""

    if context.user.must_change_password:
        raise AuthorizationError(
            "PASSWORD_CHANGE_REQUIRED", "首次登录必须修改密码", 403
        )
    return context


def require_admin(context: AuthContext) -> AuthContext:
    """Require an active administrator."""

    require_ready(context)
    if context.user.role != "admin":
        raise AuthorizationError("ADMIN_REQUIRED", "需要管理员权限", 403)
    return context


def change_password(
    db: Session,
    context: AuthContext,
    current_password: str,
    new_password: str,
) -> None:
    """Replace the current password and revoke other browser sessions."""

    if not verify_password(context.user.password_hash, current_password):
        raise AuthenticationError("CURRENT_PASSWORD_INVALID", "当前密码错误", 400)
    context.user.password_hash = hash_password(new_password)
    context.user.must_change_password = False
    db.execute(
        update(WebSession)
        .where(
            WebSession.user_id == context.user.id,
            WebSession.id != context.session.id,
            WebSession.revoked_at.is_(None),
        )
        .values(revoked_at=utc_now())
    )
    db.commit()


def revoke_session(db: Session, context: AuthContext) -> None:
    """Revoke the current browser session idempotently."""

    if context.session.revoked_at is None:
        context.session.revoked_at = utc_now()
        db.commit()


def create_child_user(db: Session, username: str) -> tuple[User, str]:
    """Create an active child user and return its password exactly once."""

    try:
        canonical = normalize_username(username)
    except ValueError as error:
        raise AuthorizationError("USERNAME_INVALID", str(error), 422) from error
    if db.scalar(select(User.id).where(User.username == canonical)) is not None:
        raise AuthorizationError("USERNAME_EXISTS", "用户名已存在", 409)
    temporary_password = generate_password()
    user = User(
        username=canonical,
        password_hash=hash_password(temporary_password),
        role="user",
        status="active",
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temporary_password


def set_child_user_status(db: Session, user: User, status: str) -> None:
    """Enable or disable one non-administrator account."""

    if user.role == "admin":
        raise AuthorizationError(
            "ADMIN_STATUS_PROTECTED", "不能通过子用户接口修改管理员", 409
        )
    if status not in {"active", "disabled"}:
        raise AuthorizationError("USER_STATUS_INVALID", "用户状态无效", 422)
    user.status = status
    if status == "disabled":
        db.execute(
            update(WebSession)
            .where(WebSession.user_id == user.id, WebSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
    db.commit()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
