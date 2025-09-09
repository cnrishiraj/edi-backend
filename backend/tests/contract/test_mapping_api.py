"""
Contract tests for POST /mappings/generate endpoint (Field mapping generation)
These tests MUST FAIL initially - no implementation exists yet
"""
import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_generate_mapping_success(async_client: AsyncClient):
    """Test successful field mapping generation"""
    file_id = "12345678-1234-1234-1234-123456789012"
    request_data = {
        "file_id": file_id,
        "target_schema": "vba_standard",
        "confidence_threshold": 0.8
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert response_data["file_id"] == file_id
    assert "mapping_id" in response_data
    assert response_data["target_schema"] == "vba_standard"
    assert response_data["status"] in ["generating", "completed"]
    assert "field_mappings" in response_data
    assert "overall_confidence" in response_data
    assert 0.0 <= response_data["overall_confidence"] <= 1.0
    assert "created_at" in response_data


@pytest.mark.asyncio
async def test_generate_mapping_with_excel_definitions(async_client: AsyncClient):
    """Test mapping generation using Excel field definitions"""
    file_id = "with-excel-defs-1234-1234-1234-123456789012"
    request_data = {
        "file_id": file_id,
        "target_schema": "custom",
        "use_excel_definitions": True
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert response_data["used_excel_definitions"] is True
    assert "custom_field_count" in response_data
    assert response_data["custom_field_count"] > 0


@pytest.mark.asyncio
async def test_generate_mapping_file_not_found(async_client: AsyncClient):
    """Test mapping generation for non-existent file"""
    request_data = {
        "file_id": "non-existent-1234-1234-1234-123456789012",
        "target_schema": "vba_standard"
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "file not found" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_file_not_parsed(async_client: AsyncClient):
    """Test mapping generation for unparsed file"""
    request_data = {
        "file_id": "unparsed-file-1234-1234-1234-123456789012",
        "target_schema": "vba_standard"
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    response_data = response.json()
    assert "not parsed" in response_data["error_message"].lower() or \
           "parsing required" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_invalid_target_schema(async_client: AsyncClient):
    """Test mapping generation with invalid target schema"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012",
        "target_schema": "invalid_schema"
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "target_schema" in response_data["error_message"].lower()
    assert "supported schemas" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_missing_required_fields(async_client: AsyncClient):
    """Test mapping generation with missing required fields"""
    request_data = {
        # Missing file_id and target_schema
        "confidence_threshold": 0.8
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    response_data = response.json()
    assert "file_id" in response_data["error_message"].lower() or \
           "target_schema" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_invalid_confidence_threshold(async_client: AsyncClient):
    """Test mapping generation with invalid confidence threshold"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "confidence_threshold": 1.5  # Invalid - should be 0.0-1.0
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "confidence_threshold" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_with_existing_mapping(async_client: AsyncClient):
    """Test generating new mapping when one already exists"""
    request_data = {
        "file_id": "has-mapping-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "force_regenerate": False
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_409_CONFLICT
    
    response_data = response.json()
    assert "mapping already exists" in response_data["error_message"].lower()
    assert "existing_mapping_id" in response_data


@pytest.mark.asyncio
async def test_generate_mapping_force_regenerate(async_client: AsyncClient):
    """Test force regenerating existing mapping"""
    request_data = {
        "file_id": "has-mapping-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "force_regenerate": True
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert response_data["regenerated"] is True
    assert "previous_mapping_id" in response_data


@pytest.mark.asyncio
async def test_generate_mapping_with_custom_rules(async_client: AsyncClient):
    """Test mapping generation with custom mapping rules"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "custom_mapping_rules": {
            "claim_number": {"required": True, "pattern": "^CLM\\d{8}$"},
            "member_id": {"required": True, "max_length": 12},
            "amount": {"required": True, "type": "decimal", "min_value": 0}
        }
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert "custom_rules_applied" in response_data
    assert response_data["custom_rules_applied"] == 3


@pytest.mark.asyncio
async def test_generate_mapping_async_processing(async_client: AsyncClient):
    """Test async mapping generation for large files"""
    request_data = {
        "file_id": "large-file-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "async_processing": True
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_202_ACCEPTED
    
    response_data = response.json()
    assert response_data["status"] == "processing"
    assert "job_id" in response_data
    assert "progress_url" in response_data
    assert "estimated_completion" in response_data


@pytest.mark.asyncio
async def test_generate_mapping_low_confidence_fields(async_client: AsyncClient):
    """Test mapping generation with fields below confidence threshold"""
    request_data = {
        "file_id": "ambiguous-fields-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "confidence_threshold": 0.9  # High threshold
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert "unmapped_fields" in response_data
    assert len(response_data["unmapped_fields"]) > 0
    assert "manual_review_required" in response_data
    assert response_data["manual_review_required"] is True
    
    # Check low confidence fields are flagged
    for field in response_data["unmapped_fields"]:
        assert "field_name" in field
        assert "reason" in field
        assert "suggested_mappings" in field


@pytest.mark.asyncio
async def test_generate_mapping_with_sample_validation(async_client: AsyncClient):
    """Test mapping generation with sample data validation"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012",
        "target_schema": "vba_standard",
        "validate_with_samples": True,
        "sample_size": 100
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_201_CREATED
    
    response_data = response.json()
    assert "validation_results" in response_data
    assert "samples_processed" in response_data["validation_results"]
    assert "validation_errors" in response_data["validation_results"]
    assert response_data["validation_results"]["samples_processed"] == 100


@pytest.mark.asyncio
async def test_generate_mapping_invalid_file_id_format(async_client: AsyncClient):
    """Test mapping generation with invalid file ID format"""
    request_data = {
        "file_id": "invalid-uuid-format",
        "target_schema": "vba_standard"
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "file_id" in response_data["error_message"].lower()
    assert "uuid" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_generate_mapping_includes_correlation_id(async_client: AsyncClient):
    """Test that mapping generation includes correlation ID"""
    request_data = {
        "file_id": "12345678-1234-1234-1234-123456789012",
        "target_schema": "vba_standard"
    }
    
    response = await async_client.post("/api/v1/mappings/generate", json=request_data)
    
    # Should have correlation ID for debugging
    if response.status_code in [201, 202]:
        response_data = response.json()
        assert "correlation_id" in response_data or "X-Correlation-ID" in response.headers