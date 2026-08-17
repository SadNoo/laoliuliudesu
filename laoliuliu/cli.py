"""Administrative bootstrap and manual synchronization commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from sqlalchemy import select

from laoliuliu.auth import create_child_user
from laoliuliu.config import get_settings
from laoliuliu.db import SessionLocal
from laoliuliu.ingestion import synchronize_current, synchronize_history
from laoliuliu.maintenance import prune_before_approved_start
from laoliuliu.models import User
from laoliuliu.security import (
    generate_password,
    hash_password,
    normalize_username,
)
from laoliuliu.source import SourceClient


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="laoliuliu-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap-admin")
    bootstrap.add_argument("--username", default="admin")
    bootstrap.add_argument("--credentials-file", type=Path, required=True)

    create_user = subparsers.add_parser("create-user")
    create_user.add_argument("--username", required=True)
    create_user.add_argument("--credentials-file", type=Path, required=True)

    subparsers.add_parser("sync-history")
    subparsers.add_parser("sync-current")
    prune = subparsers.add_parser("prune-before-start")
    prune.add_argument("--confirm-start-issue", required=True)
    return parser


def entrypoint() -> None:
    """Execute one bounded administrator command."""

    args = _parser().parse_args()
    if args.command in {"bootstrap-admin", "create-user"}:
        _create_identity(
            username=args.username,
            role="admin" if args.command == "bootstrap-admin" else "user",
            credentials_file=args.credentials_file,
        )
        return

    settings = get_settings()
    if args.command == "prune-before-start":
        if args.confirm_start_issue != settings.data_start_issue_id:
            raise SystemExit(f"confirmation must equal {settings.data_start_issue_id}")
        with SessionLocal() as db:
            prune_result = prune_before_approved_start(db)
        print(json.dumps(prune_result.__dict__, ensure_ascii=False, sort_keys=True))
        return

    client = SourceClient(settings)
    with SessionLocal() as db:
        result = (
            synchronize_history(db, client, settings)
            if args.command == "sync-history"
            else synchronize_current(db, client, settings)
        )
    print(json.dumps(result.__dict__, ensure_ascii=False, sort_keys=True))


def _create_identity(username: str, role: str, credentials_file: Path) -> None:
    canonical = normalize_username(username)
    if credentials_file.exists():
        raise SystemExit("credentials file already exists")
    credentials_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.username == canonical)) is not None:
            raise SystemExit("username already exists")
        if role == "admin":
            password = generate_password()
            user = User(
                username=canonical,
                password_hash=hash_password(password),
                role="admin",
                status="active",
                must_change_password=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user, password = create_child_user(db, canonical)
    payload = {"username": user.username, "temporary_password": password, "role": role}
    descriptor = os.open(
        credentials_file,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({"created": True, "credentials_file": str(credentials_file)}))


if __name__ == "__main__":
    entrypoint()
