"""
Chat service for AI-powered conversations about EDI data
Integrates with LlamaIndex for intelligent file analysis and Q&A
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator, Any
import pandas as pd

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from ..database import Conversation, ChatMessage, File, get_async_session
from ..models.conversation import (
    ConversationCreateRequest, ConversationResponse, ConversationStatus,
    ConversationDetailResponse, ConversationSummary, ConversationMetrics
)
from ..models.chat_message import (
    ChatMessageRequest, ChatMessageResponse, StreamingChatEvent,
    MessageRole, MessageStatus, MessageType, MessageContext, MessageMetadata
)
from ..lib.ai_chat import get_ai_chat, initialize_ai_chat
from .file_service import get_file_service

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing AI chat conversations"""
    
    def __init__(self):
        self.ai_chat = get_ai_chat()  # Get global AI chat instance
        self.file_service = get_file_service()
        
    async def create_conversation(self, 
                                  file_id: str,
                                  title: Optional[str] = None,
                                  initial_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new conversation for a file
        
        Args:
            file_id: File UUID to chat about
            title: Optional conversation title
            initial_message: Optional initial user message
            
        Returns:
            Created conversation info
        """
        try:
            # Verify file exists and is ready for chat
            file_data = await self.file_service.get_file_for_chat(file_id)
            if not file_data['success']:
                return {
                    'success': False,
                    'error': f'File not ready for chat: {file_data.get("error", "Unknown error")}',
                    'status_code': 404 if 'not found' in file_data.get('error', '').lower() else 400
                }
            
            async with get_async_session() as session:
                # Create conversation record
                conversation_id = str(uuid.uuid4())
                
                conversation = Conversation(
                    id=conversation_id,
                    file_id=file_id,
                    title=title or f"Chat about {file_data['data']['filename']}",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    message_count=0
                )
                
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)
                
                # Add initial message if provided
                if initial_message:
                    await self._add_message(
                        session,
                        conversation_id,
                        MessageRole.USER,
                        initial_message,
                        MessageType.QUESTION
                    )
                    conversation.message_count = 1
                    await session.commit()
                
                # Convert to response format
                response_data = ConversationResponse(
                    conversation_id=conversation_id,
                    file_id=file_id,
                    title=conversation.title,
                    status=ConversationStatus.ACTIVE,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    message_count=conversation.message_count,
                    correlation_id=str(uuid.uuid4())
                )
                
                logger.info(f"Created conversation {conversation_id} for file {file_id}")
                
                return {
                    'success': True,
                    'data': response_data.dict()
                }
                
        except Exception as e:
            logger.error(f"Failed to create conversation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def chat_stream(self, 
                          message: str,
                          file_id: str,
                          conversation_id: Optional[str] = None,
                          include_context: bool = True,
                          **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream AI chat response for a message
        
        Args:
            message: User message
            file_id: File to query about
            conversation_id: Optional existing conversation ID
            include_context: Whether to include file context
            **kwargs: Additional chat parameters
            
        Yields:
            Streaming chat events
        """
        try:
            # Create conversation if not provided
            if not conversation_id:
                conv_result = await self.create_conversation(file_id, initial_message=message)
                if not conv_result['success']:
                    yield {
                        'type': 'error',
                        'error_code': 'CONVERSATION_CREATE_FAILED',
                        'error_message': conv_result['error'],
                        'timestamp': datetime.now().isoformat()
                    }
                    return
                conversation_id = conv_result['data']['conversation_id']
            else:
                # Verify conversation exists and add user message
                async with get_async_session() as session:
                    conversation = await session.get(Conversation, conversation_id)
                    if not conversation:
                        yield {
                            'type': 'error',
                            'error_code': 'CONVERSATION_NOT_FOUND',
                            'error_message': 'Conversation not found',
                            'timestamp': datetime.now().isoformat()
                        }
                        return
                    
                    # Add user message
                    await self._add_message(
                        session,
                        conversation_id,
                        MessageRole.USER,
                        message,
                        MessageType.QUESTION
                    )
                    
                    # Update conversation
                    conversation.message_count += 1
                    conversation.updated_at = datetime.utcnow()
                    await session.commit()
            
            # Get file data for AI context
            if include_context:
                file_data = await self.file_service.get_file_data(file_id)
                if not file_data['success']:
                    yield {
                        'type': 'error',
                        'error_code': 'FILE_DATA_ERROR',
                        'error_message': file_data['error'],
                        'timestamp': datetime.now().isoformat()
                    }
                    return
                
                # Ensure file is indexed for AI
                if not self.ai_chat.is_file_indexed(file_id):
                    # Index the file data
                    mock_parsed_data = pd.DataFrame()  # Would be actual parsed data in production
                    field_definitions = file_data['data'].get('field_definitions', {})
                    file_metadata = {'file_id': file_id}
                    
                    index_result = await self.ai_chat.index_file_data(
                        file_id, mock_parsed_data, field_definitions, file_metadata
                    )
                    
                    if not index_result['success']:
                        yield {
                            'type': 'error',
                            'error_code': 'INDEXING_FAILED',
                            'error_message': index_result.get('error', 'Failed to index file'),
                            'timestamp': datetime.now().isoformat()
                        }
                        return
            
            # Start AI chat streaming
            assistant_message_content = ""
            start_time = datetime.now()
            
            async for event in self.ai_chat.chat_stream(
                file_id=file_id,
                message=message,
                conversation_id=conversation_id,
                include_context=include_context,
                **kwargs
            ):
                # Forward AI events and collect content
                if event['type'] == 'chunk':
                    assistant_message_content += event.get('content', '')
                
                # Add conversation_id to all events
                event['conversation_id'] = conversation_id
                yield event
            
            # Store assistant response in database
            if assistant_message_content:
                async with get_async_session() as session:
                    # Add assistant message
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    await self._add_message(
                        session,
                        conversation_id,
                        MessageRole.ASSISTANT,
                        assistant_message_content,
                        MessageType.RESPONSE,
                        metadata={
                            'response_time_seconds': response_time,
                            'include_context': include_context,
                            'file_context_used': include_context
                        }
                    )
                    
                    # Update conversation
                    conversation = await session.get(Conversation, conversation_id)
                    if conversation:
                        conversation.message_count += 1
                        conversation.updated_at = datetime.utcnow()
                        await session.commit()
            
        except Exception as e:
            logger.error(f"Chat stream error: {str(e)}")
            yield {
                'type': 'error',
                'error_code': 'CHAT_STREAM_ERROR',
                'error_message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def index_file_for_chat(self, file_id: str, **kwargs) -> Dict[str, Any]:
        """
        Index a file for AI chat capabilities
        
        Args:
            file_id: File UUID to index
            **kwargs: Indexing parameters
            
        Returns:
            Indexing result
        """
        try:
            # Get file data
            file_data = await self.file_service.get_file_data(file_id)
            if not file_data['success']:
                return {
                    'success': False,
                    'error': file_data['error'],
                    'status_code': 404 if 'not found' in file_data['error'].lower() else 400
                }
            
            # Check if already indexed
            if self.ai_chat.is_file_indexed(file_id):
                return {
                    'success': True,
                    'status': 'already_indexed',
                    'message': 'File is already indexed for chat',
                    'indexed_at': 'previously',
                    'chunk_count': 'available'
                }
            
            # Start indexing
            data = file_data['data']
            
            # Create mock parsed data for POC (in production, would retrieve actual data)
            field_definitions = data.get('field_definitions', {})
            mock_parsed_data = pd.DataFrame()
            file_metadata = {
                'file_id': file_id,
                'filename': data.get('filename', ''),
                'record_count': data.get('record_count', 0)
            }
            
            # Update file status to indexing
            await self.file_service.update_file_status_external(
                file_id, 
                status=None,  # Would use FileStatus.INDEXING in production
                progress=10
            )
            
            # Perform indexing
            index_result = await self.ai_chat.index_file_data(
                file_id=file_id,
                parsed_data=mock_parsed_data,
                field_definitions=field_definitions,
                file_metadata=file_metadata,
                **kwargs
            )
            
            if index_result['success']:
                # Update file status to indexed
                await self.file_service.update_file_status_external(
                    file_id,
                    status=None,  # Would use FileStatus.INDEXED in production
                    progress=100
                )
                
                return {
                    'success': True,
                    'file_id': file_id,
                    'status': 'indexing_started' if index_result.get('processing_time_seconds', 0) > 5 else 'completed',
                    'document_count': index_result.get('document_count', 0),
                    'chunk_count': index_result.get('chunk_count', 0),
                    'processing_time_seconds': index_result.get('processing_time_seconds', 0),
                    'indexed_at': index_result.get('indexed_at'),
                    'job_id': str(uuid.uuid4()),
                    'estimated_completion': datetime.now().isoformat()
                }
            else:
                # Update file status to failed
                await self.file_service.update_file_status_external(
                    file_id,
                    status=None,  # Would use FileStatus.FAILED
                    error_message=f"Indexing failed: {index_result.get('error', 'Unknown error')}"
                )
                
                return {
                    'success': False,
                    'error': index_result.get('error', 'Indexing failed')
                }
                
        except Exception as e:
            logger.error(f"Failed to index file for chat: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_conversation(self, conversation_id: str, include_messages: bool = False) -> Dict[str, Any]:
        """
        Get conversation details
        
        Args:
            conversation_id: Conversation UUID
            include_messages: Whether to include message history
            
        Returns:
            Conversation details
        """
        try:
            async with get_async_session() as session:
                query = select(Conversation).where(Conversation.id == conversation_id)
                if include_messages:
                    query = query.options(selectinload(Conversation.messages))
                
                result = await session.execute(query)
                conversation = result.scalar_one_or_none()
                
                if not conversation:
                    return {
                        'success': False,
                        'error': 'Conversation not found',
                        'status_code': 404
                    }
                
                # Get file info
                file_record = await session.get(File, conversation.file_id)
                file_name = file_record.filename if file_record else 'Unknown'
                file_status = file_record.status if file_record else 'unknown'
                
                # Create response
                if include_messages:
                    # Get messages
                    messages_query = select(ChatMessage).where(
                        ChatMessage.conversation_id == conversation_id
                    ).order_by(ChatMessage.timestamp)
                    
                    messages_result = await session.execute(messages_query)
                    messages = messages_result.scalars().all()
                    
                    response_data = ConversationDetailResponse(
                        conversation_id=conversation.id,
                        file_id=conversation.file_id,
                        title=conversation.title,
                        status=ConversationStatus.ACTIVE,
                        created_at=conversation.created_at,
                        updated_at=conversation.updated_at,
                        message_count=conversation.message_count,
                        last_message_at=messages[-1].timestamp if messages else None,
                        last_message_preview=messages[-1].content[:200] if messages else None,
                        file_name=file_name,
                        file_status=file_status,
                        correlation_id=str(uuid.uuid4())
                    )
                else:
                    response_data = ConversationResponse(
                        conversation_id=conversation.id,
                        file_id=conversation.file_id,
                        title=conversation.title,
                        status=ConversationStatus.ACTIVE,
                        created_at=conversation.created_at,
                        updated_at=conversation.updated_at,
                        message_count=conversation.message_count,
                        correlation_id=str(uuid.uuid4())
                    )
                
                return {
                    'success': True,
                    'data': response_data.dict()
                }
                
        except Exception as e:
            logger.error(f"Failed to get conversation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_conversations(self, 
                                 file_id: Optional[str] = None,
                                 page: int = 1,
                                 page_size: int = 20) -> Dict[str, Any]:
        """
        List conversations with optional filtering
        
        Args:
            file_id: Optional file filter
            page: Page number
            page_size: Items per page
            
        Returns:
            List of conversations
        """
        try:
            async with get_async_session() as session:
                query = select(Conversation)
                
                if file_id:
                    query = query.where(Conversation.file_id == file_id)
                
                # Add pagination
                offset = (page - 1) * page_size
                query = query.offset(offset).limit(page_size).order_by(Conversation.updated_at.desc())
                
                result = await session.execute(query)
                conversations = result.scalars().all()
                
                # Convert to response format
                conversation_responses = []
                for conv in conversations:
                    response = ConversationResponse(
                        conversation_id=conv.id,
                        file_id=conv.file_id,
                        title=conv.title,
                        status=ConversationStatus.ACTIVE,
                        created_at=conv.created_at,
                        updated_at=conv.updated_at,
                        message_count=conv.message_count
                    )
                    conversation_responses.append(response)
                
                return {
                    'success': True,
                    'data': {
                        'conversations': [conv.dict() for conv in conversation_responses],
                        'total_count': len(conversation_responses),
                        'page': page,
                        'page_size': page_size,
                        'has_more': len(conversation_responses) == page_size
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to list conversations: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _add_message(self,
                           session: AsyncSession,
                           conversation_id: str,
                           role: MessageRole,
                           content: str,
                           message_type: MessageType,
                           metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add a message to a conversation
        
        Args:
            session: Database session
            conversation_id: Conversation UUID
            role: Message role
            content: Message content
            message_type: Type of message
            metadata: Optional metadata
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        
        message = ChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            role=role.value,
            content=content,
            timestamp=datetime.utcnow(),
            message_metadata=metadata or {}
        )
        
        session.add(message)
        return message_id
    
    async def delete_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """
        Delete a conversation and all messages
        
        Args:
            conversation_id: Conversation UUID
            
        Returns:
            Deletion result
        """
        try:
            async with get_async_session() as session:
                conversation = await session.get(Conversation, conversation_id)
                
                if not conversation:
                    return {
                        'success': False,
                        'error': 'Conversation not found',
                        'status_code': 404
                    }
                
                # Delete conversation (cascades to messages)
                await session.delete(conversation)
                await session.commit()
                
                logger.info(f"Deleted conversation {conversation_id}")
                
                return {
                    'success': True,
                    'message': 'Conversation deleted successfully'
                }
                
        except Exception as e:
            logger.error(f"Failed to delete conversation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get chat system statistics"""
        ai_stats = self.ai_chat.get_system_stats()
        
        return {
            'chat_service_status': 'active',
            'ai_backend': ai_stats,
            'indexed_files': len(ai_stats.get('indexed_files_count', 0)),
            'active_conversations': ai_stats.get('active_conversations_count', 0)
        }


# Global chat service instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get global chat service instance"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service