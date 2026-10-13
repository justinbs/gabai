"""optional problem locations, and linking duplicate reports

Revision ID: e7a9c3d1b248
Revises: d4f2b7c9e016
Create Date: 2026-10-13 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e7a9c3d1b248'
down_revision: str | None = 'd4f2b7c9e016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Empty until the admin adds puroks or streets.
    op.create_table(
        'locations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=80), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0')),
    )
    op.add_column('requests', sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id'), nullable=True))
    op.add_column('requests', sa.Column('duplicate_of_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=True))
    op.create_check_constraint('ck_requests_not_own_duplicate', 'requests', 'duplicate_of_id <> id')
    op.create_index('ix_requests_duplicate_of_id', 'requests', ['duplicate_of_id'])
    # Duplicate and surge checks look back 72 hours and one hour.
    op.create_index('ix_requests_created_at', 'requests', ['created_at'])

    op.create_table(
        'duplicate_suggestions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('decision', sa.String(length=10), nullable=True),
        sa.Column('decided_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('request_id', 'candidate_id', name='uq_duplicate_suggestion_pair'),
        sa.CheckConstraint("decision IS NULL OR decision IN ('linked', 'dismissed')", name='ck_duplicate_decision'),
    )
    op.create_index('ix_duplicate_suggestions_request_id', 'duplicate_suggestions', ['request_id'])


def downgrade() -> None:
    op.drop_index('ix_duplicate_suggestions_request_id', table_name='duplicate_suggestions')
    op.drop_table('duplicate_suggestions')
    op.drop_index('ix_requests_created_at', table_name='requests')
    op.drop_index('ix_requests_duplicate_of_id', table_name='requests')
    op.drop_constraint('ck_requests_not_own_duplicate', 'requests', type_='check')
    op.drop_column('requests', 'duplicate_of_id')
    op.drop_column('requests', 'location_id')
    op.drop_table('locations')
