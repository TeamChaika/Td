"""add_starts_at_index

Revision ID: 9c341d174a21
Revises: 682febd8daff
Create Date: 2026-05-09 17:16:55.532048

Функциональный индекс на schedule->>'starts_at' для ускорения
фильтрации и сортировки событий по дате начала.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c341d174a21"
down_revision: str | Sequence[str] | None = "682febd8daff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создать индекс на JSONB-поле schedule->>'starts_at'."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_events_starts_at "
        "ON events ((schedule->>'starts_at'))"
    )


def downgrade() -> None:
    """Удалить индекс."""
    op.execute("DROP INDEX IF EXISTS ix_events_starts_at")