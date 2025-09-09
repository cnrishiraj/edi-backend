"""
Integration tests for field mapping generation and management
Tests end-to-end mapping workflow with real file processing and fuzzy matching
"""
import pytest
import tempfile
import os
from httpx import AsyncClient
from fastapi import status
import asyncio
import json


@pytest.mark.asyncio
async def test_mapping_generation_complete_workflow(async_client: AsyncClient):
    """Test complete mapping generation workflow"""
    # Create SmithRx file with varied field names for mapping challenge
    smithrx_content = """SMITHRX_CLAIMS_DATA_V2.1
CLAIMID|MEMBERID|PROVIDERID|SERVICEDATE|CLAIMAMOUNT|DIAGCODE|DRUGCODE|STATUS|COPAYAMT
CLM12345678|M123456789|PRV987654|20240115|15678|Z5111|NDC123456|A|1000
CLM12345679|M123456790|PRV987655|20240116|8945|M7989|NDC123457|A|500
CLM12345680|M123456791|PRV987656|20240117|23456|E119|NDC123458|P|750
CLM12345681|M123456792|PRV987657|20240118|44567|I10|NDC123459|R|0
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            # Step 1: Upload and process file
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("mapping_test_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                assert upload_response.status_code == status.HTTP_201_CREATED
                file_id = upload_response.json()["file_id"]
                
                # Step 2: Wait for file parsing
                await _wait_for_file_status(async_client, file_id, "parsed", max_attempts=10)
                
                # Step 3: Generate mappings
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard",
                    "confidence_threshold": 0.7
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_201_CREATED
                
                mapping_data = mapping_response.json()
                mapping_id = mapping_data["mapping_id"]
                assert mapping_data["file_id"] == file_id
                assert mapping_data["target_schema"] == "vba_standard"
                
                # Step 4: Verify field mappings
                field_mappings = mapping_data["field_mappings"]
                assert len(field_mappings) > 0
                
                # Check specific expected mappings
                mapping_dict = {fm["source_field"]: fm for fm in field_mappings}
                
                # Verify key field mappings exist
                expected_mappings = {
                    "CLAIMID": "claim_number",
                    "MEMBERID": "member_id", 
                    "CLAIMAMOUNT": "claim_amount",
                    "SERVICEDATE": "service_date",
                    "DIAGCODE": "diagnosis_code"
                }
                
                for source_field, expected_target in expected_mappings.items():
                    assert source_field in mapping_dict
                    mapping = mapping_dict[source_field]
                    assert mapping["target_field"] == expected_target
                    assert mapping["confidence_score"] >= 0.7
                    assert "data_type" in mapping
                    assert "sample_values" in mapping
                
                # Step 5: Retrieve mapping details
                get_response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
                assert get_response.status_code == status.HTTP_200_OK
                
                get_data = get_response.json()
                assert get_data["mapping_id"] == mapping_id
                assert get_data["overall_confidence"] >= 0.7
                assert "validation_results" in get_data
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_mapping_with_excel_definitions(async_client: AsyncClient):
    """Test mapping generation using Excel field definitions"""
    # Create EDI content
    edi_content = """CUSTOM_CLAIMS_FORMAT
CLMNO|MBRID|AMT|DT|STS
C001|M001|100.50|20240101|A
C002|M002|75.25|20240102|P
""".encode()
    
    # Simulate Excel definitions content
    excel_content = b"EXCEL_FIELD_DEFINITIONS_BINARY_DATA"
    
    files = {
        "edi_file": ("custom_claims.txt", edi_content, "text/plain"),
        "excel_definitions": ("field_mappings.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {
        "file_type": "smithrx_claims",
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    # Upload with Excel definitions
    upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    assert upload_response.status_code == status.HTTP_201_CREATED
    file_id = upload_response.json()["file_id"]
    
    # Wait for processing
    await _wait_for_file_status(async_client, file_id, "parsed", max_attempts=10)
    
    # Generate mapping using Excel definitions
    mapping_request = {
        "file_id": file_id,
        "target_schema": "custom",
        "use_excel_definitions": True,
        "confidence_threshold": 0.6
    }
    
    mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
    assert mapping_response.status_code == status.HTTP_201_CREATED
    
    mapping_data = mapping_response.json()
    assert mapping_data["used_excel_definitions"] is True
    assert mapping_data["target_schema"] == "custom"
    assert "custom_field_count" in mapping_data


@pytest.mark.asyncio
async def test_mapping_confidence_scoring(async_client: AsyncClient):
    """Test mapping confidence scoring with ambiguous fields"""
    # Create file with ambiguous field names
    ambiguous_content = """CLAIMS_DATA
