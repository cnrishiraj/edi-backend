"""
Conversation model for AI chat sessions
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class ConversationStatus(str, Enum):
    """Conversation status enumeration"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationCreateRequest(BaseModel):
    """Request to create a new conversation"""
    file_id: str
    title: Optional[str] = Field(None, max_length=255, description="Optional conversation title")
    initial_message: Optional[str] = Field(None, description="Initial user message")
    
    @validator('file_id')
    def validate_file_id(cls, v):
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v


class ConversationUpdateRequest(BaseModel):
    """Request to update conversation metadata"""
    title: Optional[str] = Field(None, max_length=255)
    status: Optional[ConversationStatus] = None
    notes: Optional[str] = None


class ConversationSummary(BaseModel):
    """Summary of conversation topics and insights"""
    key_topics: List[str] = Field(default=[], description="Main topics discussed")
    insights_generated: List[str] = Field(default=[], description="Key insights from the conversation")
    data_points_mentioned: List[str] = Field(default=[], description="Specific data points referenced")
    questions_asked: int = Field(default=0, description="Number of user questions")
    ai_responses: int = Field(default=0, description="Number of AI responses")
    conversation_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class ConversationMetrics(BaseModel):
    """Conversation performance metrics"""
    total_messages: int = Field(default=0)
    user_messages: int = Field(default=0)
    assistant_messages: int = Field(default=0)
    system_messages: int = Field(default=0)
    average_response_time_ms: Optional[float] = None
    total_tokens_used: Optional[int] = None
    context_tokens_used: Optional[int] = None
    completion_tokens_used: Optional[int] = None
    conversation_duration_minutes: Optional[float] = None
    user_satisfaction_score: Optional[float] = Field(None, ge=0.0, le=5.0)


class ConversationResponse(BaseModel):
    """Response model for conversation operations"""
    conversation_id: str
    file_id: str
    title: Optional[str] = None
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    message_count: int = Field(default=0, ge=0)
    last_message_at: Optional[datetime] = None
    summary: Optional[ConversationSummary] = None
    metrics: Optional[ConversationMetrics] = None
    tags: List[str] = Field(default=[], description="User-defined tags")
    is_favorite: bool = Field(default=False)
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response for listing conversations"""
    conversations: List[ConversationResponse]
    total_count: int
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    has_more: bool
    filters_applied: Optional[Dict[str, Any]] = None


class ConversationDetailResponse(BaseModel):
    """Detailed conversation response with messages"""
    conversation_id: str
    file_id: str
    title: Optional[str] = None
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    
    # Message history (basic info - detailed messages from separate endpoint)
    message_count: int = Field(default=0)
    last_message_preview: Optional[str] = Field(None, max_length=200)
    last_message_at: Optional[datetime] = None
    
    # Enhanced metadata
    summary: Optional[ConversationSummary] = None
    metrics: Optional[ConversationMetrics] = None
    tags: List[str] = Field(default=[])
    is_favorite: bool = Field(default=False)
    notes: Optional[str] = None
    
    # File context
    file_name: Optional[str] = None
    file_status: Optional[str] = None
    
    # Related conversations
    related_conversation_ids: List[str] = Field(default=[])
    
    # Export capabilities
    can_export: bool = Field(default=True)
    export_formats: List[str] = Field(default=["json", "txt", "pdf"])
    
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class ConversationSearchRequest(BaseModel):
    """Request for conversation search"""
    query: str = Field(..., min_length=1, max_length=500)
    file_id: Optional[str] = None
    status: Optional[ConversationStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None
    include_message_content: bool = Field(default=False)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)


class ConversationSearchResult(BaseModel):
    """Single conversation search result"""
    conversation_id: str
    file_id: str
    title: Optional[str] = None
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    matching_snippet: str = Field(..., description="Highlighted matching text")
    message_matches: int = Field(default=0, description="Number of matching messages")
    created_at: datetime
    last_message_at: Optional[datetime] = None


class ConversationSearchResponse(BaseModel):
    """Response for conversation search"""
    results: List[ConversationSearchResult]
    total_matches: int
    query: str
    search_time_ms: int
    page: int
    page_size: int
    has_more: bool


class ConversationExportRequest(BaseModel):
    """Request to export conversation"""
    conversation_id: str
    export_format: str = Field(default="json", description="Export format: json, txt, pdf, docx")
    include_metadata: bool = Field(default=True)
    include_system_messages: bool = Field(default=False)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    @validator('export_format')
    def validate_format(cls, v):
        if v not in ['json', 'txt', 'pdf', 'docx']:
            raise ValueError('export_format must be json, txt, pdf, or docx')
        return v


class ConversationAnalyticsRequest(BaseModel):
    """Request for conversation analytics"""
    file_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    group_by: str = Field(default="day", description="Grouping: hour, day, week, month")
    
    @validator('group_by')
    def validate_group_by(cls, v):
        if v not in ['hour', 'day', 'week', 'month']:
            raise ValueError('group_by must be hour, day, week, or month')
        return v


class ConversationAnalyticsResponse(BaseModel):
    """Analytics data for conversations"""
    total_conversations: int
    active_conversations: int
    archived_conversations: int
    deleted_conversations: int
    
    # Time series data
    conversation_trends: List[Dict[str, Any]] = Field(description="Time-based conversation counts")
    message_trends: List[Dict[str, Any]] = Field(description="Time-based message counts")
    
    # Usage patterns
    most_active_hours: List[int] = Field(description="Hours with most activity (0-23)")
    most_active_days: List[str] = Field(description="Days with most activity")
    average_conversation_length: float = Field(description="Average messages per conversation")
    average_response_time_seconds: Optional[float] = None
    
    # Popular topics and queries
    top_topics: List[Dict[str, Any]] = Field(default=[], description="Most discussed topics")
    common_question_patterns: List[str] = Field(default=[])
    
    # Performance metrics
    user_satisfaction_average: Optional[float] = Field(None, ge=0.0, le=5.0)
    successful_completion_rate: Optional[float] = Field(None, ge=0.0, le=1.0)


class ConversationBulkOperation(BaseModel):
    """Bulk operations on conversations"""
    conversation_ids: List[str] = Field(..., min_items=1, max_items=50)
    operation: str = Field(..., description="Operation: archive, delete, tag, untag")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Operation-specific parameters")
    
    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['archive', 'delete', 'tag', 'untag', 'favorite', 'unfavorite']:
            raise ValueError('operation must be archive, delete, tag, untag, favorite, or unfavorite')
        return v


class ConversationBulkOperationResult(BaseModel):
    """Result of bulk conversation operation"""
    successful_operations: List[str] = []
    failed_operations: List[Dict[str, str]] = []  # conversation_id -> error_message
    total_requested: int
    total_successful: int
    total_failed: int
    operation_performed: str
    completed_at: datetime


class ConversationTemplate(BaseModel):
    """Template for common conversation starters"""
    template_id: str
    name: str = Field(..., description="Template name")
    description: str = Field(..., description="Template description")
    category: str = Field(..., description="Template category")
    prompt_template: str = Field(..., description="Prompt template with placeholders")
    placeholders: List[str] = Field(default=[], description="Available placeholder variables")
    usage_count: int = Field(default=0, description="Number of times used")
    is_active: bool = Field(default=True)


class ConversationTemplateResponse(BaseModel):
    """Response for conversation templates"""
    templates: List[ConversationTemplate]
    categories: List[str] = Field(description="Available template categories")
    total_count: int