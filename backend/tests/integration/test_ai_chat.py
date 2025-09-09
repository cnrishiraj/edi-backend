"""
Integration tests for AI chat functionality with LlamaIndex
Tests end-to-end chat workflow with real file processing and AI responses
"""
import pytest
import tempfile
import os
from httpx import AsyncClient
from fastapi import status
import asyncio
import json


@pytest.mark.asyncio
async def test_ai_chat_with_indexed_file(async_client: AsyncClient):
    """Test complete AI chat workflow with indexed file"""
    # Create SmithRx test file with realistic data
    smithrx_content = """SMITHRX_CLAIMS_DATA_V2.1
CLAIM_ID|MEMBER_ID|PROVIDER_ID|SERVICE_DATE|AMOUNT|DIAGNOSIS_CODE|DRUG_CODE|CLAIM_STATUS
CLM12345678|M123456789|PRV987654|2024-01-15|156.78|Z51.11|NDC123456|APPROVED
CLM12345679|M123456790|PRV987655|2024-01-16|89.45|M79.89|NDC123457|APPROVED
CLM12345680|M123456791|PRV987656|2024-01-17|234.56|E11.9|NDC123458|PENDING
CLM12345681|M123456792|PRV987657|2024-01-18|445.67|I10|NDC123459|REJECTED
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            # Step 1: Upload and process file
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("smithrx_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                assert upload_response.status_code == status.HTTP_201_CREATED
                file_id = upload_response.json()["file_id"]
                
                # Step 2: Wait for file to be parsed
                await _wait_for_file_status(async_client, file_id, "parsed", max_attempts=10)
                
                # Step 3: Index file for chat
                index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
                assert index_response.status_code == status.HTTP_202_ACCEPTED
                
                # Step 4: Wait for indexing completion
                await _wait_for_file_status(async_client, file_id, "indexed", max_attempts=15)
                
                # Step 5: Test various chat queries
                chat_queries = [
                    {
                        "query": "How many claims are in this file?",
                        "expected_context": ["4", "four", "total"]
                    },
                    {
                        "query": "What is the total claim amount?",
                        "expected_context": ["926.46", "total", "amount"]  # Sum of all amounts
                    },
                    {
                        "query": "How many approved claims are there?",
                        "expected_context": ["2", "two", "approved"]
                    },
                    {
                        "query": "What diagnosis codes appear in the data?",
                        "expected_context": ["Z51.11", "M79.89", "E11.9", "I10"]
                    }
                ]
                
                for query_test in chat_queries:
                    await _test_chat_query(async_client, file_id, query_test)
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_ai_chat_conversation_continuity(async_client: AsyncClient):
    """Test AI chat maintains conversation context"""
    # Use pre-processed file (assuming it exists from previous test)
    file_id = "12345678-1234-1234-1234-123456789012"
    
    # Start new conversation
    first_query = {
        "message": "What types of claims are in this file?",
        "file_id": file_id,
        "include_context": True
    }
    
    conversation_id = None
    
    # First message
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream", 
        json=first_query,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        events.append({"raw": event_data})
        
        # Extract conversation ID
        start_event = next((e for e in events if e.get("type") == "start"), None)
        assert start_event is not None
        conversation_id = start_event["conversation_id"]
    
    # Follow-up message in same conversation
    followup_query = {
        "message": "What about the total amount for those?",
        "file_id": file_id,
        "conversation_id": conversation_id,
        "include_context": True
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=followup_query,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        events.append({"raw": event_data})
        
        # Verify same conversation ID
        start_event = next((e for e in events if e.get("type") == "start"), None)
        assert start_event is not None
        assert start_event["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_ai_chat_streaming_response(async_client: AsyncClient):
    """Test AI chat streaming response format and timing"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    query = {
        "message": "Provide a detailed analysis of the claims data including patterns and insights.",
        "file_id": file_id
    }
    
    import time
    start_time = time.time()
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        events = []
        first_chunk_time = None
        last_chunk_time = None
        
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                current_time = time.time()
                if first_chunk_time is None:
                    first_chunk_time = current_time
                last_chunk_time = current_time
                
                event_data = line[6:]
                if event_data.strip():
                    try:
                        event = json.loads(event_data)
                        events.append(event)
                    except json.JSONDecodeError:
                        events.append({"raw": event_data})
        
        # Verify streaming structure
        assert len(events) >= 3  # start, chunks, end
        
        # Verify start event
        start_event = events[0]
        assert start_event["type"] == "start"
        assert "conversation_id" in start_event
        assert "timestamp" in start_event
        
        # Verify content chunks
        chunk_events = [e for e in events if e.get("type") == "chunk"]
        assert len(chunk_events) > 0
        
        for chunk in chunk_events:
            assert "content" in chunk
            assert "timestamp" in chunk
            assert isinstance(chunk["content"], str)
        
        # Verify end event
        end_event = events[-1]
        assert end_event["type"] == "end"
        assert "total_tokens" in end_event
        assert "response_time_ms" in end_event
        
        # Performance checks
        time_to_first_chunk = first_chunk_time - start_time
        assert time_to_first_chunk < 5.0, f"First chunk took {time_to_first_chunk:.2f}s, should be < 5s"
        
        total_response_time = last_chunk_time - start_time
        assert total_response_time < 30.0, f"Total response took {total_response_time:.2f}s, should be < 30s"


