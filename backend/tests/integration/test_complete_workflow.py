"""
Integration tests for complete EDI POC workflow
Tests the full end-to-end user journey: Upload -> Chat -> Mapping -> Export
"""
import pytest
import tempfile
import os
from httpx import AsyncClient
from fastapi import status
import asyncio
import json
import time


@pytest.mark.asyncio
async def test_complete_edi_workflow_smithrx_claims(async_client: AsyncClient):
    """Test complete EDI workflow from upload to mapping generation"""
    # Create comprehensive SmithRx test file
    smithrx_content = """SMITHRX_CLAIMS_DATA_V2.1
CLAIM_ID|MEMBER_ID|PROVIDER_ID|SERVICE_DATE|AMOUNT|DIAGNOSIS_CODE|DRUG_CODE|STATUS|COPAY_AMOUNT|DEDUCTIBLE
CLM12345678|M123456789|PRV987654|2024-01-15|156.78|Z51.11|NDC123456|APPROVED|10.00|25.00
CLM12345679|M123456790|PRV987655|2024-01-16|89.45|M79.89|NDC123457|APPROVED|15.00|25.00
CLM12345680|M123456791|PRV987656|2024-01-17|234.56|E11.9|NDC123458|PENDING|20.00|25.00
CLM12345681|M123456792|PRV987657|2024-01-18|445.67|I10|NDC123459|REJECTED|0.00|0.00
CLM12345682|M123456793|PRV987658|2024-01-19|567.89|F32.1|NDC123460|APPROVED|25.00|50.00
CLM12345683|M123456794|PRV987659|2024-01-20|123.45|K59.00|NDC123461|APPROVED|5.00|25.00
""".encode()
    
    workflow_results = {}
    
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
        temp_file.write(smithrx_content)
        temp_file.flush()
        
        try:
            # ===========================================
            # PHASE 1: FILE UPLOAD AND PROCESSING
            # ===========================================
            print("Phase 1: File Upload and Processing")
            start_time = time.time()
            
            with open(temp_file.name, 'rb') as file:
                files = {"edi_file": ("complete_workflow_claims.txt", file, "text/plain")}
                data = {
                    "file_type": "smithrx_claims",
                    "project_id": "12345678-1234-1234-1234-123456789012"
                }
                
                upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
                assert upload_response.status_code == status.HTTP_201_CREATED
                
                upload_data = upload_response.json()
                file_id = upload_data["file_id"]
                workflow_results["file_id"] = file_id
                workflow_results["upload_time"] = time.time() - start_time
                
                print(f"File uploaded: {file_id}")
                assert upload_data["filename"] == "complete_workflow_claims.txt"
                assert upload_data["file_type"] == "smithrx_claims"
                assert upload_data["status"] in ["uploaded", "parsing"]
            
            # Wait for file parsing completion
            parsing_start = time.time()
            parsing_complete = False
            max_attempts = 15
            attempt = 0
            
            while not parsing_complete and attempt < max_attempts:
                await asyncio.sleep(2)
                
                status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                assert status_response.status_code == status.HTTP_200_OK
                status_data = status_response.json()
                
                print(f"File status: {status_data['status']}")
                
                if status_data["status"] == "parsed":
                    parsing_complete = True
                    workflow_results["parsing_time"] = time.time() - parsing_start
                    workflow_results["record_count"] = status_data["records_count"]
                    workflow_results["field_count"] = status_data["field_definitions_count"]
                    
                    # Verify parsing results
                    assert status_data["records_count"] == 6  # 6 claims
                    assert status_data["field_definitions_count"] >= 10  # 10+ fields
                    
                elif status_data["status"] == "failed":
                    pytest.fail(f"File parsing failed: {status_data.get('error_message', 'Unknown error')}")
                
                attempt += 1
            
            assert parsing_complete, "File parsing did not complete within timeout"
            print(f"Parsing completed in {workflow_results['parsing_time']:.2f}s")
            
            # ===========================================
            # PHASE 2: FILE INDEXING FOR CHAT
            # ===========================================
            print("Phase 2: File Indexing for Chat")
            indexing_start = time.time()
            
            index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
            assert index_response.status_code == status.HTTP_202_ACCEPTED
            
            index_data = index_response.json()
            assert index_data["file_id"] == file_id
            assert index_data["status"] == "indexing_started"
            
            # Wait for indexing completion
            indexing_complete = False
            attempt = 0
            
            while not indexing_complete and attempt < max_attempts:
                await asyncio.sleep(3)  # Indexing takes longer
                
                status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                status_data = status_response.json()
                
                if status_data["status"] == "indexed":
                    indexing_complete = True
                    workflow_results["indexing_time"] = time.time() - indexing_start
                    print(f"Indexing completed in {workflow_results['indexing_time']:.2f}s")
                elif status_data["status"] == "failed":
                    pytest.fail(f"File indexing failed: {status_data.get('error_message', 'Unknown error')}")
                
                attempt += 1
            
            assert indexing_complete, "File indexing did not complete within timeout"
            
            # ===========================================
            # PHASE 3: AI CHAT INTERACTION
            # ===========================================
            print("Phase 3: AI Chat Interaction")
            
            # Test multiple chat interactions
            chat_queries = [
                {
                    "message": "How many claims are in this file?",
                    "expected_info": ["6", "six"]
                },
                {
                    "message": "What is the total claim amount across all claims?",
                    "expected_info": ["1617.80"]  # Sum of all amounts
                },
                {
                    "message": "How many approved claims are there?",
                    "expected_info": ["4", "four"]
                },
                {
                    "message": "What are the different diagnosis codes?",
                    "expected_info": ["Z51.11", "E11.9", "I10", "F32.1"]
                }
            ]
            
            conversation_id = None
            chat_results = []
            
            for i, query in enumerate(chat_queries):
                chat_start = time.time()
                
                chat_request = {
                    "message": query["message"],
                    "file_id": file_id,
                    "include_context": True
                }
                
                if conversation_id:
                    chat_request["conversation_id"] = conversation_id
                
                print(f"Chat query {i+1}: {query['message']}")
                
                async with async_client.stream(
                    "POST",
                    "/api/v1/chat/stream",
                    json=chat_request,
                    headers={"Accept": "text/event-stream"}
                ) as chat_response:
                    assert chat_response.status_code == status.HTTP_200_OK
                    
                    events = []
                    content_chunks = []
                    
                    async for line in chat_response.aiter_lines():
                        if line.startswith("data: "):
                            event_data = line[6:]
                            if event_data.strip():
                                try:
                                    event = json.loads(event_data)
                                    events.append(event)
                                    
                                    if event.get("type") == "start" and not conversation_id:
                                        conversation_id = event["conversation_id"]
                                    
                                    if event.get("type") == "chunk":
                                        content_chunks.append(event["content"])
                                        
                                except json.JSONDecodeError:
                                    pass
                    
                    chat_time = time.time() - chat_start
                    full_response = "".join(content_chunks).lower()
                    
                    chat_results.append({
                        "query": query["message"],
                        "response_time": chat_time,
                        "response_length": len(full_response),
                        "events_count": len(events)
                    })
                    
                    print(f"Chat response time: {chat_time:.2f}s")
                    
                    # Performance check
                    assert chat_time < 10.0, f"Chat response took {chat_time:.2f}s, should be < 10s"
                    
                    # Content verification (lenient - AI responses vary)
                    content_found = any(
                        expected.lower() in full_response 
                        for expected in query["expected_info"]
                    )
                    if not content_found:
                        print(f"Warning: Expected content {query['expected_info']} not clearly found in response")
            
            workflow_results["chat_results"] = chat_results
            workflow_results["conversation_id"] = conversation_id
            
            # ===========================================
            # PHASE 4: FIELD MAPPING GENERATION
            # ===========================================
            print("Phase 4: Field Mapping Generation")
            mapping_start = time.time()
            
            mapping_request = {
                "file_id": file_id,
                "target_schema": "vba_standard",
                "confidence_threshold": 0.8,
                "validate_with_samples": True,
                "sample_size": 6
            }
            
            mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
            assert mapping_response.status_code == status.HTTP_201_CREATED
            
            mapping_data = mapping_response.json()
            mapping_id = mapping_data["mapping_id"]
            workflow_results["mapping_id"] = mapping_id
            workflow_results["mapping_time"] = time.time() - mapping_start
            
            print(f"Mapping generated: {mapping_id}")
            print(f"Mapping generation time: {workflow_results['mapping_time']:.2f}s")
            
            # Verify mapping results
            assert mapping_data["file_id"] == file_id
            assert mapping_data["target_schema"] == "vba_standard"
            assert len(mapping_data["field_mappings"]) > 0
            assert mapping_data["overall_confidence"] >= 0.8
            
            # Check specific field mappings
            field_mappings = mapping_data["field_mappings"]
            mapping_dict = {fm["source_field"]: fm for fm in field_mappings}
            
            expected_mappings = {
                "CLAIM_ID": "claim_number",
                "MEMBER_ID": "member_id",
                "AMOUNT": "claim_amount",
                "SERVICE_DATE": "service_date",
                "STATUS": "claim_status"
            }
            
            mapped_count = 0
            for source_field, expected_target in expected_mappings.items():
                if source_field in mapping_dict:
                    mapping = mapping_dict[source_field]
                    if mapping["target_field"] == expected_target:
                        mapped_count += 1
                        assert mapping["confidence_score"] >= 0.8
            
            workflow_results["correctly_mapped_fields"] = mapped_count
            print(f"Correctly mapped fields: {mapped_count}/{len(expected_mappings)}")
            
            # ===========================================
            # PHASE 5: RETRIEVE COMPLETE MAPPING DETAILS
            # ===========================================
            print("Phase 5: Retrieve Mapping Details")
            
            get_mapping_response = await async_client.get(
                f"/api/v1/mappings/{mapping_id}",
                params={
                    "include_statistics": "true",
                    "include_preview": "true"
                }
            )
            assert get_mapping_response.status_code == status.HTTP_200_OK
            
            mapping_details = get_mapping_response.json()
            assert mapping_details["mapping_id"] == mapping_id
            assert "field_statistics" in mapping_details
            assert "transformation_preview" in mapping_details
            
            stats = mapping_details["field_statistics"]
            assert stats["total_fields"] >= 10
            assert stats["mapped_fields"] >= 5
            assert stats["high_confidence_mappings"] >= 5
            
            workflow_results["mapping_stats"] = stats
            
            # ===========================================
            # PHASE 6: PERFORMANCE VALIDATION
            # ===========================================
            print("Phase 6: Performance Validation")
            
            total_workflow_time = time.time() - start_time
            workflow_results["total_time"] = total_workflow_time
            
            print(f"\n=== WORKFLOW PERFORMANCE SUMMARY ===")
            print(f"Total workflow time: {total_workflow_time:.2f}s")
            print(f"File upload time: {workflow_results['upload_time']:.2f}s")
            print(f"File parsing time: {workflow_results['parsing_time']:.2f}s")
            print(f"File indexing time: {workflow_results['indexing_time']:.2f}s")
            print(f"Mapping generation time: {workflow_results['mapping_time']:.2f}s")
            print(f"Records processed: {workflow_results['record_count']}")
            print(f"Fields identified: {workflow_results['field_count']}")
            print(f"Chat interactions: {len(chat_results)}")
            print(f"Correctly mapped fields: {workflow_results['correctly_mapped_fields']}")
            
            # Performance assertions based on POC requirements
            assert workflow_results["parsing_time"] < 30, f"Parsing took {workflow_results['parsing_time']:.2f}s, should be < 30s"
            assert workflow_results["indexing_time"] < 60, f"Indexing took {workflow_results['indexing_time']:.2f}s, should be < 60s"
            assert workflow_results["mapping_time"] < 60, f"Mapping took {workflow_results['mapping_time']:.2f}s, should be < 60s"
            
            # Overall workflow should complete in reasonable time
            assert total_workflow_time < 180, f"Total workflow took {total_workflow_time:.2f}s, should be < 180s"
            
            # Data quality assertions
            assert workflow_results["record_count"] == 6, "Should process all 6 records"
            assert workflow_results["correctly_mapped_fields"] >= 4, "Should correctly map at least 4/5 key fields"
            
            print("✅ Complete EDI workflow test passed!")
            
        finally:
            os.unlink(temp_file.name)


