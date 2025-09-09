"""
Contract tests for POST /chat/stream endpoint (AI chat with streaming)
These tests MUST FAIL initially - no implementation exists yet
"""
import pytest
from httpx import AsyncClient
from fastapi import status
import json


@pytest.mark.asyncio
async def test_chat_stream_success(async_client: AsyncClient):
    """Test successful streaming chat response"""
    request_data = {
        "message": "How many claims are in this file?",
        "file_id": "12345678-1234-1234-1234-123456789012",
        "include_context": True
    }
    
    async with async_client.stream(
        "POST", 
        "/api/v1/chat/stream",
        json=request_data,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # Collect streaming data
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]  # Remove "data: " prefix
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        # Some events might be plain text
                        events.append({"raw": event_data})
        
        # Should have at least start, content chunks, and end events
        assert len(events) >= 3
        
        # First event should be start
        start_event = events[0]
        assert start_event["type"] == "start"
        assert "conversation_id" in start_event
        
        # Middle events should be content chunks
        content_chunks = [e for e in events if e.get("type") == "chunk"]
        assert len(content_chunks) > 0
        
        # Last event should be end
        end_event = events[-1]
        assert end_event["type"] == "end"
        assert "total_tokens" in end_event


@pytest.mark.asyncio
async def test_chat_stream_new_conversation(async_client: AsyncClient):
    """Test starting new conversation"""
    request_data = {
        "message": "What is the average claim amount?",
        "file_id": "12345678-1234-1234-1234-123456789012"
        # No conversation_id - should create new conversation
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream", 
        json=request_data,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        # Get first event
        first_line = await response.aiter_lines().__anext__()
        assert first_line.startswith("data: ")
        
        start_event = json.loads(first_line[6:])
        assert start_event["type"] == "start"
        assert "conversation_id" in start_event
        # Should be a new UUID
        assert len(start_event["conversation_id"]) == 36  # UUID length


@pytest.mark.asyncio
async def test_chat_stream_continue_conversation(async_client: AsyncClient):
    """Test continuing existing conversation"""
    request_data = {
        "message": "What about the highest claim amount?",
        "file_id": "12345678-1234-1234-1234-123456789012",
        "conversation_id": "conv-1234-1234-1234-123456789012"
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=request_data,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        first_line = await response.aiter_lines().__anext__()
        start_event = json.loads(first_line[6:])
        
        # Should continue with same conversation ID
        assert start_event["conversation_id"] == "conv-1234-1234-1234-123456789012"


@pytest.mark.asyncio
async def test_chat_stream_file_not_found(async_client: AsyncClient):
    """Test chat stream with non-existent file"""
    request_data = {
        "message": "How many claims?",
        "file_id": "non-existent-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "file not found" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_file_not_indexed(async_client: AsyncClient):
    """Test chat stream with file not ready for chat (not indexed)"""
    request_data = {
        "message": "Tell me about this file",
        "file_id": "not-indexed-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response_data = response.json()
    assert "not indexed" in response_data["error_message"].lower() or \
           "not processed" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_missing_message(async_client: AsyncClient):
    """Test chat stream with missing message"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012"
        # Missing required "message" field
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    response_data = response.json()
    assert "message" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_missing_file_id(async_client: AsyncClient):
    """Test chat stream with missing file_id"""
    request_data = {
        "message": "How many claims are there?"
        # Missing required "file_id" field
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    response_data = response.json()
    assert "file_id" in response_data["error_message"].lower()


@pytest.mark.asyncio  
async def test_chat_stream_invalid_file_id(async_client: AsyncClient):
    """Test chat stream with invalid file_id format"""
    request_data = {
        "message": "How many claims?",
        "file_id": "invalid-uuid"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "file_id" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_empty_message(async_client: AsyncClient):
    """Test chat stream with empty message"""
    request_data = {
        "message": "",  # Empty message
        "file_id": "12345678-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=request_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    response_data = response.json()
    assert "message" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_chat_stream_error_during_processing(async_client: AsyncClient):
    """Test chat stream when AI processing fails"""
    request_data = {
        "message": "This should trigger an error",
        "file_id": "error-trigger-1234-1234-1234-123456789012"
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=request_data,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        # Should get error event in stream
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    events.append(json.loads(event_data))
        
        # Should have an error event
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) > 0
        
        error_event = error_events[0]
        assert "error_message" in error_event


@pytest.mark.asyncio
async def test_chat_stream_context_disabled(async_client: AsyncClient):
    """Test chat stream with context disabled"""
    request_data = {
        "message": "How many claims?",
        "file_id": "12345678-1234-1234-1234-123456789012", 
        "include_context": False
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=request_data,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        # Should still work, but might have different response
        first_line = await response.aiter_lines().__anext__()
        start_event = json.loads(first_line[6:])
        assert start_event["type"] == "start"