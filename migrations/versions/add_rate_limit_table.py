"""add rate limit table

Revision ID: add_rate_limit_table
Revises: a9935c5f7f60
Create Date: 2024-10-17 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_rate_limit_table'
down_revision = 'a9935c5f7f60'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('rate_limit',
        sa.Column('key', sa.String(255), primary_key=True),
        sa.Column('value', sa.Integer, nullable=False, default=0),
        sa.Column('expiry', sa.DateTime, nullable=False)
    )

def downgrade():
    op.drop_table('rate_limit')
