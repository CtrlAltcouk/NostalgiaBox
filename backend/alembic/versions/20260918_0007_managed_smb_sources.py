"""Add non-secret managed SMB source configuration.

Revision ID: 20260918_0007
Revises: 20260915_0006
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
revision = "20260918_0007"
down_revision: str | Sequence[str] | None = "20260915_0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    for name in ("smb_host", "smb_share", "smb_subpath", "credential_ref"):
        op.add_column("media_sources", sa.Column(name, sa.String(), nullable=True))

def downgrade() -> None:
    for name in ("credential_ref", "smb_subpath", "smb_share", "smb_host"):
        op.drop_column("media_sources", name)