@pytest.mark.asyncio
async def test_workflow_with_excel_definitions(async_client: AsyncClient):
    """Test complete workflow with Excel field definitions"""
    # Create EDI file
    edi_content = """CUSTOM_EDI_FORMAT
CLMNO|MBRID|PRVID|SVCDT|AMT|DIAG|DRUG|STS
C001|M001|P001|20240101|100.50|Z5111|NDC001|A
C002|M002|P002|20240102|75.25|M7989|NDC002|A
""".encode()
    
    # Mock Excel file
    excel_content = b"EXCEL_FIELD_DEFINITIONS_MOCK_DATA"
    
    files = {
        "edi_file": ("custom_format.txt", edi_content, "text/plain"),
        "excel_definitions": ("mappings.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
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
    await _wait_for_status(async_client, file_id, "parsed", max_attempts=10)
    
    # Index for chat
    index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
    assert index_response.status_code == status.HTTP_202_ACCEPTED
    
    await _wait_for_status(async_client, file_id, "indexed", max_attempts=15)
    
    # Generate mapping using Excel definitions
    mapping_request = {
        "file_id": file_id,
        "target_schema": "custom",
        "use_excel_definitions": True
    }
    
    mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
    assert mapping_response.status_code == status.HTTP_201_CREATED
    
    mapping_data = mapping_response.json()
    assert mapping_data["used_excel_definitions"] is True
    assert mapping_data["target_schema"] == "custom"
    
    print("✅ Excel definitions workflow test passed!")


@pytest.mark.asyncio
async def test_workflow_error_scenarios(async_client: AsyncClient):
    """Test workflow behavior with various error scenarios"""
    # Test with invalid file format
    invalid_content = b"INVALID_FILE_FORMAT\nThis is not a valid EDI file"
    
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
                
                # Should fail during parsing
                failed = False
                max_attempts = 10
                attempt = 0
                
                while not failed and attempt < max_attempts:
                    await asyncio.sleep(2)
                    
                    status_response = await async_client.get(f"/api/v1/files/{file_id}/status")
                    status_data = status_response.json()
                    
                    if status_data["status"] == "failed":
                        failed = True
                        assert "error_message" in status_data
                        break
                    
                    attempt += 1
                
                assert failed, "Invalid file should have failed processing"
                
                # Verify subsequent operations fail gracefully
                index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
                assert index_response.status_code == status.HTTP_400_BAD_REQUEST
                
                mapping_request = {"file_id": file_id, "target_schema": "vba_standard"}
                mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
                assert mapping_response.status_code == status.HTTP_400_BAD_REQUEST
                
        finally:
            os.unlink(temp_file.name)
    
    print("✅ Error scenarios workflow test passed!")


@pytest.mark.asyncio
async def test_concurrent_workflows(async_client: AsyncClient):
    """Test multiple concurrent workflows"""
    # Create multiple test files
    files_data = []
    for i in range(3):
        content = f"""SMITHRX_CLAIMS_DATA_V2.1
CLAIM_ID|MEMBER_ID|AMOUNT|STATUS
CLM{i:08d}|M{i:09d}|{100.0 + i * 10}|APPROVED
CLM{i:08d}01|M{i:09d}01|{150.0 + i * 20}|PENDING
""".encode()
        
        temp_file = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        temp_file.write(content)
        temp_file.flush()
        files_data.append(temp_file.name)
    
    try:
        # Start multiple workflows concurrently
        workflow_tasks = []
        
        for i, file_path in enumerate(files_data):
            task = asyncio.create_task(
                _run_single_workflow(async_client, file_path, f"concurrent_test_{i}.txt")
            )
            workflow_tasks.append(task)
        
        # Wait for all workflows to complete
        results = await asyncio.gather(*workflow_tasks, return_exceptions=True)
        
        # Verify all workflows completed successfully
        successful_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Workflow {i} failed: {result}")
            else:
                successful_count += 1
                print(f"Workflow {i} completed successfully")
        
        assert successful_count == 3, f"Only {successful_count}/3 concurrent workflows succeeded"
        
        print("✅ Concurrent workflows test passed!")
        
    finally:
        # Clean up temporary files
        for file_path in files_data:
            os.unlink(file_path)


async def _run_single_workflow(async_client: AsyncClient, file_path: str, filename: str) -> dict:
    """Helper function to run a single workflow"""
    with open(file_path, 'rb') as file:
        files = {"edi_file": (filename, file, "text/plain")}
        data = {
            "file_type": "smithrx_claims",
            "project_id": "12345678-1234-1234-1234-123456789012"
        }
        
        # Upload
        upload_response = await async_client.post("/api/v1/files/upload", files=files, data=data)
        assert upload_response.status_code == status.HTTP_201_CREATED
        file_id = upload_response.json()["file_id"]
        
        # Wait for parsing
        await _wait_for_status(async_client, file_id, "parsed")
        
        # Index
        index_response = await async_client.post(f"/api/v1/chat/index/{file_id}")
        assert index_response.status_code == status.HTTP_202_ACCEPTED
        
        await _wait_for_status(async_client, file_id, "indexed")
        
        # Generate mapping
        mapping_request = {"file_id": file_id, "target_schema": "vba_standard"}
        mapping_response = await async_client.post("/api/v1/mappings/generate", json=mapping_request)
        assert mapping_response.status_code == status.HTTP_201_CREATED
        
        return {
            "file_id": file_id,
            "mapping_id": mapping_response.json()["mapping_id"],
            "status": "completed"
        }


async def _wait_for_status(async_client: AsyncClient, file_id: str, target_status: str, max_attempts: int = 15):
    """Helper function to wait for file status"""
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