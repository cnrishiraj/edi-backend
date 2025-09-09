"""
Database configuration and SQLite setup for EDI POC
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, 
    DateTime, 
    ForeignKey, 
    Integer, 
    String, 
    Text, 
    Float,
    JSON,
    create_engine,
    Index
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# Database URL for SQLite (async)
DATABASE_URL = "sqlite+aiosqlite:///./edi_poc.db"

# Engine and session will be created when needed
async_engine = None
AsyncSessionLocal = None

# Base class for models
Base = declarative_base()


def generate_uuid() -> str:
    """Generate UUID string for primary keys"""
    return str(uuid.uuid4())


class File(Base):
    """File model for uploaded SmithRx claims files"""
    __tablename__ = "files"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="uploading")  # uploading, parsing, parsed, indexed, failed
    content_hash = Column(String(64))
    record_count = Column(Integer)
    file_metadata = Column(JSON)  # File statistics and metadata


class Mapping(Base):
    """Mapping model for field mappings between SmithRx and VBA schema"""
    __tablename__ = "mappings"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    field_mappings = Column(JSON, nullable=False)  # Array of field mapping objects
    confidence_score = Column(Float, default=0.0)
    status = Column(String(20), default="generating")  # generating, draft, approved


class Conversation(Base):
    """Conversation model for AI chat sessions"""
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count = Column(Integer, default=0)


class ChatMessage(Base):
    """Chat message model for individual messages in conversations"""
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    message_metadata = Column(JSON)  # Response time, tokens, sources, etc.


class ProcessingJob(Base):
    """Processing job model for tracking file processing tasks"""
    __tablename__ = "processing_jobs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    job_type = Column(String(20), nullable=False)  # parse, index, map
    status = Column(String(20), default="queued")  # queued, running, completed, failed
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(Text)


# Create indexes for better performance
Index('idx_files_status', File.status)
Index('idx_conversations_file_id', Conversation.file_id)
Index('idx_chat_messages_conversation_id', ChatMessage.conversation_id)
Index('idx_processing_jobs_file_id', ProcessingJob.file_id)
Index('idx_processing_jobs_status', ProcessingJob.status)


def _create_engine_and_session():
    """Create engine and session factory"""
    global async_engine, AsyncSessionLocal
    
    if async_engine is None:
        async_engine = create_async_engine(DATABASE_URL, echo=True)
        AsyncSessionLocal = async_sessionmaker(
            async_engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )


def get_async_session():
    """Get async database session context manager"""
    _create_engine_and_session()
    return AsyncSessionLocal()


async def get_db() -> AsyncSession:
    """FastAPI dependency for database session"""
    _create_engine_and_session()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_database():
    """Initialize database tables"""
    _create_engine_and_session()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_database():
    """Close database connections"""
    if async_engine:
        await async_engine.dispose()