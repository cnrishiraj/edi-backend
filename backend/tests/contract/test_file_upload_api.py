"""
Contract tests for POST /files/upload endpoint
These tests MUST FAIL initially - no implementation exists yet
"""
import pytest
from httpx import AsyncClient
from fastapi import status
import tempfile
import os

@pytest.mark.asyncio
async def test_upload_smithrx_file_success(async_client: AsyncClient):
    """Test successful SmithRx file upload"""
    # Create temporary test file
    test_content = b"SMITHRX_CLAIMS_TEST_DATA\nCLAIM_ID,MEMBER_ID,AMOUNT\n001,M123,156.78"
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(test_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("smithrx_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                
                # Should return 201 Created
                assert response.status_code == status.HTTP_201_CREATED
                
                response_data = response.json()
                assert "file_id" in response_data
                assert response_data["filename"] == "smithrx_claims.txt"
                assert response_data["file_type"] == "smithrx_claims"
                assert response_data["status"] in ["uploaded", "parsing"]
                assert "upload_timestamp" in response_data
                assert "file_size" in response_data
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio 
async def test_upload_file_with_excel_definitions(async_client: AsyncClient):
    """Test file upload with Excel field definitions"""
    test_edi_content = b"EDI_TEST_DATA"
    test_excel_content = b"FAKE_EXCEL_CONTENT"
    
    files = {
        "edi_file": ("claims.txt", test_edi_content, "text/plain"),
        "excel_definitions": ("field_defs.xlsx", test_excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {
        "file_type": "smithrx_claims", 
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert response_data["field_definitions_count"] >= 0


@pytest.mark.asyncio
async def test_upload_file_missing_required_fields(async_client: AsyncClient):
    """Test upload with missing required fields"""
    test_content = b"TEST_DATA"
    files = {"edi_file": ("test.txt", test_content, "text/plain")}
    # Missing file_type and project_id
    
    response = await async_client.post("/api/v1/files/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_data = response.json()
    assert "error_code" in response_data
    assert "error_message" in response_data


@pytest.mark.asyncio
async def test_upload_file_too_large(async_client: AsyncClient):
    """Test upload with file exceeding size limit"""
    # Create file larger than 10MB limit (for POC)
    large_content = b"X" * (11 * 1024 * 1024)  # 11MB
    
    files = {"edi_file": ("large_file.txt", large_content, "text/plain")}
    data = {
        "file_type": "smithrx_claims",
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    
    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    response_data = response.json()
    assert "File too large" in response_data["error_message"]


@pytest.mark.asyncio
async def test_upload_invalid_file_type(async_client: AsyncClient):
    """Test upload with invalid file type"""
    test_content = b"TEST_DATA"
    files = {"edi_file": ("test.txt", test_content, "text/plain")}
    data = {
        "file_type": "invalid_type",  # Should only accept smithrx_claims for POC
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    assert "file_type" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_invalid_project_id(async_client: AsyncClient):
    """Test upload with invalid project ID format"""
    test_content = b"TEST_DATA"
    files = {"edi_file": ("test.txt", test_content, "text/plain")}
    data = {
        "file_type": "smithrx_claims",
        "project_id": "invalid-uuid"  # Invalid UUID format
    }
    
    response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    assert "project_id" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_upload_no_file_provided(async_client: AsyncClient):
    """Test upload request with no file"""
    data = {
        "file_type": "smithrx_claims",
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    response = await async_client.post("/api/v1/files/upload", data=data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    response_data = response.json()
    assert "edi_file" in response_data["error_message"].lower()