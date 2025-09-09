"""
Mapping model for field mappings between EDI formats and target schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class MappingStatus(str, Enum):
    """Mapping generation status"""
    GENERATING = "generating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    FAILED = "failed"


class TargetSchema(str, Enum):
    """Supported target schemas"""
    VBA_STANDARD = "vba_standard"
    CUSTOM = "custom"


class DataType(str, Enum):
    """Data types for field mappings"""
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    JSON = "json"


class ValidationRule(BaseModel):
    """Field validation rule"""
    rule_type: str = Field(..., description="Type of validation: required, pattern, range, length")
    rule_value: Union[str, int, float, bool, Dict[str, Any]] = Field(..., description="Rule value or configuration")
    error_message: Optional[str] = None


class TransformationRule(BaseModel):
    """Field transformation rule"""
    transformation_type: str = Field(..., description="Type: format, calculate, lookup, concatenate, split")
    transformation_config: Dict[str, Any] = Field(..., description="Transformation configuration")
    description: Optional[str] = None


class FieldMapping(BaseModel):
    """Individual field mapping definition"""
    source_field: str = Field(..., description="Source field name from EDI file")
    target_field: str = Field(..., description="Target field name in schema")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in this mapping")
    data_type: DataType = Field(..., description="Expected data type")
    is_required: bool = Field(default=False, description="Whether field is required")
    sample_values: List[str] = Field(default=[], description="Sample values from source")
    validation_rules: List[ValidationRule] = Field(default=[], description="Validation rules")
    transformation_rules: List[TransformationRule] = Field(default=[], description="Transformation rules")
    validation_status: str = Field(default="pending", description="Validation status: pending, valid, invalid")
    notes: Optional[str] = Field(None, description="Additional notes or comments")
    created_by: Optional[str] = Field(None, description="User or system that created mapping")
    last_modified: Optional[datetime] = None

    @validator('confidence_score')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence_score must be between 0.0 and 1.0')
        return v

    @validator('validation_status')
    def validate_status(cls, v):
        if v not in ['pending', 'valid', 'invalid', 'warning']:
            raise ValueError('validation_status must be pending, valid, invalid, or warning')
        return v


class UnmappedField(BaseModel):
    """Field that could not be mapped automatically"""
    field_name: str
    data_type: Optional[DataType] = None
    sample_values: List[str] = []
    reason: str = Field(..., description="Why field could not be mapped")
    suggested_mappings: List[Dict[str, Any]] = Field(default=[], description="Suggested target mappings")
    requires_manual_review: bool = Field(default=True)


class MappingGenerateRequest(BaseModel):
    """Request to generate field mappings"""
    file_id: str
    target_schema: TargetSchema = Field(..., description="Target schema to map to")
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum confidence for auto-mapping")
    use_excel_definitions: bool = Field(default=False, description="Use uploaded Excel definitions")
    custom_mapping_rules: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Custom mapping rules")
    validate_with_samples: bool = Field(default=True, description="Validate mappings with sample data")
    sample_size: int = Field(default=100, ge=1, le=1000, description="Number of sample records for validation")
    async_processing: bool = Field(default=False, description="Process asynchronously for large files")
    force_regenerate: bool = Field(default=False, description="Force regenerate existing mapping")

    @validator('file_id')
    def validate_file_id(cls, v):
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v


class ValidationError(BaseModel):
    """Validation error details"""
    field_name: str
    error_type: str
    error_message: str
    record_index: Optional[int] = None
    sample_value: Optional[str] = None


class ValidationResults(BaseModel):
    """Mapping validation results"""
    total_records_validated: int
    validation_errors: List[ValidationError] = []
    validation_warnings: List[ValidationError] = []
    data_quality_score: float = Field(..., ge=0.0, le=1.0)
    field_coverage: float = Field(..., ge=0.0, le=1.0, description="Percentage of fields mapped")
    error_rate: float = Field(..., ge=0.0, le=1.0)


class FieldStatistics(BaseModel):
    """Field mapping statistics"""
    total_fields: int
    mapped_fields: int
    unmapped_fields: int
    high_confidence_mappings: int = Field(..., description="Mappings with confidence >= 0.9")
    medium_confidence_mappings: int = Field(..., description="Mappings with confidence 0.7-0.9")
    low_confidence_mappings: int = Field(..., description="Mappings with confidence < 0.7")
    manual_review_required: int


class TransformationPreview(BaseModel):
    """Preview of data transformation"""
    sample_records: List[Dict[str, Any]] = Field(..., description="Sample transformed records")
    transformation_summary: Dict[str, str] = Field(..., description="Summary of transformations applied")


class MappingResponse(BaseModel):
    """Response for mapping generation"""
    mapping_id: str
    file_id: str
    target_schema: TargetSchema
    status: MappingStatus
    field_mappings: List[FieldMapping]
    unmapped_fields: List[UnmappedField] = []
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    validation_results: Optional[ValidationResults] = None
    used_excel_definitions: bool = Field(default=False)
    custom_field_count: Optional[int] = None
    custom_rules_applied: Optional[int] = None
    regenerated: bool = Field(default=False)
    previous_mapping_id: Optional[str] = None
    manual_review_required: bool = Field(default=False)
    processing_time_ms: Optional[int] = None
    correlation_id: Optional[str] = None

    # For async processing
    job_id: Optional[str] = None
    progress_url: Optional[str] = None
    estimated_completion: Optional[datetime] = None

    class Config:
        from_attributes = True


class MappingDetailResponse(BaseModel):
    """Detailed mapping response with additional info"""
    mapping_id: str
    file_id: str
    target_schema: TargetSchema
    status: MappingStatus
    field_mappings: List[FieldMapping]
    unmapped_fields: List[UnmappedField] = []
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    version: int = Field(default=1)
    
    # Extended details
    validation_results: Optional[ValidationResults] = None
    field_statistics: Optional[FieldStatistics] = None
    transformation_preview: Optional[TransformationPreview] = None
    
    # Excel definitions metadata
    excel_definitions_used: bool = Field(default=False)
    excel_field_count: Optional[int] = None
    excel_filename: Optional[str] = None
    
    # Schema information
    schema_definition: Optional[Dict[str, Any]] = None
    custom_fields: Optional[List[Dict[str, Any]]] = None
    
    # Processing metadata
    processing_logs: Optional[List[str]] = None
    progress_percentage: Optional[int] = Field(None, ge=0, le=100)
    
    # Archive status
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None
    
    # Export information
    supported_export_formats: List[str] = Field(default=["json", "csv", "excel"])
    
    # History and versioning
    change_history: Optional[List[Dict[str, Any]]] = None
    
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class MappingUpdateRequest(BaseModel):
    """Request to update field mappings"""
    field_mappings: List[FieldMapping]
    notes: Optional[str] = None
    status: Optional[MappingStatus] = None


class MappingExportRequest(BaseModel):
    """Request to export mapping configuration"""
    mapping_id: str
    export_format: str = Field(default="json", description="Export format: json, csv, excel, yaml")
    include_samples: bool = Field(default=True)
    include_validation: bool = Field(default=True)
    
    @validator('export_format')
    def validate_format(cls, v):
        if v not in ['json', 'csv', 'excel', 'yaml']:
            raise ValueError('export_format must be json, csv, excel, or yaml')
        return v


class MappingImportRequest(BaseModel):
    """Request to import mapping configuration"""
    file_id: str
    mapping_configuration: Dict[str, Any] = Field(..., description="Mapping configuration to import")
    overwrite_existing: bool = Field(default=False)
    validate_before_import: bool = Field(default=True)


class MappingBulkOperation(BaseModel):
    """Bulk operation on multiple mappings"""
    mapping_ids: List[str] = Field(..., min_items=1, max_items=20)
    operation: str = Field(..., description="Operation: approve, reject, archive, delete")
    
    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['approve', 'reject', 'archive', 'delete']:
            raise ValueError('operation must be approve, reject, archive, or delete')
        return v


class MappingComparisonRequest(BaseModel):
    """Request to compare two mappings"""
    mapping_id_1: str
    mapping_id_2: str
    include_field_details: bool = Field(default=True)


class MappingComparisonResult(BaseModel):
    """Result of mapping comparison"""
    mapping_1_id: str
    mapping_2_id: str
    fields_only_in_1: List[str] = []
    fields_only_in_2: List[str] = []
    fields_with_different_mappings: List[Dict[str, Any]] = []
    confidence_score_differences: Dict[str, float] = {}
    overall_similarity_score: float = Field(..., ge=0.0, le=1.0)