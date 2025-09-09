"""
Chat message model for individual messages in conversations
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class MessageRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    """Message type classification"""
    QUESTION = "question"
    RESPONSE = "response"
    CLARIFICATION = "clarification"
    SUMMARY = "summary"
    ERROR = "error"
    SYSTEM_NOTIFICATION = "system_notification"


class MessageStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    STREAMING = "streaming"


class MessageSource(BaseModel):
    """Source information for message context"""
    source_type: str = Field(..., description="Type of source: file, database, api, calculation")
    source_id: str = Field(..., description="Identifier of the source")
    source_name: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    excerpt: Optional[str] = Field(None, max_length=500)
    page_number: Optional[int] = None
    line_number: Optional[int] = None


class MessageContext(BaseModel):
    """Context information used to generate response"""
    file_id: str
    relevant_records: Optional[List[Dict[str, Any]]] = None
    context_window: Optional[str] = Field(None, description="Relevant context snippet")
    sources: List[MessageSource] = Field(default=[])
    tokens_used: Optional[int] = None
    retrieval_query: Optional[str] = None
    filters_applied: Optional[Dict[str, Any]] = None


class MessageMetadata(BaseModel):
    """Extended metadata for messages"""
    response_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    context_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    
    # User interaction metadata
    user_feedback: Optional[str] = None  # thumbs_up, thumbs_down, neutral
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    was_helpful: Optional[bool] = None
    follow_up_questions: Optional[List[str]] = None
    
    # Technical metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class ChatMessageRequest(BaseModel):
    """Request to send a chat message"""
    message: str = Field(..., min_length=1, max_length=8000, description="User message content")
    conversation_id: Optional[str] = None
    file_id: str = Field(..., description="File ID for context")
    include_context: bool = Field(default=True, description="Include file context in response")
    context_filters: Optional[Dict[str, Any]] = Field(None, description="Filters for context retrieval")
    stream_response: bool = Field(default=True, description="Stream the response")
    max_tokens: Optional[int] = Field(None, ge=1, le=4000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    
    @validator('file_id')
    def validate_file_id(cls, v):
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError('file_id must be a valid UUID')
        return v
    
    @validator('conversation_id')
    def validate_conversation_id(cls, v):
        if v is not None:
            import uuid
            try:
                uuid.UUID(v)
            except ValueError:
                raise ValueError('conversation_id must be a valid UUID')
        return v


class ChatMessageResponse(BaseModel):
    """Response model for chat messages"""
    message_id: str
    conversation_id: str
    role: MessageRole
    content: str
    message_type: Optional[MessageType] = None
    status: MessageStatus
    timestamp: datetime
    context: Optional[MessageContext] = None
    metadata: Optional[MessageMetadata] = None
    parent_message_id: Optional[str] = None
    has_follow_up: bool = Field(default=False)
    correlation_id: Optional[str] = None

    class Config:
        from_attributes = True


class StreamingChatEvent(BaseModel):
    """Streaming chat event for Server-Sent Events"""
    type: str = Field(..., description="Event type: start, chunk, end, error")
    timestamp: datetime
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    
    # Start event data
    estimated_tokens: Optional[int] = None
    
    # Chunk event data
    content: Optional[str] = None
    content_index: Optional[int] = None
    
    # End event data
    total_tokens: Optional[int] = None
    response_time_ms: Optional[int] = None
    context_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    finish_reason: Optional[str] = None
    
    # Error event data
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Context information
    sources_used: Optional[List[str]] = None
    context_retrieved: Optional[bool] = None


class MessageListRequest(BaseModel):
    """Request to list messages in conversation"""
    conversation_id: str
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)
    include_metadata: bool = Field(default=False)
    include_context: bool = Field(default=False)
    message_type: Optional[MessageType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class MessageListResponse(BaseModel):
    """Response for message list"""
    messages: List[ChatMessageResponse]
    conversation_id: str
    total_count: int
    page: int
    page_size: int
    has_more: bool
    has_previous: bool


class MessageUpdateRequest(BaseModel):
    """Request to update message metadata"""
    user_feedback: Optional[str] = Field(None, description="thumbs_up, thumbs_down, neutral")
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    was_helpful: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    
    @validator('user_feedback')
    def validate_feedback(cls, v):
        if v is not None and v not in ['thumbs_up', 'thumbs_down', 'neutral']:
            raise ValueError('user_feedback must be thumbs_up, thumbs_down, or neutral')
        return v


class MessageSearchRequest(BaseModel):
    """Request to search messages"""
    query: str = Field(..., min_length=1, max_length=500)
    conversation_id: Optional[str] = None
    file_id: Optional[str] = None
    role: Optional[MessageRole] = None
    message_type: Optional[MessageType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    include_context: bool = Field(default=False)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MessageSearchResult(BaseModel):
    """Single message search result"""
    message_id: str
    conversation_id: str
    role: MessageRole
    content_snippet: str = Field(..., description="Highlighted matching snippet")
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime
    message_type: Optional[MessageType] = None
    file_id: str


class MessageSearchResponse(BaseModel):
    """Response for message search"""
    results: List[MessageSearchResult]
    total_matches: int
    query: str
    search_time_ms: int
    page: int
    page_size: int
    has_more: bool


class MessageAnalyticsRequest(BaseModel):
    """Request for message analytics"""
    conversation_id: Optional[str] = None
    file_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    group_by: str = Field(default="day", description="Grouping: hour, day, week, month")


class MessageAnalyticsResponse(BaseModel):
    """Analytics data for messages"""
    total_messages: int
    messages_by_role: Dict[str, int]
    messages_by_type: Dict[str, int]
    messages_over_time: List[Dict[str, Any]]
    
    # Performance metrics
    average_response_time_ms: Optional[float] = None
    average_tokens_per_message: Optional[float] = None
    user_satisfaction_metrics: Dict[str, Any] = {}
    
    # Usage patterns
    most_active_hours: List[int] = []
    common_question_patterns: List[str] = []
    frequent_topics: List[Dict[str, Any]] = []
    
    # Error analysis
    error_rate: float = Field(..., ge=0.0, le=1.0)
    common_errors: List[Dict[str, Any]] = []


class MessageExportRequest(BaseModel):
    """Request to export messages"""
    conversation_id: Optional[str] = None
    file_id: Optional[str] = None
    message_ids: Optional[List[str]] = None
    export_format: str = Field(default="json", description="Export format: json, csv, txt")
    include_metadata: bool = Field(default=True)
    include_context: bool = Field(default=False)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    
    @validator('export_format')
    def validate_format(cls, v):
        if v not in ['json', 'csv', 'txt']:
            raise ValueError('export_format must be json, csv, or txt')
        return v


class MessageBulkOperation(BaseModel):
    """Bulk operations on messages"""
    message_ids: List[str] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., description="Operation: delete, archive, tag, rate")
    parameters: Optional[Dict[str, Any]] = None
    
    @validator('operation')
    def validate_operation(cls, v):
        if v not in ['delete', 'archive', 'tag', 'rate', 'flag', 'unflag']:
            raise ValueError('operation must be delete, archive, tag, rate, flag, or unflag')
        return v


class MessageTemplate(BaseModel):
    """Template for common message responses"""
    template_id: str
    name: str
    category: str = Field(..., description="Template category")
    template_content: str = Field(..., description="Template content with placeholders")
    placeholders: List[str] = Field(default=[])
    use_case: str = Field(..., description="When to use this template")
    is_active: bool = Field(default=True)
    usage_count: int = Field(default=0)


class MessageFeedbackSummary(BaseModel):
    """Summary of message feedback"""
    total_rated_messages: int
    average_rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    thumbs_up_count: int = Field(default=0)
    thumbs_down_count: int = Field(default=0)
    neutral_count: int = Field(default=0)
    helpful_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    
    # Feedback trends
    feedback_over_time: List[Dict[str, Any]] = []
    improvement_suggestions: List[str] = []