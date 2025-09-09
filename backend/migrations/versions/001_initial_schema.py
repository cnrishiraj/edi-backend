"""Initial schema for EDI POC

Revision ID: 001
Revises: 
Create Date: 2025-09-08 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Files table
    op.create_table('files',
        sa.Column('id', sa.String(), nullable=False, default=sa.text('(uuid4())')),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('upload_timestamp', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(20), nullable=True, default='uploading'),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Mappings table
    op.create_table('mappings',
        sa.Column('id', sa.String(), nullable=False, default=sa.text('(uuid4())')),
        sa.Column('file_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('field_mappings', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('status', sa.String(20), nullable=True, default='generating'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Conversations table
    op.create_table('conversations',
        sa.Column('id', sa.String(), nullable=False, default=sa.text('(uuid4())')),
        sa.Column('file_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('message_count', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Chat messages table
    op.create_table('chat_messages',
        sa.Column('id', sa.String(), nullable=False, default=sa.text('(uuid4())')),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Processing jobs table
    op.create_table('processing_jobs',
        sa.Column('id', sa.String(), nullable=False, default=sa.text('(uuid4())')),
        sa.Column('file_id', sa.String(), nullable=False),
        sa.Column('job_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=True, default='queued'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_files_status', 'files', ['status'])
    op.create_index('idx_conversations_file_id', 'conversations', ['file_id'])  
    op.create_index('idx_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('idx_processing_jobs_file_id', 'processing_jobs', ['file_id'])
    op.create_index('idx_processing_jobs_status', 'processing_jobs', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order to handle foreign keys
    op.drop_table('processing_jobs')
    op.drop_table('chat_messages') 
    op.drop_table('conversations')
    op.drop_table('mappings')
    op.drop_table('files')