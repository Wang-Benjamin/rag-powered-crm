"""add outreach tables, smtp_credentials, and outreach columns on user_profiles

Revision ID: b7c8d9e0f1a2
Revises: 6e0b4bf58f68
Create Date: 2026-04-11 00:00:00.000000

Add outreach_alias and outreach_display_name columns to user_profiles.
Create outreach_conversations, outreach_messages, and smtp_credentials tables
for the outreach email pipeline and SMTP email configuration.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b7c8d9e0f1a2'
down_revision = '6e0b4bf58f68'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add outreach columns to user_profiles
    op.add_column('user_profiles', sa.Column('outreach_alias', sa.String(255), nullable=True))
    op.add_column('user_profiles', sa.Column('outreach_display_name', sa.String(255), nullable=True))
    op.create_unique_constraint('user_profiles_outreach_alias_key', 'user_profiles', ['outreach_alias'])

    # Create outreach_conversations table
    op.create_table(
        'outreach_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_email', sa.String(255), nullable=False),
        sa.Column('alias', sa.String(255), nullable=False),
        sa.Column('buyer_email', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='outreach_conversations_pkey'),
    )
    op.create_index('idx_outreach_conv_user', 'outreach_conversations', ['user_email'])
    op.create_index('idx_outreach_conv_buyer', 'outreach_conversations', ['buyer_email'])

    # Create outreach_messages table
    op.create_table(
        'outreach_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.Integer(), sa.ForeignKey('outreach_conversations.id'), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('from_email', sa.String(255), nullable=False),
        sa.Column('to_email', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body_en', sa.Text(), nullable=True),
        sa.Column('body_zh', sa.Text(), nullable=True),
        sa.Column('message_id', sa.String(255), nullable=True),
        sa.Column('in_reply_to', sa.String(255), nullable=True),
        sa.Column('sendgrid_message_id', sa.String(255), nullable=True),
        sa.Column('status', sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='outreach_messages_pkey'),
    )
    op.create_index('idx_outreach_msg_conv', 'outreach_messages', ['conversation_id'])
    op.create_index('idx_outreach_msg_from', 'outreach_messages', ['from_email'])
    op.create_index('idx_outreach_msg_direction', 'outreach_messages', ['direction'])

    # Create smtp_credentials table
    op.create_table(
        'smtp_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_email', sa.String(255), nullable=False),
        sa.Column('provider_name', sa.String(50), server_default=sa.text("'custom'"), nullable=False),
        sa.Column('smtp_host', sa.String(255), nullable=False),
        sa.Column('smtp_port', sa.Integer(), server_default=sa.text('587'), nullable=False),
        sa.Column('smtp_user', sa.String(255), nullable=False),
        sa.Column('smtp_password_encrypted', sa.Text(), nullable=False),
        sa.Column('imap_host', sa.String(255), nullable=True),
        sa.Column('imap_port', sa.Integer(), server_default=sa.text('993'), nullable=True),
        sa.Column('from_name', sa.String(255), nullable=True),
        sa.Column('verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='smtp_credentials_pkey'),
        sa.UniqueConstraint('user_email', name='smtp_credentials_user_email_key'),
    )
    op.create_index('idx_smtp_cred_user', 'smtp_credentials', ['user_email'])


def downgrade() -> None:
    op.drop_table('smtp_credentials')
    op.drop_table('outreach_messages')
    op.drop_table('outreach_conversations')
    op.drop_constraint('user_profiles_outreach_alias_key', 'user_profiles', type_='unique')
    op.drop_column('user_profiles', 'outreach_display_name')
    op.drop_column('user_profiles', 'outreach_alias')
