"""
Contract tests for GET /files/{file_id}/status endpoint
These tests MUST FAIL initially - no implementation exists yet
"""
import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_get_file_status_success(async_client: AsyncClient):
    """Test getting file status for existing file"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["file_id"] == file_id
    assert "status" in response_data
    assert response_data["status"] in ["uploaded", "parsing", "parsed", "indexed", "failed"]
    assert "last_updated" in response_data
    
    # Optional fields that may be present
    if "progress_percentage" in response_data:
        assert 0 <= response_data["progress_percentage"] <= 100
    if "records_count" in response_data:
        assert response_data["records_count"] >= 0
    if "field_definitions_count" in response_data:
        assert response_data["field_definitions_count"] >= 0


@pytest.mark.asyncio
async def test_get_file_status_with_processing_logs(async_client: AsyncClient):
    """Test getting file status includes processing logs"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "processing_logs" in response_data
    
    if response_data["processing_logs"]:
        log_entry = response_data["processing_logs"][0]
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert log_entry["level"] in ["INFO", "WARNING", "ERROR"]
        assert "message" in log_entry


@pytest.mark.asyncio
async def test_get_file_status_parsing_in_progress(async_client: AsyncClient):
    """Test getting status for file currently being parsed"""
    file_id = "parsing-file-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "parsing"
    assert "progress_percentage" in response_data
    assert 0 <= response_data["progress_percentage"] < 100


@pytest.mark.asyncio  
async def test_get_file_status_completed_with_results(async_client: AsyncClient):
    """Test getting status for successfully parsed file"""
    file_id = "completed-file-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "parsed"
    assert response_data["progress_percentage"] == 100
    assert "records_count" in response_data
    assert response_data["records_count"] > 0
    assert "field_definitions_count" in response_data


@pytest.mark.asyncio
async def test_get_file_status_failed_with_error(async_client: AsyncClient):
    """Test getting status for failed file processing"""
    file_id = "failed-file-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "failed"
    assert "error_message" in response_data
    assert response_data["error_message"] is not None
    assert len(response_data["error_message"]) > 0


@pytest.mark.asyncio
async def test_get_file_status_not_found(async_client: AsyncClient):
    """Test getting status for non-existent file"""
    file_id = "non-existent-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "error_message" in response_data
    assert "not found" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_get_file_status_invalid_uuid(async_client: AsyncClient):
    """Test getting status with invalid UUID format"""
    invalid_file_id = "invalid-uuid-format"
    
    response = await async_client.get(f"/api/v1/files/{invalid_file_id}/status")
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "error_message" in response_data
    assert "uuid" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_get_file_status_archived_file(async_client: AsyncClient):
    """Test getting status for archived file"""
    file_id = "archived-file-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "archived"
    assert "last_updated" in response_data


@pytest.mark.asyncio
async def test_get_file_status_includes_correlation_id(async_client: AsyncClient):
    """Test that response includes correlation ID for debugging"""
    file_id = "12345678-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/files/{file_id}/status")
    
    # Should have correlation ID in response for debugging
    if response.status_code in [200, 404]:
        response_data = response.json()
        # Correlation ID might be in headers or response body
        assert "correlation_id" in response_data or "X-Correlation-ID" in response.headers