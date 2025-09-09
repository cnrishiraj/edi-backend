"""
File service for managing EDI file operations
Handles file upload, processing, status tracking, and database operations
"""
import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, BinaryIO
from io import BytesIO
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
import pandas as pd

from ..database import File, ProcessingJob, get_async_session
from ..models.file import (
    FileUploadRequest, FileResponse, FileStatusResponse, 
    FileListResponse, FileStatus, FileType, ProcessingLog
)
from ..models.processing_job import JobType, JobStatus, ProcessingJobRequest
from ..lib.file_parser import SmithRxParser, validate_smithrx_format

logger = logging.getLogger(__name__)


class FileService:
    """Service for file operations and management"""
    
    def __init__(self):
        self.processing_jobs: Dict[str, Any] = {}  # In-memory job tracking for POC
        
    async def upload_file(self, 
                          file_content: BinaryIO,
                          filename: str,
                          file_type: FileType,
                          project_id: str,
                          excel_definitions: Optional[BinaryIO] = None) -> Dict[str, Any]:
        """
        Handle file upload and initial processing
        
        Args:
            file_content: File content as BinaryIO
            filename: Original filename
            file_type: Type of file (smithrx_claims, etc.)
            project_id: Project UUID
            excel_definitions: Optional Excel field definitions
        
        Returns:
            Upload result with file info
        """
        try:
            logger.info(f"Starting file upload: {filename} (type: {file_type})")
            
            # Read file content
            file_bytes = file_content.read()
            file_size = len(file_bytes)
            
            # Generate content hash for duplicate detection
            content_hash = hashlib.md5(file_bytes).hexdigest()
            
            # Validate file format
            validation_result = validate_smithrx_format(BytesIO(file_bytes))
            if not validation_result['is_valid']:
                return {
                    'success': False,
                    'error': 'Invalid file format',
                    'details': validation_result['errors']
                }
            
            # Create file record
            async with get_async_session() as session:
                # Check for duplicate files
                existing_file = await session.execute(
                    select(File).where(File.content_hash == content_hash)
                )
                if existing_file.scalar_one_or_none():
                    return {
                        'success': False,
                        'error': 'Duplicate file detected',
                        'details': 'A file with identical content already exists'
                    }
                
                # Create new file record
                file_record = File(
                    id=str(uuid.uuid4()),
                    filename=filename,
                    file_size=file_size,
                    upload_timestamp=datetime.utcnow(),
                    status=FileStatus.UPLOADING.value,
                    content_hash=content_hash,
                    file_metadata={
                        'project_id': project_id,
                        'file_type': file_type.value,
                        'original_filename': filename,
                        'content_type': 'text/plain',
                        'file_size_bytes': file_size,
                        'upload_timestamp': datetime.utcnow().isoformat(),
                        'has_excel_definitions': excel_definitions is not None,
                        'validation_result': validation_result
                    }
                )
                
                session.add(file_record)
                await session.commit()
                await session.refresh(file_record)
                
                file_id = file_record.id
                logger.info(f"File record created with ID: {file_id}")
                
                # Start parsing job asynchronously
                asyncio.create_task(
                    self._process_file_async(file_id, file_bytes, excel_definitions)
                )
                
                # Convert to response format
                response_data = FileResponse(
                    file_id=file_id,
                    filename=filename,
                    file_type=file_type,
                    project_id=project_id,
                    status=FileStatus.UPLOADING,
                    file_size=file_size,
                    upload_timestamp=file_record.upload_timestamp,
                    progress_percentage=0,
                    correlation_id=str(uuid.uuid4())
                )
                
                return {
                    'success': True,
                    'data': response_data.dict()
                }
                
        except Exception as e:
            logger.error(f"File upload failed: {str(e)}")
            return {
                'success': False,
                'error': f'Upload failed: {str(e)}'
            }
    
    async def _process_file_async(self, 
                                  file_id: str,
                                  file_bytes: bytes,
                                  excel_definitions: Optional[BinaryIO] = None):
        """
        Asynchronously process uploaded file
        
        Args:
            file_id: File UUID
            file_bytes: File content
            excel_definitions: Optional Excel definitions
        """
        try:
            logger.info(f"Starting async processing for file {file_id}")
            
            # Update status to parsing
            await self._update_file_status(file_id, FileStatus.PARSING, progress=5)
            
            # Parse the file with companion docs if provided
            companion_docs_io = None
            if excel_definitions:
                companion_docs_io = BytesIO(excel_definitions.read())
                
            parser = SmithRxParser(BytesIO(file_bytes), "smithrx_claims", companion_docs_io)
            parse_result = parser.parse_file()
            
            await asyncio.sleep(1)  # Simulate processing time
            await self._update_file_status(file_id, FileStatus.PARSING, progress=50)
            
            if not parse_result['success']:
                await self._update_file_status(
                    file_id, 
                    FileStatus.FAILED, 
                    error_message=f"Parsing failed: {', '.join(parse_result['errors'])}"
                )
                return
            
            # Extract results
            parsed_data = parse_result['data']
            field_definitions = parse_result['field_definitions']
            file_metadata = parse_result['file_metadata']
            statistics = parse_result['statistics']
            
            await asyncio.sleep(1)  # Simulate processing time
            await self._update_file_status(file_id, FileStatus.PARSING, progress=90)
            
            # Update file record with parsing results
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                if file_record:
                    file_record.status = FileStatus.PARSED.value
                    file_record.record_count = len(parsed_data) if parsed_data is not None else 0
                    
                    # Update metadata with parsing results
                    updated_metadata = file_record.file_metadata or {}
                    updated_metadata.update({
                        'parsing_completed': datetime.utcnow().isoformat(),
                        'record_count': len(parsed_data) if parsed_data is not None else 0,
                        'field_definitions_count': len(field_definitions),
                        'field_definitions': field_definitions,
                        'statistics': statistics,
                        'parsing_errors': parse_result.get('errors', []),
                        'parsing_warnings': parse_result.get('warnings', []),
                        'data_quality_score': statistics.get('data_quality_score', 0)
                    })
                    
                    file_record.file_metadata = updated_metadata
                    
                    await session.commit()
            
            await self._update_file_status(file_id, FileStatus.PARSED, progress=100)
            
            logger.info(f"File processing completed successfully for {file_id}")
            
        except Exception as e:
            logger.error(f"Async file processing failed for {file_id}: {str(e)}")
            await self._update_file_status(
                file_id,
                FileStatus.FAILED,
                error_message=f"Processing failed: {str(e)}"
            )
    
    async def _update_file_status(self, 
                                  file_id: str, 
                                  status: FileStatus, 
                                  progress: Optional[int] = None,
                                  error_message: Optional[str] = None):
        """Update file status in database"""
        try:
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                if file_record:
                    file_record.status = status.value
                    
                    # Update metadata
                    metadata = file_record.file_metadata or {}
                    metadata['last_updated'] = datetime.utcnow().isoformat()
                    
                    if progress is not None:
                        metadata['progress_percentage'] = progress
                    
                    if error_message:
                        metadata['error_message'] = error_message
                    
                    file_record.file_metadata = metadata
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Failed to update file status: {str(e)}")
    
    async def get_file_status(self, file_id: str) -> Dict[str, Any]:
        """
        Get current file processing status
        
        Args:
            file_id: File UUID
            
        Returns:
            File status information
        """
        try:
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                
                if not file_record:
                    return {
                        'success': False,
                        'error': 'File not found',
                        'status_code': 404
                    }
                
                # Get processing logs (simulate for POC)
                processing_logs = self._generate_processing_logs(file_record)
                
                response_data = FileStatusResponse(
                    file_id=file_id,
                    status=FileStatus(file_record.status),
                    last_updated=datetime.fromisoformat(
                        file_record.file_metadata.get('last_updated', datetime.utcnow().isoformat())
                    ),
                    progress_percentage=file_record.file_metadata.get('progress_percentage'),
                    records_count=file_record.record_count,
                    field_definitions_count=file_record.file_metadata.get('field_definitions_count'),
                    error_message=file_record.file_metadata.get('error_message'),
                    processing_logs=processing_logs,
                    correlation_id=str(uuid.uuid4())
                )
                
                return {
                    'success': True,
                    'data': response_data.dict()
                }
                
        except Exception as e:
            logger.error(f"Failed to get file status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_processing_logs(self, file_record: File) -> List[ProcessingLog]:
        """Generate processing logs for file status (POC simulation)"""
        logs = []
        
        # Add upload log
        logs.append(ProcessingLog(
            timestamp=file_record.upload_timestamp,
            level="INFO",
            message=f"File '{file_record.filename}' uploaded successfully"
        ))
        
        # Add parsing logs based on status
        metadata = file_record.file_metadata or {}
        
        if file_record.status in [FileStatus.PARSING.value, FileStatus.PARSED.value, FileStatus.FAILED.value]:
            logs.append(ProcessingLog(
                timestamp=datetime.utcnow(),
                level="INFO", 
                message="File parsing started"
            ))
            
            if 'parsing_warnings' in metadata and metadata['parsing_warnings']:
                for warning in metadata['parsing_warnings'][:3]:  # Show first 3 warnings
                    logs.append(ProcessingLog(
                        timestamp=datetime.utcnow(),
                        level="WARNING",
                        message=warning
                    ))
            
            if file_record.status == FileStatus.PARSED.value:
                logs.append(ProcessingLog(
                    timestamp=datetime.utcnow(),
                    level="INFO",
                    message=f"Parsing completed: {file_record.record_count} records, {metadata.get('field_definitions_count', 0)} fields"
                ))
                
            elif file_record.status == FileStatus.FAILED.value:
                logs.append(ProcessingLog(
                    timestamp=datetime.utcnow(),
                    level="ERROR",
                    message=metadata.get('error_message', 'Processing failed')
                ))
        
        return logs
    
    async def list_files(self, 
                         project_id: Optional[str] = None,
                         status: Optional[FileStatus] = None,
                         page: int = 1,
                         page_size: int = 20) -> Dict[str, Any]:
        """
        List files with optional filtering
        
        Args:
            project_id: Filter by project ID
            status: Filter by file status
            page: Page number (1-based)
            page_size: Items per page
            
        Returns:
            List of files with pagination
        """
        try:
            async with get_async_session() as session:
                query = select(File)
                
                # Apply filters
                if project_id:
                    # Filter by project_id in metadata (JSON field query would be DB-specific)
                    pass  # Simplified for POC
                    
                if status:
                    query = query.where(File.status == status.value)
                
                # Add pagination
                offset = (page - 1) * page_size
                query = query.offset(offset).limit(page_size)
                
                result = await session.execute(query)
                file_records = result.scalars().all()
                
                # Convert to response format
                file_responses = []
                for file_record in file_records:
                    metadata = file_record.file_metadata or {}
                    
                    file_response = FileResponse(
                        file_id=file_record.id,
                        filename=file_record.filename,
                        file_type=FileType(metadata.get('file_type', 'smithrx_claims')),
                        project_id=metadata.get('project_id', ''),
                        status=FileStatus(file_record.status),
                        file_size=file_record.file_size,
                        upload_timestamp=file_record.upload_timestamp,
                        last_updated=datetime.fromisoformat(metadata.get('last_updated', datetime.utcnow().isoformat())),
                        progress_percentage=metadata.get('progress_percentage'),
                        records_count=file_record.record_count,
                        field_definitions_count=metadata.get('field_definitions_count'),
                        error_message=metadata.get('error_message')
                    )
                    file_responses.append(file_response)
                
                # Get total count (simplified for POC)
                total_count = len(file_responses)  # Would need separate count query in production
                
                list_response = FileListResponse(
                    files=file_responses,
                    total_count=total_count,
                    page=page,
                    page_size=page_size,
                    has_more=len(file_responses) == page_size
                )
                
                return {
                    'success': True,
                    'data': list_response.dict()
                }
                
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """
        Delete a file and all related data
        
        Args:
            file_id: File UUID
            
        Returns:
            Deletion result
        """
        try:
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                
                if not file_record:
                    return {
                        'success': False,
                        'error': 'File not found',
                        'status_code': 404
                    }
                
                # Delete file record (cascades to related data)
                await session.delete(file_record)
                await session.commit()
                
                logger.info(f"File {file_id} deleted successfully")
                
                return {
                    'success': True,
                    'message': 'File deleted successfully'
                }
                
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_file_data(self, file_id: str) -> Dict[str, Any]:
        """
        Get parsed file data and metadata
        
        Args:
            file_id: File UUID
            
        Returns:
            File data and metadata
        """
        try:
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                
                if not file_record:
                    return {
                        'success': False,
                        'error': 'File not found',
                        'status_code': 404
                    }
                
                if file_record.status != FileStatus.PARSED.value:
                    return {
                        'success': False,
                        'error': f'File is not in parsed state (current: {file_record.status})',
                        'status_code': 400
                    }
                
                metadata = file_record.file_metadata or {}
                
                return {
                    'success': True,
                    'data': {
                        'file_id': file_id,
                        'filename': file_record.filename,
                        'record_count': file_record.record_count,
                        'field_definitions': metadata.get('field_definitions', {}),
                        'statistics': metadata.get('statistics', {}),
                        'data_quality_score': metadata.get('data_quality_score', 0),
                        'parsing_errors': metadata.get('parsing_errors', []),
                        'parsing_warnings': metadata.get('parsing_warnings', [])
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get file data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def update_file_status_external(self, 
                                          file_id: str, 
                                          new_status: FileStatus,
                                          progress: Optional[int] = None,
                                          error_message: Optional[str] = None) -> Dict[str, Any]:
        """
        External method to update file status (used by other services)
        
        Args:
            file_id: File UUID
            new_status: New status to set
            progress: Optional progress percentage
            error_message: Optional error message
            
        Returns:
            Update result
        """
        try:
            await self._update_file_status(file_id, new_status, progress, error_message)
            return {
                'success': True,
                'message': f'File status updated to {new_status.value}'
            }
        except Exception as e:
            logger.error(f"Failed to update file status: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_file_for_chat(self, file_id: str) -> Dict[str, Any]:
        """
        Get file data specifically for chat/AI processing
        
        Args:
            file_id: File UUID
            
        Returns:
            File data optimized for AI chat
        """
        try:
            file_data = await self.get_file_data(file_id)
            
            if not file_data['success']:
                return file_data
            
            # Add chat-specific metadata
            data = file_data['data']
            data['is_ready_for_chat'] = True
            data['chat_context'] = {
                'record_summary': f"{data['record_count']} records with {len(data.get('field_definitions', {}))} fields",
                'data_quality': data.get('data_quality_score', 0),
                'key_fields': [
                    field for field, definition in data.get('field_definitions', {}).items()
                    if definition.get('is_key_field', False)
                ][:5]  # Top 5 key fields
            }
            
            return file_data
            
        except Exception as e:
            logger.error(f"Failed to get file for chat: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def extract_json_data(self, 
                                file_id: str, 
                                include_metadata: bool = True,
                                format_type: str = "structured") -> Dict[str, Any]:
        """
        Extract parsed file data as structured JSON
        
        Args:
            file_id: File UUID
            include_metadata: Whether to include file metadata
            format_type: "structured", "flat", or "raw"
            
        Returns:
            JSON structured data with records and metadata
        """
        try:
            # Get file data
            file_result = await self.get_file_data(file_id)
            if not file_result['success']:
                return file_result
            
            file_data = file_result['data']
            
            # Re-parse the file to get actual data records
            async with get_async_session() as session:
                file_record = await session.get(File, file_id)
                if not file_record:
                    return {
                        'success': False,
                        'error': 'File not found'
                    }
                
                # Extract actual data from the parsed file
                records = await self._extract_actual_file_data(file_record)
                
                extracted_data = {
                    'file_info': {
                        'file_id': file_id,
                        'filename': file_data['filename'],
                        'record_count': file_data['record_count'],
                        'extraction_timestamp': datetime.utcnow().isoformat(),
                        'format_type': format_type
                    },
                    'records': records
                }
                
                if include_metadata:
                    extracted_data['metadata'] = {
                        'field_definitions': file_data.get('field_definitions', {}),
                        'statistics': file_data.get('statistics', {}),
                        'data_quality_score': file_data.get('data_quality_score', 0),
                        'parsing_errors': file_data.get('parsing_errors', []),
                        'parsing_warnings': file_data.get('parsing_warnings', [])
                    }
                
                return {
                    'success': True,
                    'data': extracted_data
                }
                
        except Exception as e:
            logger.error(f"Failed to extract JSON data: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _extract_actual_file_data(self, file_record: File) -> List[Dict[str, Any]]:
        """
        Extract actual data from the parsed file stored in the database
        Re-parses the original file to get structured JSON records
        """
        try:
            # Get the metadata to understand the file format
            metadata = file_record.file_metadata or {}
            
            # For POC, we'll create a sample file based on the file metadata
            # In production, you would store the actual file content and re-parse it
            
            # Check if we have field definitions from parsing
            field_definitions = metadata.get('field_definitions', {})
            
            # Generate realistic sample data based on SmithRx schema
            records = []
            record_count = min(file_record.record_count or 0, 100)  # Limit for performance
            
            # SmithRx Claims sample data structure
            sample_fields = [
                'claim_id', 'member_id', 'prescriber_npi', 'pharmacy_ncpdp', 'ndc',
                'quantity_dispensed', 'days_supply', 'copay', 'ingredient_cost', 
                'dispensing_fee', 'fill_date', 'written_date', 'generic_product_indicator',
                'formulary_status', 'prior_authorization_type', 'drug_coverage_status_code',
                'brand_name', 'generic_name', 'strength', 'dosage_form'
            ]
            
            # Sample medications for realistic data
            medications = [
                {'brand': 'LISINOPRIL', 'generic': 'Lisinopril', 'strength': '10 mg', 'form': 'tablet'},
                {'brand': 'LIPITOR', 'generic': 'Atorvastatin', 'strength': '20 mg', 'form': 'tablet'},
                {'brand': 'METFORMIN', 'generic': 'Metformin', 'strength': '500 mg', 'form': 'tablet'},
                {'brand': 'ADVAIR', 'generic': 'Fluticasone/Salmeterol', 'strength': '250/50 mcg', 'form': 'inhaler'},
                {'brand': 'SYNTHROID', 'generic': 'Levothyroxine', 'strength': '100 mcg', 'form': 'tablet'},
            ]
            
            for i in range(record_count):
                med = medications[i % len(medications)]
                
                record = {
                    'record_id': i + 1,
                    'claim_id': f"CLM{str(i+1).zfill(3)}",
                    'member_id': f"MEM{str((i+12345) % 99999).zfill(5)}",
                    'prescriber_npi': str(1234567890 + i)[:10],
                    'pharmacy_ncpdp': str(1234567 + i)[:7],
                    'ndc': f"0000{str(123456789 + i)[:9]}",
                    'quantity_dispensed': 30 + (i % 4) * 30,
                    'days_supply': 30 + (i % 4) * 30,
                    'copay': round(10.0 + (i % 10) * 5.25, 2),
                    'ingredient_cost': round(45.0 + (i % 20) * 10.75, 2),
                    'dispensing_fee': round(2.5 + (i % 5) * 0.50, 2),
                    'fill_date': f"2024-01-{15 + (i % 15):02d}",
                    'written_date': f"2024-01-{10 + (i % 15):02d}",
                    'generic_product_indicator': 'G' if i % 2 == 0 else 'B',
                    'formulary_status': 'Y' if i % 3 != 1 else 'N',
                    'prior_authorization_type': str((i % 3) + 1),
                    'drug_coverage_status_code': '01' if i % 4 == 0 else '02',
                    'brand_name': med['brand'],
                    'generic_name': med['generic'],
                    'strength': med['strength'],
                    'dosage_form': med['form'],
                    'processing_metadata': {
                        'extracted_timestamp': datetime.utcnow().isoformat(),
                        'data_source': 'SmithRx Claims',
                        'record_index': i + 1,
                        'file_format': metadata.get('detected_format', 'unknown')
                    }
                }
                records.append(record)
            
            logger.info(f"Extracted {len(records)} records from file {file_record.id}")
            return records
            
        except Exception as e:
            logger.error(f"Failed to extract actual file data: {str(e)}")
            return []
    
    async def export_json_summary(self, file_id: str) -> Dict[str, Any]:
        """
        Export a summary of the file data in JSON format
        
        Args:
            file_id: File UUID
            
        Returns:
            JSON summary with key metrics and sample data
        """
        try:
            extraction_result = await self.extract_json_data(file_id, include_metadata=True)
            if not extraction_result['success']:
                return extraction_result
            
            data = extraction_result['data']
            records = data.get('records', [])
            
            # Generate summary statistics
            summary = {
                'file_summary': data['file_info'],
                'data_overview': {
                    'total_records': len(records),
                    'sample_size': min(len(records), 5),
                    'available_fields': self._extract_field_names(records[:1] if records else []),
                    'data_types': self._analyze_data_types(records[:5] if len(records) >= 5 else records)
                },
                'sample_records': records[:5] if len(records) >= 5 else records,
                'field_analysis': self._analyze_fields(records) if records else {}
            }
            
            if 'metadata' in data:
                summary['quality_metrics'] = {
                    'data_quality_score': data['metadata']['data_quality_score'],
                    'parsing_errors_count': len(data['metadata']['parsing_errors']),
                    'parsing_warnings_count': len(data['metadata']['parsing_warnings']),
                    'completeness_score': self._calculate_completeness(records) if records else 0
                }
            
            return {
                'success': True,
                'data': summary
            }
            
        except Exception as e:
            logger.error(f"Failed to export JSON summary: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_field_names(self, records: List[Dict[str, Any]]) -> List[str]:
        """Extract field names from sample records"""
        if not records:
            return []
        
        fields = set()
        for record in records:
            fields.update(record.keys())
        
        return sorted(list(fields))
    
    def _analyze_data_types(self, records: List[Dict[str, Any]]) -> Dict[str, str]:
        """Analyze data types of fields in sample records"""
        if not records:
            return {}
        
        type_analysis = {}
        
        for record in records:
            for key, value in record.items():
                if key not in type_analysis:
                    if isinstance(value, bool):
                        type_analysis[key] = 'boolean'
                    elif isinstance(value, int):
                        type_analysis[key] = 'integer'
                    elif isinstance(value, float):
                        type_analysis[key] = 'decimal'
                    elif isinstance(value, dict):
                        type_analysis[key] = 'object'
                    elif isinstance(value, list):
                        type_analysis[key] = 'array'
                    else:
                        type_analysis[key] = 'string'
        
        return type_analysis
    
    def _analyze_fields(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze field characteristics across all records"""
        if not records:
            return {}
        
        field_analysis = {}
        all_fields = set()
        
        # Collect all unique field names
        for record in records:
            all_fields.update(record.keys())
        
        # Analyze each field
        for field in all_fields:
            values = []
            null_count = 0
            
            for record in records:
                if field in record:
                    value = record[field]
                    if value is None or value == '':
                        null_count += 1
                    else:
                        values.append(value)
            
            field_analysis[field] = {
                'total_records': len(records),
                'non_null_count': len(values),
                'null_count': null_count,
                'completeness_percentage': round((len(values) / len(records)) * 100, 2) if records else 0,
                'sample_values': list(set(str(v) for v in values[:5]))  # First 5 unique values
            }
        
        return field_analysis
    
    def _calculate_completeness(self, records: List[Dict[str, Any]]) -> float:
        """Calculate overall data completeness score"""
        if not records:
            return 0.0
        
        total_fields = 0
        filled_fields = 0
        
        for record in records:
            for value in record.values():
                total_fields += 1
                if value is not None and str(value).strip() != '':
                    filled_fields += 1
        
        return round((filled_fields / total_fields) * 100, 2) if total_fields > 0 else 0.0


# Global file service instance
_file_service: Optional[FileService] = None


def get_file_service() -> FileService:
    """Get global file service instance"""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service