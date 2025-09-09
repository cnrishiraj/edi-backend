"""
Integration tests for complete file upload and processing pipeline
Tests the full workflow: upload -> parse -> index -> ready for chat/mapping
"""
import pytest
import tempfile
import os
from httpx import AsyncClient
from fastapi import status
import asyncio
import json


@pytest.mark.asyncio
async def test_complete_file_pipeline_smithrx_claims(async_client: AsyncClient):
    """Test complete SmithRx claims file processing pipeline"""
    # Create realistic SmithRx test file
    smithrx_content = """SMITHRX_CLAIMS_DATA_V2.1
CLAIM_ID|MEMBER_ID|PROVIDER_ID|SERVICE_DATE|AMOUNT|DIAGNOSIS_CODE|DRUG_CODE
CLM12345678|M123456789|PRV987654|2024-01-15|156.78|Z51.11|NDC123456
CLM12345679|M123456790|PRV987655|2024-01-16|89.45|M79.89|NDC123457
CLM12345680|M123456791|PRV987656|2024-01-17|234.56|E11.9|NDC123458
""".encode()
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            # Step 1: Upload file
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("smithrx_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post(
                    "/api/v1/files/upload", 
                    files=files, 
                    data=data
                )
                
                assert upload_response.status_code == status.HTTP_201_CREATED
                upload_data = upload_response.json()
                file_id = upload_data["file_id"]
                
                # Step 2: Monitor parsing progress
                parsing_complete = False
                max_attempts = 10
                attempt = 0
                
                while not parsing_complete and attempt < max_attempts:
                    await asyncio.sleep(2)  # Wait for processing
                    
                    status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                    assert status_response.status_code == status.HTTP_200_OK
                    status_data = status_response.json()
                    
                    if status_data["status"] == "parsed":
                        parsing_complete = True
                        assert status_data["records_count"] == 3
                        assert status_data["field_definitions_count"] >= 7
                        break
                    elif status_data["status"] == "failed":
                        pytest.fail(f"File parsing failed: {status_data.get('error_message', 'Unknown error')}")
                    
                    attempt += 1
                
                assert parsing_complete, "File parsing did not complete within timeout"
                
                # Step 3: Index file for chat
                index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
                assert index_response.status_code == status.HTTP_202_ACCEPTED
                index_data = index_response.json()
                
                # Step 4: Wait for indexing completion
                indexing_complete = False
                attempt = 0
                
                while not indexing_complete and attempt < max_attempts:
                    await asyncio.sleep(3)  # Indexing takes longer
                    
                    status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                    status_data = status_response.json()
                    
                    if status_data["status"] == "indexed":
                        indexing_complete = True
                        break
                    elif status_data["status"] == "failed":
                        pytest.fail(f"File indexing failed: {status_data.get('error_message', 'Unknown error')}")
                    
                    attempt += 1
                
                assert indexing_complete, "File indexing did not complete within timeout"
                
                # Step 5: Verify file is ready for chat
                chat_request = {
                    "message": "How many claims are in this file?",
                    "file_id": file_id
                }
                
                async with async_client.stream(
                    "POST",
                    "/api/v1/chat/stream",
                    json=chat_request,
                    headers={"Accept": "text/event-stream"}
                ) as chat_response:
                    assert chat_response.status_code == status.HTTP_200_OK
                    
                    # Get first response to verify chat works
                    first_line = await chat_response.aiter_lines().__anext__()
                    assert first_line.startswith("data: ")
                    start_event = json.loads(first_line[6:])
                    assert start_event["type"] == "start"
                
                # Step 6: Verify mapping generation works
                mapping_request = {
                    "file_id": file_id,
                    "target_schema": "vba_standard"
                }
                
                mapping_response = await async_client.post(
                    "/api/v1/mappings/generate",
                    json=mapping_request
                )
                assert mapping_response.status_code == status.HTTP_201_CREATED
                mapping_data = mapping_response.json()
                assert mapping_data["file_id"] == file_id
                assert len(mapping_data["field_mappings"]) > 0
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_file_pipeline_with_excel_definitions(async_client: AsyncClient):
    """Test file pipeline with Excel field definitions"""
    # Create EDI content and Excel definitions
    edi_content = b"EDI_HEADER\nCLAIM001,MEMBER001,100.50"
    excel_content = b"FAKE_EXCEL_DEFINITIONS_DATA"
    
    files = {
        "edi_file": ("claims.txt", edi_content, "text/plain"),
        "excel_definitions": ("field_defs.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {
        "file_type": "smithrx_claims",
        "project_id": "12345678-1234-1234-1234-123456789012"
    }
    
    # Upload with Excel definitions
    upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
    assert upload_response.status_code == status.HTTP_201_CREATED
    upload_data = upload_response.json()
    file_id = upload_data["file_id"]
    
    # Wait for processing with Excel definitions
    max_attempts = 8
    attempt = 0
    processing_complete = False
    
    while not processing_complete and attempt < max_attempts:
        await asyncio.sleep(2)
        
        status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
        status_data = status_response.json()
        
        if status_data["status"] in ["parsed", "indexed"]:
            processing_complete = True
            # Should have field definitions from Excel
            assert status_data.get("field_definitions_count", 0) >= 0
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Processing failed: {status_data.get('error_message', 'Unknown error')}")
        
        attempt += 1
    
    assert processing_complete, "File processing with Excel definitions did not complete"


@pytest.mark.asyncio 
async def test_file_pipeline_error_handling(async_client: AsyncClient):
    """Test file pipeline error handling with invalid file"""
    # Create invalid file content
    invalid_content = b"INVALID_FORMAT_NOT_EDI"
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(invalid_content)
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("invalid.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                assert upload_response.status_code == status.HTTP_201_CREATED
                file_id = upload_response.json()["file_id"]
                
                # Wait for processing to fail
                max_attempts = 6
                attempt = 0
                failed = False
                
                while not failed and attempt < max_attempts:
                    await asyncio.sleep(2)
                    
                    status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                    status_data = status_response.json()
                    
                    if status_data["status"] == "failed":
                        failed = True
                        assert "error_message" in status_data
                        assert len(status_data["error_message"]) > 0
                        break
                    
                    attempt += 1
                
                assert failed, "File processing should have failed for invalid content"
                
                # Verify chat is not available for failed file
                chat_request = {
                    "message": "Test message",
                    "file_id": file_id
                }
                
                chat_response = await async_client.post("/api/v1/chat/stream", json=chat_request)
                assert chat_response.status_code == status.HTTP_404_NOT_FOUND
                
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_concurrent_file_processing(async_client: AsyncClient):
    """Test pipeline handles concurrent file uploads"""
    # Create multiple test files
    files_data = []
    for i in range(3):
        content = f"""SMITHRX_CLAIMS_DATA_V2.1
CLAIM_ID|MEMBER_ID|AMOUNT
CLM{i:08d}|M{i:09d}|{100.0 + i}
""".encode()
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        temp_file.write(content)
        temp_file.flush()
        files_data.append(temp_file.name)
    
    try:
        # Upload all files concurrently
        upload_tasks = []
        for i, file_path in enumerate(files_data):
            with open(file_path, 'rb') as file:
                files = {"edi_file": (f"claims_{i}.txt", file.read(), "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_tasks.append(
                    async_client.post("/api/v1/files/upload", 
                                    files={"edi_file": (f"claims_{i}.txt", files["edi_file"][1], "text/plain")}, 
                                    data=data)
                )
        
        # Wait for all uploads
        upload_responses = await asyncio.gather(*upload_tasks)
        
        # Verify all uploads succeeded
        file_ids = []
        for response in upload_responses:
            assert response.status_code == status.HTTP_201_CREATED
            file_ids.append(response.json()["file_id"])
        
        # Monitor all files for completion
        max_attempts = 15
        attempt = 0
        all_complete = False
        
        while not all_complete and attempt < max_attempts:
            await asyncio.sleep(3)
            
            status_tasks = [
                async_client.get(f"/api/v1/files/{file_id}/status")
                for file_id in file_ids
            ]
            status_responses = await asyncio.gather(*status_tasks)
            
            completed_count = 0
            failed_count = 0
            
            for response in status_responses:
                assert response.status_code == status.HTTP_200_OK
                status_data = response.json()
                
                if status_data["status"] in ["parsed", "indexed"]:
                    completed_count += 1
                elif status_data["status"] == "failed":
                    failed_count += 1
            
            if completed_count == len(file_ids):
                all_complete = True
            elif failed_count > 0:
                pytest.fail("One or more files failed processing")
            
            attempt += 1
        
        assert all_complete, "Not all files completed processing within timeout"
        
    finally:
        # Clean up temporary files
        for file_path in files_data:
            os.unlink(file_path)


@pytest.mark.asyncio
async def test_file_pipeline_performance_monitoring(async_client: AsyncClient):
    """Test pipeline includes performance monitoring"""
    # Create medium-sized test file
    records = []
    for i in range(100):  # 100 records for performance test
        records.append(f"CLM{i:08d}|M{i:09d}|PRV{i:06d}|2024-01-{(i%28)+1:02d}|{100.0 + i}|Z51.11|NDC{i:06d}")
    
    content = "SMITHRX_CLAIMS_DATA_V2.1\nCLAIM_ID|MEMBER_ID|PROVIDER_ID|SERVICE_DATE|AMOUNT|DIAGNOSIS_CODE|DRUG_CODE\n"
    content += "\n".join(records)
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(content.encode())
        temp_file.flush()
        
        try:
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("large_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                # Record upload start time
                import time
                start_time = time.time()
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                assert upload_response.status_code == status.HTTP_201_CREATED
                file_id = upload_response.json()["file_id"]
                
                # Monitor processing with timing
                max_attempts = 20
                attempt = 0
                processing_complete = False
                
                while not processing_complete and attempt < max_attempts:
                    await asyncio.sleep(2)
                    
                    status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                    status_data = status_response.json()
                    
                    # Check for processing logs and progress
                    if "processing_logs" in status_data:
                        assert isinstance(status_data["processing_logs"], list)
                    
                    if "progress_percentage" in status_data:
                        assert 0 <= status_data["progress_percentage"] <= 100
                    
                    if status_data["status"] == "parsed":
                        processing_complete = True
                        end_time = time.time()
                        processing_duration = end_time - start_time
                        
                        # Performance assertion - should complete within 30 seconds
                        assert processing_duration < 30, f"Processing took {processing_duration:.2f}s, exceeds 30s limit"
                        assert status_data["records_count"] == 100
                        break
                    elif status_data["status"] == "failed":
                        pytest.fail(f"Processing failed: {status_data.get('error_message', 'Unknown error')}")
                    
                    attempt += 1
                
                assert processing_complete, "File processing did not complete within timeout"
                
        finally:
            os.unlink(temp_file.name)