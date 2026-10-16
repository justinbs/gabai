"""referred status, and the agencies a concern can be referred to

Revision ID: f1c4a8d2b693
Revises: b5d8f2a4c716
Create Date: 2026-10-15 09:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f1c4a8d2b693'
down_revision: str | None = 'b5d8f2a4c716'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

agencies = sa.table(
    "referral_agencies",
    sa.column("name", sa.String),
    sa.column("sort_order", sa.Integer),
)


def upgrade() -> None:
    # A new enum value can't be used in the transaction that adds it, so commit
    # first. Contact details are left empty on purpose: the barangay confirms them.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE request_status ADD VALUE IF NOT EXISTS 'referred'")

    op.create_table(
        'referral_agencies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=100), nullable=False, unique=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('hours', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.String(length=300), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
    )
    op.bulk_insert(agencies, [
        {"name": "Meralco", "sort_order": 1},
        {"name": "Water service provider", "sort_order": 2},
        {"name": "Bureau of Fire Protection (BFP)", "sort_order": 3},
        {"name": "Philippine National Police (PNP)", "sort_order": 4},
    ])

    op.add_column('requests', sa.Column('referred_agency_id', sa.Integer(), sa.ForeignKey('referral_agencies.id'), nullable=True))
    op.add_column('requests', sa.Column('referred_at', sa.DateTime(timezone=True), nullable=True))
    # Encrypted by the application, so plain text type.
    op.add_column('requests', sa.Column('referral_note', sa.Text(), nullable=True))
    op.create_check_constraint(
        'ck_requests_referred_has_agency',
        'requests',
        "status::text <> 'referred' OR referred_agency_id IS NOT NULL",
    )


def downgrade() -> None:
    # Postgres can't drop an enum value. 'referred' stays in the type, and any
    # request still referred goes back to the review queue.
    op.drop_constraint('ck_requests_referred_has_agency', 'requests', type_='check')
    op.execute("UPDATE requests SET status = 'under_review' WHERE status::text = 'referred'")
    op.drop_column('requests', 'referral_note')
    op.drop_column('requests', 'referred_at')
    op.drop_column('requests', 'referred_agency_id')
    op.drop_table('referral_agencies')