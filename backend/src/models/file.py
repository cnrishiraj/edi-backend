"""
File model for EDI file uploads and processing
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class FileStatus(str, Enum):
    """File processing status enumeration"""
    UPLOADING = "uploading"
    PARSING = "parsing" 
    PARSED = "parsed"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
    ARCHIVED = "archived"


class FileType(str, Enum):
    """Supported file types"""
    SMITHRX_CLAIMS = "smithrx_claims"


class FileUploadRequest(BaseModel):
    """Request model for file upload"""
    file_type: FileType = Field(..., description="Type of EDI file being uploaded")
    project_id: str = Field(..., description="Project UUID this file belongs to")
    
    @validator('project_id')
    def validate_project_id(cls, v):
        """Validate project_id is a valid UUID format"""
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('project_id must be a valid UUID')
        return v


class ProcessingLog(BaseModel):
    """Processing log entry"""
    timestamp: datetime
    level: str = Field(..., description="Log level: INFO, WARNING, ERROR")
    message: str = Field(..., description="Log message")
    
    @validator('level')
    def validate_level(cls, v):
        if v not in ['INFO', 'WARNING', 'ERROR']:
            raise ValueError('level must be INFO, WARNING, or ERROR')
        return v


class FileMetadata(BaseModel):
    """File metadata and statistics"""
    original_filename: str
    content_type: str
    file_size_bytes: int
    upload_timestamp: datetime
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    record_count: Optional[int] = None
    field_definitions_count: Optional[int] = None
    data_quality_score: Optional[float] = None
    sample_records: Optional[List[Dict[str, Any]]] = None
    parsing_errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class FileResponse(BaseModel):
    """Response model for file operations"""
    file_id: str
    filename: str
    file_type: FileType
    project_id: str
    status: FileStatus
    file_size: int
    upload_timestamp: datetime
    last_updated: Optional[datetime] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    records_count: Optional[int] = Field(None, ge=0)
    field_definitions_count: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    processing_logs: Optional[List[ProcessingLog]] = None
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class FileStatusResponse(BaseModel):
    """Response model for file status endpoint"""
    file_id: str
    status: FileStatus
    last_updated: datetime
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    records_count: Optional[int] = Field(None, ge=0)
    field_definitions_count: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    processing_logs: Optional[List[ProcessingLog]] = None
    estimated_completion: Optional[datetime] = None
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Response model for listing files"""
    files: List[FileResponse]
    total_count: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)
    has_more: bool


class FileStatsResponse(BaseModel):
    """File processing statistics"""
    total_files: int
    files_by_status: Dict[FileStatus, int]
    total_records_processed: int
    average_processing_time_seconds: Optional[float]
    success_rate: float = Field(..., ge=0.0, le=1.0)
    most_recent_upload: Optional[datetime]


class FileExportRequest(BaseModel):
    """Request for file data export"""
    file_id: str
    export_format: str = Field(default="json", description="Export format: json, csv, xlsx")
    include_metadata: bool = Field(default=True, description="Include file metadata")
    record_limit: Optional[int] = Field(None, ge=1, le=10000, description="Maximum records to export")
    
    @validator('file_id')
    def validate_file_id(cls, v):
        """Validate file_id is a valid UUID format"""
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v
    
    @validator('export_format')
    def validate_export_format(cls, v):
        if v not in ['json', 'csv', 'xlsx']:
            raise ValueError('export_format must be json, csv, or xlsx')
        return v


class FileValidationResult(BaseModel):
    """Result of file validation"""
    is_valid: bool
    validation_errors: List[str] = []
    validation_warnings: List[str] = []
    record_count: Optional[int] = None
    field_count: Optional[int] = None
    detected_format: Optional[str] = None
    encoding: Optional[str] = None
    delimiter: Optional[str] = None
    has_header: Optional[bool] = None


class FileBulkOperation(BaseModel):
    """Bulk operation on multiple files"""
    file_ids: List[str] = Field(..., min_items=1, max_items=50)
    operation: str = Field(..., description="Operation: delete, archive, reprocess")
    
    @validator('file_ids')
    def validate_file_ids(cls, v):
        """Validate all file_ids are valid UUIDs"""
        import uuid
        for file_id in v:
            try:
                uuid.UUID(file_id)
            except ValueError:
                raise ValueError(f'Invalid UUID format: {file_id}')
        return v
    
    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['delete', 'archive', 'reprocess']:
            raise ValueError('operation must be delete, archive, or reprocess')
        return v


class FileBulkOperationResult(BaseModel):
    """Result of bulk file operation"""
    successful_operations: List[str] = []
    failed_operations: List[Dict[str, str]] = []  # file_id -> error_message
    total_requested: int
    total_successful: int
    total_failed: int