"""
Processing job model for tracking background tasks
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class JobType(str, Enum):
    """Types of processing jobs"""
    PARSE = "parse"
    INDEX = "index"
    MAP = "map"
    EXPORT = "export"
    VALIDATE = "validate"
    TRANSFORM = "transform"
    BACKUP = "backup"
    CLEANUP = "cleanup"


class JobStatus(str, Enum):
    """Job execution status"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRY = "retry"


class JobPriority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class JobProgress(BaseModel):
    """Detailed job progress information"""
    current_step: str = Field(..., description="Current processing step")
    total_steps: int = Field(..., ge=1, description="Total number of steps")
    completed_steps: int = Field(..., ge=0, description="Number of completed steps")
    percentage: int = Field(..., ge=0, le=100, description="Progress percentage")
    estimated_completion: Optional[datetime] = None
    processing_rate: Optional[float] = Field(None, description="Records/items per second")
    
    @validator('completed_steps')
    def validate_completed_steps(cls, v, values):
        total_steps = values.get('total_steps', 0)
        if v > total_steps:
            raise ValueError('completed_steps cannot exceed total_steps')
        return v


class JobError(BaseModel):
    """Job error information"""
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    occurred_at: datetime
    is_retryable: bool = Field(default=False)
    retry_count: int = Field(default=0, ge=0)


class JobConfiguration(BaseModel):
    """Job-specific configuration parameters"""
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=60, ge=0)
    timeout_minutes: int = Field(default=60, ge=1, le=1440)  # Max 24 hours
    priority: JobPriority = JobPriority.NORMAL
    
    # File processing specific
    chunk_size: Optional[int] = Field(None, ge=1)
    batch_size: Optional[int] = Field(None, ge=1)
    parallel_workers: Optional[int] = Field(None, ge=1, le=10)
    
    # Output configuration
    output_format: Optional[str] = None
    include_metadata: bool = Field(default=True)
    compress_output: bool = Field(default=False)
    
    # Notification settings
    notify_on_completion: bool = Field(default=False)
    notify_on_failure: bool = Field(default=True)
    notification_email: Optional[str] = None
    webhook_url: Optional[str] = None


class JobMetrics(BaseModel):
    """Job execution metrics"""
    items_processed: int = Field(default=0, ge=0)
    items_successful: int = Field(default=0, ge=0)
    items_failed: int = Field(default=0, ge=0)
    items_skipped: int = Field(default=0, ge=0)
    
    # Performance metrics
    execution_time_seconds: Optional[float] = None
    average_processing_time_ms: Optional[float] = None
    peak_memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    
    # Data metrics
    bytes_processed: Optional[int] = Field(None, ge=0)
    bytes_output: Optional[int] = Field(None, ge=0)
    compression_ratio: Optional[float] = None
    
    # Quality metrics
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class ProcessingJobRequest(BaseModel):
    """Request to create a processing job"""
    job_type: JobType
    file_id: str
    job_parameters: Dict[str, Any] = Field(default={}, description="Job-specific parameters")
    configuration: Optional[JobConfiguration] = None
    scheduled_at: Optional[datetime] = Field(None, description="Schedule job for later execution")
    depends_on: Optional[List[str]] = Field(None, description="Job IDs this job depends on")
    
    @validator('file_id')
    def validate_file_id(cls, v):
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v
    
    @validator('depends_on')
    def validate_dependencies(cls, v):
        if v:
            import uuid
            for job_id in v:
                try:
                    uuid.UUID(job_id)
                except ValueError:
                    raise ValueError(f'Invalid job ID format: {job_id}')
        return v


class ProcessingJobResponse(BaseModel):
    """Response model for processing jobs"""
    job_id: str
    file_id: str
    job_type: JobType
    status: JobStatus
    priority: JobPriority
    
    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_updated: datetime
    
    # Progress and execution
    progress: Optional[JobProgress] = None
    metrics: Optional[JobMetrics] = None
    error: Optional[JobError] = None
    
    # Configuration
    configuration: Optional[JobConfiguration] = None
    job_parameters: Dict[str, Any] = Field(default={})
    
    # Dependencies and relationships
    depends_on: List[str] = Field(default=[])
    dependent_jobs: List[str] = Field(default=[])
    
    # Output and results
    output_location: Optional[str] = None
    result_summary: Optional[Dict[str, Any]] = None
    
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class JobListRequest(BaseModel):
    """Request to list processing jobs"""
    file_id: Optional[str] = None
    job_type: Optional[JobType] = None
    status: Optional[JobStatus] = None
    priority: Optional[JobPriority] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at", description="Sort field: created_at, priority, status")
    sort_order: str = Field(default="desc", description="Sort order: asc, desc")
    
    @validator('sort_by')
    def validate_sort_by(cls, v):
        if v not in ['created_at', 'started_at', 'completed_at', 'priority', 'status']:
            raise ValueError('sort_by must be created_at, started_at, completed_at, priority, or status')
        return v
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError('sort_order must be asc or desc')
        return v