@pytest.mark.asyncio
async def test_ai_chat_context_filtering(async_client: AsyncClient):
    """Test AI chat with context filtering options"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    # Test with context disabled
    query_without_context = {
        "message": "What can you tell me about this data?",
        "file_id": file_id,
        "include_context": False
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query_without_context,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        start_event = next((e for e in events if e.get("type") == "start"), None)
        assert start_event is not None
        assert start_event.get("context_included") is False
    
    # Test with specific context filters
    query_with_filters = {
        "message": "Show me information about member demographics",
        "file_id": file_id,
        "include_context": True,
        "context_filters": {
            "fields": ["MEMBER_ID"],
            "max_records": 10
        }
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query_with_filters,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_ai_chat_error_handling(async_client: AsyncClient):
    """Test AI chat error handling scenarios"""
    # Test with non-existent file
    query_bad_file = {
        "message": "Tell me about this file",
        "file_id": "non-existent-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=query_bad_file)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    # Test with non-indexed file
    query_unindexed = {
        "message": "Analyze this data",
        "file_id": "unindexed-file-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/chat/stream", json=query_unindexed)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    # Test streaming error during processing
    query_error_trigger = {
        "message": "This should trigger an AI processing error",
        "file_id": "error-trigger-1234-1234-1234-123456789012"
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query_error_trigger,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        # Should have error event in stream
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) > 0
        
        error_event = error_events[0]
        assert "error_message" in error_event
        assert "error_code" in error_event


@pytest.mark.asyncio
async def test_ai_chat_performance_monitoring(async_client: AsyncClient):
    """Test AI chat includes performance monitoring"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    query = {
        "message": "Generate a comprehensive summary of all claims with statistics and insights.",
        "file_id": file_id
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        events.append(json.loads(event_data))
                    except json.JSONDecodeError:
                        pass
        
        end_event = next((e for e in events if e.get("type") == "end"), None)
        assert end_event is not None
        
        # Check performance metrics
        assert "total_tokens" in end_event
        assert "response_time_ms" in end_event
        assert "context_tokens" in end_event
        assert "completion_tokens" in end_event
        
        # Performance assertions
        assert end_event["response_time_ms"] < 30000  # Less than 30 seconds
        assert end_event["total_tokens"] > 0
        
        # Check if correlation ID is present for debugging
        start_event = next((e for e in events if e.get("type") == "start"), None)
        assert "correlation_id" in start_event or "request_id" in start_event


async def _wait_for_file_status(async_client: AsyncClient, file_id: str, target_status: str, max_attempts: int = 10):
    """Helper function to wait for file processing status"""
    attempt = 0
    while attempt < max_attempts:
        await asyncio.sleep(2)
        
        status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
        assert status_response.status_code == status.HTTP_200_OK
        status_data = status_response.json()
        
        if status_data["status"] == target_status:
            return status_data
        elif status_data["status"] == "failed":
            pytest.fail(f"File processing failed: {status_data.get('error_message', 'Unknown error')}")
        
        attempt += 1
    
    pytest.fail(f"File did not reach {target_status} status within {max_attempts * 2} seconds")


async def _test_chat_query(async_client: AsyncClient, file_id: str, query_test: dict):
    """Helper function to test a chat query and verify response context"""
    query = {
        "message": query_test["query"],
        "file_id": file_id,
        "include_context": True
    }
    
    async with async_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json=query,
        headers={"Accept": "text/event-stream"}
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        
        events = []
        content_chunks = []
        
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                event_data = line[6:]
                if event_data.strip():
                    try:
                        event = json.loads(event_data)
                        events.append(event)
                        if event.get("type") == "chunk":
                            content_chunks.append(event["content"])
                    except json.JSONDecodeError:
                        pass
        
        # Verify response structure
        assert len(events) >= 3  # start, chunks, end
        
        # Combine all content chunks
        full_response = "".join(content_chunks).lower()
        
        # Check if any expected context appears in response
        context_found = any(
            expected.lower() in full_response 
            for expected in query_test["expected_context"]
        )
        
        assert context_found, f"Expected context {query_test['expected_context']} not found in response: {full_response[:200]}..."