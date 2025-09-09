"""
Contract tests for GET /mappings/{mapping_id} endpoint (Retrieve field mappings)
These tests MUST FAIL initially - no implementation exists yet
"""
import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_get_mapping_success(async_client: AsyncClient):
    """Test successful retrieval of field mapping"""
    mapping_id = "mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["mapping_id"] == mapping_id
    assert "file_id" in response_data
    assert "target_schema" in response_data
    assert "field_mappings" in response_data
    assert isinstance(response_data["field_mappings"], list)
    assert "overall_confidence" in response_data
    assert 0.0 <= response_data["overall_confidence"] <= 1.0
    assert "status" in response_data
    assert response_data["status"] in ["draft", "approved", "rejected"]
    assert "created_at" in response_data
    assert "updated_at" in response_data


@pytest.mark.asyncio
async def test_get_mapping_with_detailed_field_info(async_client: AsyncClient):
    """Test mapping retrieval includes detailed field information"""
    mapping_id = "detailed-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    field_mappings = response_data["field_mappings"]
    assert len(field_mappings) > 0
    
    # Check first field mapping structure
    field_mapping = field_mappings[0]
    assert "source_field" in field_mapping
    assert "target_field" in field_mapping
    assert "confidence_score" in field_mapping
    assert "data_type" in field_mapping
    assert "transformation_rules" in field_mapping
    assert "sample_values" in field_mapping
    assert "validation_status" in field_mapping
    
    # Confidence should be between 0 and 1
    assert 0.0 <= field_mapping["confidence_score"] <= 1.0


@pytest.mark.asyncio
async def test_get_mapping_with_validation_results(async_client: AsyncClient):
    """Test mapping retrieval includes validation results"""
    mapping_id = "validated-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "validation_results" in response_data
    
    validation = response_data["validation_results"]
    assert "total_records_validated" in validation
    assert "validation_errors" in validation
    assert "validation_warnings" in validation
    assert "data_quality_score" in validation
    assert 0.0 <= validation["data_quality_score"] <= 1.0


@pytest.mark.asyncio
async def test_get_mapping_not_found(async_client: AsyncClient):
    """Test retrieval of non-existent mapping"""
    mapping_id = "non-existent-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "error_message" in response_data
    assert "mapping not found" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_get_mapping_invalid_uuid(async_client: AsyncClient):
    """Test retrieval with invalid mapping ID format"""
    invalid_mapping_id = "invalid-uuid-format"
    
    response = await async_client.get(f"/api/v1/mappings/{invalid_mapping_id}")
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    response_data = response.json()
    assert "error_code" in response_data
    assert "error_message" in response_data
    assert "uuid" in response_data["error_message"].lower()


@pytest.mark.asyncio
async def test_get_mapping_with_unmapped_fields(async_client: AsyncClient):
    """Test mapping retrieval includes unmapped fields"""
    mapping_id = "partial-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "unmapped_fields" in response_data
    assert isinstance(response_data["unmapped_fields"], list)
    
    if len(response_data["unmapped_fields"]) > 0:
        unmapped_field = response_data["unmapped_fields"][0]
        assert "field_name" in unmapped_field
        assert "data_type" in unmapped_field
        assert "sample_values" in unmapped_field
        assert "reason" in unmapped_field
        assert "suggested_mappings" in unmapped_field


@pytest.mark.asyncio
async def test_get_mapping_with_custom_schema(async_client: AsyncClient):
    """Test mapping retrieval for custom target schema"""
    mapping_id = "custom-schema-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["target_schema"] == "custom"
    assert "schema_definition" in response_data
    assert "custom_fields" in response_data
    assert isinstance(response_data["custom_fields"], list)


@pytest.mark.asyncio
async def test_get_mapping_processing_status(async_client: AsyncClient):
    """Test mapping retrieval shows processing status"""
    mapping_id = "processing-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "generating"
    assert "progress_percentage" in response_data
    assert 0 <= response_data["progress_percentage"] <= 100
    assert "estimated_completion" in response_data


@pytest.mark.asyncio
async def test_get_mapping_with_excel_definitions(async_client: AsyncClient):
    """Test mapping retrieval includes Excel definitions metadata"""
    mapping_id = "excel-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "excel_definitions_used" in response_data
    assert response_data["excel_definitions_used"] is True
    assert "excel_field_count" in response_data
    assert "excel_filename" in response_data


@pytest.mark.asyncio
async def test_get_mapping_with_transformation_preview(async_client: AsyncClient):
    """Test mapping retrieval includes transformation preview"""
    mapping_id = "mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(
        f"/api/v1/mappings/{mapping_id}",
        params={"include_preview": "true"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "transformation_preview" in response_data
    
    preview = response_data["transformation_preview"]
    assert "sample_records" in preview
    assert "before" in preview["sample_records"][0]
    assert "after" in preview["sample_records"][0]
    assert "transformation_applied" in preview["sample_records"][0]


@pytest.mark.asyncio
async def test_get_mapping_with_statistics(async_client: AsyncClient):
    """Test mapping retrieval includes field statistics"""
    mapping_id = "mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(
        f"/api/v1/mappings/{mapping_id}",
        params={"include_statistics": "true"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "field_statistics" in response_data
    
    stats = response_data["field_statistics"]
    assert "total_fields" in stats
    assert "mapped_fields" in stats
    assert "unmapped_fields" in stats
    assert "high_confidence_mappings" in stats
    assert "manual_review_required" in stats
    assert stats["total_fields"] == stats["mapped_fields"] + stats["unmapped_fields"]


@pytest.mark.asyncio
async def test_get_mapping_with_history(async_client: AsyncClient):
    """Test mapping retrieval includes change history"""
    mapping_id = "versioned-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(
        f"/api/v1/mappings/{mapping_id}",
        params={"include_history": "true"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "version" in response_data
    assert "change_history" in response_data
    
    if len(response_data["change_history"]) > 0:
        history_entry = response_data["change_history"][0]
        assert "version" in history_entry
        assert "changed_by" in history_entry
        assert "change_type" in history_entry
        assert "timestamp" in history_entry
        assert "changes" in history_entry


@pytest.mark.asyncio
async def test_get_mapping_archived_status(async_client: AsyncClient):
    """Test retrieval of archived mapping"""
    mapping_id = "archived-mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert response_data["status"] == "archived"
    assert "archived_at" in response_data
    assert "archive_reason" in response_data


@pytest.mark.asyncio
async def test_get_mapping_includes_correlation_id(async_client: AsyncClient):
    """Test that mapping retrieval includes correlation ID"""
    mapping_id = "mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
    
    # Should have correlation ID in response for debugging
    if response.status_code in [200, 404]:
        response_data = response.json()
        assert "correlation_id" in response_data or "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_get_mapping_with_export_formats(async_client: AsyncClient):
    """Test mapping retrieval includes supported export formats"""
    mapping_id = "mapping-1234-1234-1234-123456789012"
    
    response = await async_client.get(
        f"/api/v1/mappings/{mapping_id}",
        params={"include_export_info": "true"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    
    response_data = response.json()
    assert "supported_export_formats" in response_data
    assert "json" in response_data["supported_export_formats"]
    assert "csv" in response_data["supported_export_formats"]
    assert "excel" in response_data["supported_export_formats"]