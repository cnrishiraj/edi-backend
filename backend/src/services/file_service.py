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
            
            # Parse the file
            parser = SmithRxParser(BytesIO(file_bytes), "smithrx_claims")
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


# Global file service instance
_file_service: Optional[FileService] = None


def get_file_service() -> FileService:
    """Get global file service instance"""
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service