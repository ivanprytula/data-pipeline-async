"""add_partial_index_active_source

Revision ID: 21878e22a57b
Revises: 2a45941f1152
Create Date: 2026-04-17 20:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21878e22a57b'
down_revision: Union[str, Sequence[str], None] = '2a45941f1152'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add partial index on (source) WHERE deleted_at IS NULL.

    This index optimizes the common query pattern:
        WHERE deleted_at IS NULL AND source = ?

    By using a partial index, we:
    - Index only non-deleted rows (much smaller than full table)
    - Minimize write overhead (INSERTs always add to active set; soft-deletes remove)
    - Support both query shapes: soft-delete filter AND source filter
    """
    op.create_index(
        'ix_records_active_source',
        'records',
        ['source'],
        postgresql_where='(deleted_at IS NULL)',
    )


def downgrade() -> None:
    """Remove partial index."""
    op.drop_index('ix_records_active_source', table_name='records')
