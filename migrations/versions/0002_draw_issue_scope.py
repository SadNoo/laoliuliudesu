"""Enforce the approved 2026 issue 048 start boundary.

Revision ID: 0002_draw_issue_scope
Revises: 0001_initial
Create Date: 2026-08-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_draw_issue_scope"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("draw_records") as batch_op:
        batch_op.create_check_constraint(
            "ck_draw_approved_issue_scope",
            "issue >= '2026048' AND issue <= '2026999'",
        )


def downgrade() -> None:
    with op.batch_alter_table("draw_records") as batch_op:
        batch_op.drop_constraint(
            "ck_draw_approved_issue_scope",
            type_="check",
        )