F1|F2|F3|F4|F5|F6
VAL001|VAL002|12345|20240101|100.50|APPROVED
VAL003|VAL004|12346|20240102|75.25|PENDING
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(ambiguous_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("ambiguous_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                file_id = upload_response.json()["file_id"]
                
                await _wait_for_file_status(async_client, file_id, "parsed")
                
                # Test with high confidence threshold
                high_threshold_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard",
                    "confidence_threshold": 0.9
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=high_threshold_request)
                assert mapping_response.status_code == status.HTTP_201_CREATED
                
                mapping_data = mapping_response.json()
                
                # Should have unmapped fields due to low confidence
                assert "unmapped_fields" in mapping_data
                assert len(mapping_data["unmapped_fields"]) > 0
                assert mapping_data["manual_review_required"] is True
                
                # Check unmapped field structure
                unmapped_field = mapping_data["unmapped_fields"][0]
                assert "field_name" in unmapped_field
                assert "reason" in unmapped_field
                assert "suggested_mappings" in unmapped_field
                assert isinstance(unmapped_field["suggested_mappings"], list)
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_mapping_with_sample_validation(async_client: AsyncClient):
    """Test mapping generation with sample data validation"""
    # Create file with validation-testable data
    validation_content = """SMITHRX_CLAIMS_DATA
CLAIM_ID|MEMBER_ID|AMOUNT|SERVICE_DATE|STATUS
CLM00000001|M000000001|100.50|2024-01-01|APPROVED
CLM00000002|M000000002|INVALID_AMOUNT|2024-01-02|APPROVED  
CLM00000003|M000000003|75.25|INVALID_DATE|PENDING
CLM00000004||50.00|2024-01-04|APPROVED  
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(validation_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("validation_test.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                file_id = upload_response.json()["file_id"]
                
                await _wait_for_file_status(async_client, file_id, "parsed")
                
                # Generate mapping with sample validation
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard",
                    "validate_with_samples": True,
                    "sample_size": 4
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_201_CREATED
                
                mapping_data = mapping_response.json()
                
                # Check validation results
                assert "validation_results" in mapping_data
                validation = mapping_data["validation_results"]
                assert "samples_processed" in validation
                assert validation["samples_processed"] == 4
                assert "validation_errors" in validation
                assert "validation_warnings" in validation
                
                # Should detect data quality issues
                assert len(validation["validation_errors"]) > 0 or len(validation["validation_warnings"]) > 0
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_mapping_async_processing(async_client: AsyncClient):
    """Test async mapping generation for large files"""
    # Create larger file to trigger async processing
    records = []
    for i in range(500):  # 500 records to trigger async mode
        records.append(f"CLM{i:08d}|M{i:09d}|PRV{i:06d}|2024-01-{(i%28)+1:02d}|{100.0 + i}|Z51.11|NDC{i:06d}|A")
    
    large_content = "SMITHRX_CLAIMS_DATA_V2.1\n"
    large_content += "CLAIM_ID|MEMBER_ID|PROVIDER_ID|SERVICE_DATE|AMOUNT|DIAGNOSIS_CODE|DRUG_CODE|STATUS\n"
    large_content += "\n".join(records)
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(large_content.encode())
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("large_file.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                file_id = upload_response.json()["file_id"]
                
                await _wait_for_file_status(async_client, file_id, "parsed", max_attempts=20)
                
                # Request async processing
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard",
                    "async_processing": True
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_202_ACCEPTED
                
                mapping_data = mapping_response.json()
                assert mapping_data["status"] == "processing"
                assert "job_id" in mapping_data
                assert "progress_url" in mapping_data
                assert "estimated_completion" in mapping_data
                
                mapping_id = mapping_data["mapping_id"]
                
                # Wait for async processing completion
                max_attempts = 30
                attempt = 0
                processing_complete = False
                
                while not processing_complete and attempt < max_attempts:
                    await asyncio.sleep(3)
                    
                    get_response = await async_client.get(f"/api/v1/mappings/{mapping_id}")
                    assert get_response.status_code == status.HTTP_200_OK
                    
                    get_data = get_response.json()
                    
                    if get_data["status"] == "completed":
                        processing_complete = True
                        assert len(get_data["field_mappings"]) > 0
                        assert get_data["overall_confidence"] > 0
                        break
                    elif get_data["status"] == "failed":
                        pytest.fail(f"Async mapping generation failed: {get_data.get('error_message', 'Unknown error')}")
                    else:
                        # Check progress
                        if "progress_percentage" in get_data:
                            assert 0 <= get_data["progress_percentage"] <= 100
                    
                    attempt += 1
                
                assert processing_complete, "Async mapping generation did not complete within timeout"
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_mapping_custom_rules(async_client: AsyncClient):
    """Test mapping generation with custom mapping rules"""
    smithrx_content = """CLAIMS_DATA
CLAIM_NO|MEMBER_NO|AMOUNT_USD|DATE|STATUS_CODE
CLM001|MEM001|100.50|2024-01-01|APP
CLM002|MEM002|75.25|2024-01-02|PEN
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("custom_rules_test.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                file_id = upload_response.json()["file_id"]
                
                await _wait_for_file_status(async_client, file_id, "parsed")
                
                # Generate mapping with custom rules
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard",
                    "custom_mapping_rules": {
                        "claim_number": {
                            "required": True,
                            "pattern": "^CLM\\d{3}$",
                            "source_hint": "CLAIM_NO"
                        },
                        "member_id": {
                            "required": True,
                            "max_length": 12,
                            "source_hint": "MEMBER_NO"
                        },
                        "amount": {
                            "required": True,
                            "type": "decimal",
                            "min_value": 0,
                            "source_hint": "AMOUNT_USD"
                        }
                    }
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_201_CREATED
                
                mapping_data = mapping_response.json()
                assert "custom_rules_applied" in mapping_data
                assert mapping_data["custom_rules_applied"] >= 3
                
                # Verify custom rule mappings
                field_mappings = mapping_data["field_mappings"]
                mapping_dict = {fm["target_field"]: fm for fm in field_mappings}
                
                # Check custom rule applications
                claim_mapping = mapping_dict.get("claim_number")
                assert claim_mapping is not None
                assert claim_mapping["source_field"] == "CLAIM_NO"
                assert "validation_rules" in claim_mapping
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_mapping_performance_monitoring(async_client: AsyncClient):
    """Test mapping generation includes performance monitoring"""
    smithrx_content = """SMITHRX_CLAIMS_DATA
CLAIM_ID|MEMBER_ID|AMOUNT|SERVICE_DATE|STATUS
CLM001|M001|100.50|2024-01-01|A
CLM002|M002|75.25|2024-01-02|P
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("perf_test.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                file_id = upload_response.json()["file_id"]
                
                await _wait_for_file_status(async_client, file_id, "parsed")
                
                import time
                start_time = time.time()
                
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard"
                }
                
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_201_CREATED
                
                end_time = time.time()
                generation_time = end_time - start_time
                
                mapping_data = mapping_response.json()
                mapping_id = mapping_data["mapping_id"]
                
                # Performance assertion - should complete within 60 seconds
                assert generation_time < 60, f"Mapping generation took {generation_time:.2f}s, exceeds 60s limit"
                
                # Check performance metrics in response
                assert "created_at" in mapping_data
                if "processing_time_ms" in mapping_data:
                    assert mapping_data["processing_time_ms"] > 0
                
                # Get detailed mapping with statistics
                get_response = await async_client.get(
                    f"/api/v1/mappings/{mapping_id}",
                    params={"include_statistics": "true"}
                )
                assert get_response.status_code == status.HTTP_200_OK
                
                get_data = get_response.json()
                assert "field_statistics" in get_data
                
                stats = get_data["field_statistics"]
                assert "total_fields" in stats
                assert "mapped_fields" in stats
                assert "high_confidence_mappings" in stats
                
        finally:
            os.unlink(temp_file.name)


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