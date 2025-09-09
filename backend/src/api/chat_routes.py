from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, AsyncGenerator
import json
from datetime import datetime

from ..database import get_db
from ..services.chat_service import get_chat_service
from ..models.conversation import ConversationCreateRequest, ConversationResponse
from ..models.chat_message import (
    ChatMessageRequest, 
    ChatMessageResponse, 
    MessageType,
    StreamingChatEvent
)

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/stream")
async def stream_chat(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Stream AI chat responses in real-time using Server-Sent Events
    
    - **conversation_id**: Optional existing conversation ID
    - **message**: User message content
    - **file_id**: Optional file ID for context
    - **user_id**: Optional user ID
    - **temperature**: AI response creativity (0.0-1.0)
    - **max_tokens**: Maximum response length
    
    Returns streaming SSE response with chat chunks
    """
    try:
        chat_service = get_chat_service()
        
        async def generate_stream() -> AsyncGenerator[str, None]:
            try:
                # Create or get conversation
                conversation_id = request.conversation_id
                if not conversation_id:
                    conversation_data = {
                        "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                        "user_id": getattr(request, 'user_id', None),
                        "file_id": getattr(request, 'file_id', None)
                    }
                    conversation = await chat_service.create_conversation(conversation_data)
                    conversation_id = conversation.id
                
                # Add user message
                user_message_data = {
                    "conversation_id": conversation_id,
                    "content": request.message,
                    "message_type": MessageType.USER,
                    "user_id": getattr(request, 'user_id', None)
                }
                user_message = await chat_service.add_message(user_message_data)
                
                # Send user message confirmation
                user_chunk = StreamingChatEvent(
                    conversation_id=conversation_id,
                    message_id=user_message.id,
                    content=request.message,
                    event_type="user_message",
                    is_complete=True,
                    timestamp=datetime.utcnow()
                )
                yield f"data: {user_chunk.model_dump_json()}\n\n"
                
                # Start assistant message
                assistant_message_data = {
                    "conversation_id": conversation_id,
                    "content": "",
                    "message_type": MessageType.ASSISTANT,
                    "user_id": getattr(request, 'user_id', None)
                }
                assistant_message = await chat_service.add_message(assistant_message_data)
                
                # Stream AI response
                full_content = ""
                async for chunk in chat_service.stream_chat_response(
                    conversation_id=conversation_id,
                    message=request.message,
                    file_id=getattr(request, 'file_id', None),
                    temperature=getattr(request, 'temperature', 0.7),
                    max_tokens=getattr(request, 'max_tokens', 1000)
                ):
                    full_content += chunk.content
                    
                    # Send streaming chunk
                    response_chunk = StreamingChatEvent(
                        conversation_id=conversation_id,
                        message_id=assistant_message.id,
                        content=chunk.content,
                        event_type="assistant_response",
                        is_complete=False,
                        timestamp=datetime.utcnow()
                    )
                    yield f"data: {response_chunk.model_dump_json()}\n\n"
                
                # Update message with full content
                await chat_service.update_message_content(assistant_message.id, full_content)
                
                # Send completion chunk
                final_chunk = StreamingChatEvent(
                    conversation_id=conversation_id,
                    message_id=assistant_message.id,
                    content="",
                    event_type="complete",
                    is_complete=True,
                    timestamp=datetime.utcnow()
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                
            except Exception as e:
                # Send error chunk
                error_chunk = StreamingChatEvent(
                    conversation_id=conversation_id if 'conversation_id' in locals() else None,
                    message_id=None,
                    content=f"Error: {str(e)}",
                    event_type="error",
                    is_complete=True,
                    timestamp=datetime.utcnow()
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat streaming failed: {str(e)}"
        )


@router.post("/index/{file_id}")
async def index_file_for_chat(
    file_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: Optional[str] = None
):
    """
    Index a file for AI chat context using LlamaIndex
    
    - **file_id**: UUID of the file to index
    - **user_id**: Optional user ID for ownership
    
    Returns indexing status and starts background processing
    """
    try:
        chat_service = get_chat_service()
        
        # Check if file exists and is processed
        from ..services.file_service import FileService
        file_service = FileService(db)
        file_record = await file_service.get_file(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        if file_record.processing_status.value != "completed":
            raise HTTPException(
                status_code=400,
                detail="File must be fully processed before indexing"
            )
        
        # Start indexing in background
        background_tasks.add_task(
            chat_service.index_file_async,
            file_id,
            user_id
        )
        
        return {
            "message": "File indexing started",
            "file_id": file_id,
            "status": "indexing",
            "estimated_time_minutes": 2
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File indexing failed: {str(e)}"
        )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    skip: int = 0,
    limit: int = 50,
    user_id: Optional[str] = None,
    file_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List chat conversations with optional filtering
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (max 100)
    - **user_id**: Filter by user ID
    - **file_id**: Filter by associated file
    
    Returns list of conversation records
    """
    try:
        if limit > 100:
            limit = 100
        
        chat_service = get_chat_service()
        conversations = await chat_service.list_conversations(
            skip=skip,
            limit=limit,
            user_id=user_id,
            file_id=file_id
        )
        
        return conversations
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get conversation details with messages
    
    - **conversation_id**: UUID of the conversation
    
    Returns conversation with all messages
    """
    try:
        chat_service = get_chat_service()
        conversation = await chat_service.get_conversation(conversation_id)
        
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        return conversation
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation: {str(e)}"
        )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation and all its messages
    
    - **conversation_id**: UUID of the conversation to delete
    
    Returns success message
    """
    try:
        chat_service = get_chat_service()
        success = await chat_service.delete_conversation(conversation_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )
        
        return {"message": "Conversation deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.post("/messages/{message_id}/feedback")
async def add_message_feedback(
    message_id: str,
    feedback_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Add feedback (thumbs up/down, rating) to a chat message
    
    - **message_id**: UUID of the message
    - **feedback_data**: Feedback information (rating, helpful, etc.)
    
    Returns updated message
    """
    try:
        chat_service = get_chat_service()
        updated_message = await chat_service.add_message_feedback(message_id, feedback_data)
        
        if not updated_message:
            raise HTTPException(
                status_code=404,
                detail="Message not found"
            )
        
        return updated_message
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add feedback: {str(e)}"
        )