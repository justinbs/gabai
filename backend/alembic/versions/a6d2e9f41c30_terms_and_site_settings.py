"""record terms acceptance, and keep the barangay's details and look in the database

Revision ID: a6d2e9f41c30
Revises: f3a9c2e7b815
Create Date: 2026-10-01 09:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a6d2e9f41c30'
down_revision: str | None = 'f3a9c2e7b815'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THEMES = ('green', 'blue', 'maroon', 'teal', 'purple', 'brown')


def upgrade() -> None:
    # Null for existing accounts, so they're asked to accept at next sign-in.
    op.add_column('users', sa.Column('terms_accepted_version', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))

    # Single row, enforced by the CHECK on id.
    op.create_table(
        'site_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('barangay_name', sa.String(100), nullable=False),
        sa.Column('place', sa.String(100), nullable=False),
        sa.Column('address', sa.String(200), nullable=True),
        sa.Column('hotline', sa.String(50), nullable=True),
        sa.Column('office_hours', sa.String(100), nullable=True),
        sa.Column('theme', sa.String(10), nullable=False, server_default='green'),
        sa.Column('logo_path', sa.String(255), nullable=True),
        sa.Column('logo_version', sa.String(40), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('id = 1', name='ck_site_settings_single_row'),
        sa.CheckConstraint(
            'theme IN (' + ', '.join(f"'{t}'" for t in THEMES) + ')',
            name='ck_site_settings_theme',
        ),
    )
    # Contact fields start empty until an admin fills them in.
    op.execute(
        "INSERT INTO site_settings (id, barangay_name, place) "
        "VALUES (1, 'Barangay V (Singko)', 'Amaya, Tanza, Cavite')"
    )


def downgrade() -> None:
    op.drop_table('site_settings')
    op.drop_column('users', 'terms_accepted_at')
    op.drop_column('users', 'terms_accepted_version')