class JobListResponse(BaseModel):
    """Response for job listing"""
    jobs: List[ProcessingJobResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool
    filters_applied: Optional[Dict[str, Any]] = None


class JobUpdateRequest(BaseModel):
    """Request to update job properties"""
    priority: Optional[JobPriority] = None
    configuration: Optional[JobConfiguration] = None
    job_parameters: Optional[Dict[str, Any]] = None


class JobActionRequest(BaseModel):
    """Request to perform action on job"""
    action: str = Field(..., description="Action: cancel, pause, resume, retry")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for the action")
    
    @validator('action')
    def validate_action(cls, v):
        if v not in ['cancel', 'pause', 'resume', 'retry']:
            raise ValueError('action must be cancel, pause, resume, or retry')
        return v


class JobAnalyticsRequest(BaseModel):
    """Request for job analytics"""
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    job_type: Optional[JobType] = None
    group_by: str = Field(default="day", description="Grouping: hour, day, week, month")
    
    @validator('group_by')
    def validate_group_by(cls, v):
        if v not in ['hour', 'day', 'week', 'month']:
            raise ValueError('group_by must be hour, day, week, or month')
        return v


class JobAnalyticsResponse(BaseModel):
    """Job analytics and statistics"""
    total_jobs: int
    jobs_by_status: Dict[str, int]
    jobs_by_type: Dict[str, int]
    jobs_by_priority: Dict[str, int]
    
    # Time series data
    job_trends: List[Dict[str, Any]] = Field(description="Jobs created over time")
    completion_trends: List[Dict[str, Any]] = Field(description="Jobs completed over time")
    
    # Performance metrics
    average_execution_time: Dict[str, float] = Field(description="Average execution time by job type")
    success_rates: Dict[str, float] = Field(description="Success rates by job type")
    error_rates: Dict[str, float] = Field(description="Error rates by job type")
    
    # Queue health
    queue_depth: int = Field(description="Current number of queued jobs")
    average_queue_time_minutes: Optional[float] = None
    processing_capacity_utilization: float = Field(..., ge=0.0, le=1.0)
    
    # Resource usage
    peak_concurrent_jobs: int
    average_concurrent_jobs: float
    total_processing_time_hours: float
    
    # Common issues
    frequent_errors: List[Dict[str, Any]] = []
    performance_bottlenecks: List[str] = []


class JobBulkOperation(BaseModel):
    """Bulk operations on jobs"""
    job_ids: List[str] = Field(..., min_items=1, max_items=50)
    operation: str = Field(..., description="Operation: cancel, pause, resume, retry, delete")
    parameters: Optional[Dict[str, Any]] = None
    
    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['cancel', 'pause', 'resume', 'retry', 'delete', 'prioritize']:
            raise ValueError('operation must be cancel, pause, resume, retry, delete, or prioritize')
        return v


class JobBulkOperationResult(BaseModel):
    """Result of bulk job operation"""
    successful_operations: List[str] = []
    failed_operations: List[Dict[str, str]] = []  # job_id -> error_message
    total_requested: int
    total_successful: int
    total_failed: int
    operation_performed: str
    completed_at: datetime


class JobQueue(BaseModel):
    """Job queue status and information"""
    queue_name: str
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    failed_jobs: int
    completed_jobs: int
    
    # Queue health
    is_healthy: bool
    average_wait_time_minutes: Optional[float] = None
    processing_rate_per_hour: Optional[float] = None
    oldest_queued_job: Optional[datetime] = None
    
    # Capacity
    max_concurrent_jobs: int
    current_concurrent_jobs: int
    available_capacity: int


class JobSchedule(BaseModel):
    """Scheduled job configuration"""
    schedule_id: str
    job_type: JobType
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    job_parameters: Dict[str, Any] = Field(default={})
    configuration: Optional[JobConfiguration] = None
    is_active: bool = Field(default=True)
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    run_count: int = Field(default=0)
    failure_count: int = Field(default=0)