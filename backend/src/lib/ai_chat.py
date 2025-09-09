"""
AI Chat library with LlamaIndex integration for EDI data analysis
Provides conversational AI capabilities for querying and analyzing EDI files
"""
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator, Any, Union
from pathlib import Path
import json
import uuid

# LlamaIndex imports (will be installed when needed)
try:
    from llama_index.core import VectorStoreIndex, Document, ServiceContext, Settings
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.core.storage.storage_context import StorageContext
    from llama_index.core.memory import ChatMemoryBuffer
    from llama_index.core.chat_engine import CondensePlusContextChatEngine
    from llama_index.core.retrievers import VectorIndexRetriever
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.postprocessor import SimilarityPostprocessor
    from llama_index.core.response.schema import StreamingResponse
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    # Fallback for POC - will use mock responses
    LLAMA_INDEX_AVAILABLE = False
    logging.warning("LlamaIndex not available - using mock AI responses")

# OpenAI imports (for embedding and LLM)
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available - using mock AI responses")

import pandas as pd
from io import StringIO

logger = logging.getLogger(__name__)


class AIChat:
    """Main AI Chat class for EDI data analysis"""
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 model_name: str = "gpt-3.5-turbo",
                 embedding_model: str = "text-embedding-ada-002",
                 chunk_size: int = 512,
                 chunk_overlap: int = 50):
        """
        Initialize AI Chat with configuration
        
        Args:
            openai_api_key: OpenAI API key (if None, will use mock responses)
            model_name: LLM model to use
            embedding_model: Embedding model for vector search
            chunk_size: Document chunk size for indexing
            chunk_overlap: Overlap between chunks
        """
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Runtime flags
        self.use_mock = not (LLAMA_INDEX_AVAILABLE and OPENAI_AVAILABLE and openai_api_key)
        
        # Storage for indexed files
        self.indexed_files: Dict[str, Any] = {}
        self.conversations: Dict[str, Any] = {}
        
        # Initialize OpenAI client if available
        if OPENAI_AVAILABLE and openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        else:
            self.openai_client = None
        
        # Configure LlamaIndex if available
        if LLAMA_INDEX_AVAILABLE and not self.use_mock:
            self._configure_llama_index()
        
        logger.info(f"AIChat initialized (mock_mode: {self.use_mock})")
    
    def _configure_llama_index(self):
        """Configure LlamaIndex settings"""
        try:
            # This would set up the service context with OpenAI
            # Settings.llm = OpenAI(model=self.model_name, api_key=self.openai_api_key)
            # Settings.embed_model = OpenAIEmbedding(model=self.embedding_model, api_key=self.openai_api_key)
            
            # Set up node parser
            self.node_parser = SimpleNodeParser.from_defaults(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            
            logger.info("LlamaIndex configured successfully")
        except Exception as e:
            logger.warning(f"Failed to configure LlamaIndex: {e}")
            self.use_mock = True
    
    async def index_file_data(self, 
                              file_id: str,
                              parsed_data: pd.DataFrame,
                              field_definitions: Dict[str, Any],
                              file_metadata: Dict[str, Any],
                              **kwargs) -> Dict[str, Any]:
        """
        Index parsed file data for AI chat queries
        
        Args:
            file_id: Unique file identifier
            parsed_data: Parsed DataFrame
            field_definitions: Field definition metadata
            file_metadata: File metadata
            **kwargs: Additional indexing parameters
        
        Returns:
            Indexing result with status and metadata
        """
        try:
            logger.info(f"Starting indexing for file {file_id}")
            start_time = datetime.now()
            
            if self.use_mock:
                return await self._mock_index_file(file_id, parsed_data, field_definitions, file_metadata)
            
            # Create documents from the data
            documents = self._create_documents_from_data(parsed_data, field_definitions, file_metadata)
            
            # Build vector index
            index = VectorStoreIndex.from_documents(
                documents,
                node_parser=self.node_parser,
                show_progress=True
            )
            
            # Store the index and metadata
            self.indexed_files[file_id] = {
                'index': index,
                'parsed_data': parsed_data,
                'field_definitions': field_definitions,
                'file_metadata': file_metadata,
                'indexed_at': datetime.now(),
                'document_count': len(documents),
                'chunk_count': len(index.docstore.docs)
            }
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Successfully indexed file {file_id} in {processing_time:.2f}s")
            
            return {
                'success': True,
                'file_id': file_id,
                'document_count': len(documents),
                'chunk_count': len(index.docstore.docs),
                'processing_time_seconds': processing_time,
                'indexed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to index file {file_id}: {str(e)}")
            return {
                'success': False,
                'file_id': file_id,
                'error': str(e)
            }
    
    def _create_documents_from_data(self, 
                                    parsed_data: pd.DataFrame,
                                    field_definitions: Dict[str, Any],
                                    file_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create LlamaIndex documents from parsed data"""
        documents = []
        
        # Create a summary document with metadata
        summary_content = self._create_data_summary(parsed_data, field_definitions, file_metadata)
        summary_doc = {
            'text': summary_content,
            'metadata': {
                'document_type': 'summary',
                'file_id': file_metadata.get('file_id', 'unknown'),
                'record_count': len(parsed_data)
            }
        }
        documents.append(summary_doc)
        
        # Create field definition documents
        for field_name, field_def in field_definitions.items():
            field_content = self._create_field_description(field_name, field_def, parsed_data)
            field_doc = {
                'text': field_content,
                'metadata': {
                    'document_type': 'field_definition',
                    'field_name': field_name,
                    'data_type': field_def.get('data_type', 'unknown')
                }
            }
            documents.append(field_doc)
        
        # Create sample data documents (chunk the data)
        chunk_size = 100  # Records per chunk
        total_records = len(parsed_data)
        
        for start_idx in range(0, total_records, chunk_size):
            end_idx = min(start_idx + chunk_size, total_records)
            chunk_data = parsed_data.iloc[start_idx:end_idx]
            
            chunk_content = self._create_data_chunk_content(chunk_data, start_idx)
            chunk_doc = {
                'text': chunk_content,
                'metadata': {
                    'document_type': 'data_chunk',
                    'start_record': start_idx,
                    'end_record': end_idx - 1,
                    'record_count': len(chunk_data)
                }
            }
            documents.append(chunk_doc)
        
        return documents
    
    def _create_data_summary(self, 
                             parsed_data: pd.DataFrame,
                             field_definitions: Dict[str, Any],
                             file_metadata: Dict[str, Any]) -> str:
        """Create a comprehensive summary of the data"""
        summary_parts = [
            f"Data Summary for EDI File",
            f"Total Records: {len(parsed_data)}",
            f"Total Fields: {len(parsed_data.columns)}",
            f"File Type: {file_metadata.get('file_type', 'Unknown')}",
            ""
        ]
        
        # Field overview
        summary_parts.append("Field Overview:")
        for field_name, field_def in field_definitions.items():
            data_type = field_def.get('data_type', 'unknown')
            null_pct = field_def.get('null_percentage', 0)
            summary_parts.append(f"- {field_name}: {data_type} ({100-null_pct:.1f}% complete)")
        
        summary_parts.append("")
        
        # Data statistics
        if 'statistics' in file_metadata:
            stats = file_metadata['statistics']
            if 'numeric_ranges' in stats:
                summary_parts.append("Numeric Field Ranges:")
                for field, ranges in stats['numeric_ranges'].items():
                    summary_parts.append(
                        f"- {field}: ${ranges['min_value']:.2f} to ${ranges['max_value']:.2f} "
                        f"(avg: ${ranges['mean_value']:.2f})"
                    )
        
        return "\n".join(summary_parts)
    
    def _create_field_description(self, 
                                  field_name: str,
                                  field_def: Dict[str, Any],
                                  parsed_data: pd.DataFrame) -> str:
        """Create a detailed description of a field"""
        desc_parts = [
            f"Field: {field_name}",
            f"Data Type: {field_def.get('data_type', 'unknown')}",
            f"Standardized Name: {field_def.get('standardized_name', 'N/A')}",
            f"Completeness: {100 - field_def.get('null_percentage', 0):.1f}%",
            f"Unique Values: {field_def.get('unique_count', 0)}",
            ""
        ]
        
        # Sample values
        sample_values = field_def.get('sample_values', [])
        if sample_values:
            desc_parts.append("Sample Values:")
            for value in sample_values[:5]:
                desc_parts.append(f"- {value}")
            desc_parts.append("")
        
        # Field-specific insights
        if field_name in parsed_data.columns:
            series = parsed_data[field_name].dropna()
            if len(series) > 0:
                data_type = field_def.get('data_type')
                if data_type in ['integer', 'decimal']:
                    desc_parts.extend([
                        f"Minimum: {series.min()}",
                        f"Maximum: {series.max()}",
                        f"Average: {series.mean():.2f}" if data_type == 'decimal' else f"Average: {series.mean():.0f}",
                    ])
                elif data_type == 'string':
                    value_counts = series.value_counts().head(3)
                    desc_parts.append("Most Common Values:")
                    for value, count in value_counts.items():
                        desc_parts.append(f"- {value}: {count} times")
        
        return "\n".join(desc_parts)
    
    def _create_data_chunk_content(self, chunk_data: pd.DataFrame, start_idx: int) -> str:
        """Create content for a data chunk"""
        content_parts = [
            f"Data Records {start_idx + 1} to {start_idx + len(chunk_data)}:",
            ""
        ]
        
        # Convert chunk to a readable format
        for idx, row in chunk_data.head(10).iterrows():  # Show first 10 records
            record_parts = []
            for col, value in row.items():
                if pd.notna(value):
                    record_parts.append(f"{col}: {value}")
            
            content_parts.append(f"Record {idx + 1}: " + ", ".join(record_parts))
        
        if len(chunk_data) > 10:
            content_parts.append(f"... and {len(chunk_data) - 10} more records in this chunk")
        
        return "\n".join(content_parts)
    
    async def chat_stream(self,
                          file_id: str,
                          message: str,
                          conversation_id: Optional[str] = None,
                          include_context: bool = True,
                          max_tokens: Optional[int] = None,
                          temperature: float = 0.7) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response for a query about the indexed file data
        
        Args:
            file_id: ID of the indexed file
            message: User message/query
            conversation_id: Optional conversation ID for context
            include_context: Whether to include file context
            max_tokens: Maximum tokens in response
            temperature: Response creativity (0-1)
        
        Yields:
            Stream events with response chunks
        """
        try:
            # Generate or use existing conversation ID
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # Start event
            yield {
                'type': 'start',
                'conversation_id': conversation_id,
                'timestamp': datetime.now().isoformat(),
                'file_id': file_id
            }
            
            if self.use_mock:
                async for event in self._mock_chat_stream(file_id, message, conversation_id):
                    yield event
                return
            
            # Check if file is indexed
            if file_id not in self.indexed_files:
                yield {
                    'type': 'error',
                    'error_code': 'FILE_NOT_INDEXED',
                    'error_message': f'File {file_id} is not indexed for chat',
                    'timestamp': datetime.now().isoformat()
                }
                return
            
            # Get indexed data
            file_data = self.indexed_files[file_id]
            index = file_data['index']
            
            # Create or get conversation context
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = {
                    'file_id': file_id,
                    'messages': [],
                    'created_at': datetime.now(),
                    'memory_buffer': ChatMemoryBuffer.from_defaults(token_limit=3000)
                }
            
            conversation = self.conversations[conversation_id]
            
            # Create chat engine with memory
            chat_engine = index.as_chat_engine(
                chat_mode="condense_plus_context",
                memory=conversation['memory_buffer'],
                context_template=(
                    "You are an AI assistant analyzing EDI healthcare claims data. "
                    "Use the following context information to answer questions about the data. "
                    "Be specific with numbers, dates, and statistics when available.\n"
                    "Context information:\n"
                    "{context_str}\n"
                    "Query: {query_str}\n"
                    "Answer: "
                ),
                verbose=True
            )
            
            # Stream the response
            response = await chat_engine.astream_chat(message)
            
            # Process streaming response
            response_parts = []
            async for token in response.async_response_gen():
                chunk_content = str(token)
                response_parts.append(chunk_content)
                
                yield {
                    'type': 'chunk',
                    'content': chunk_content,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Store conversation
            full_response = ''.join(response_parts)
            conversation['messages'].extend([
                {'role': 'user', 'content': message, 'timestamp': datetime.now()},
                {'role': 'assistant', 'content': full_response, 'timestamp': datetime.now()}
            ])
            
            # End event with metadata
            yield {
                'type': 'end',
                'total_tokens': len(full_response.split()),  # Rough estimate
                'response_time_ms': 2000,  # Placeholder
                'sources_used': ['indexed_data'],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Chat stream error: {str(e)}")
            yield {
                'type': 'error',
                'error_code': 'CHAT_ERROR',
                'error_message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _mock_chat_stream(self, file_id: str, message: str, conversation_id: str):
        """Mock chat streaming for development/testing"""
        # Simulate processing delay
        await asyncio.sleep(0.5)
        
        # Generate mock response based on message content
        if 'how many' in message.lower() and ('claim' in message.lower() or 'record' in message.lower()):
            response = "Based on the analysis of your EDI file, I found approximately 1,247 claims records. This includes both processed and pending claims with dates ranging from January 2024 to March 2024."
        elif 'total' in message.lower() and 'amount' in message.lower():
            response = "The total claim amount across all records in your file is $2,847,392.45. This breaks down to an average of $2,284.12 per claim, with amounts ranging from $15.50 to $45,678.90."
        elif 'status' in message.lower() or 'approved' in message.lower():
            response = "Looking at the claim status distribution: 856 claims (68.7%) are approved, 234 claims (18.8%) are pending review, 98 claims (7.9%) are rejected, and 59 claims (4.7%) require additional information."
        elif 'diagnosis' in message.lower() or 'code' in message.lower():
            response = "The most common diagnosis codes in your data are: Z51.11 (chemotherapy sessions) appearing in 145 claims, E11.9 (diabetes type 2) in 89 claims, I10 (hypertension) in 67 claims, and F32.1 (major depression) in 45 claims."
        elif 'provider' in message.lower():
            response = "There are 234 unique healthcare providers in your dataset. The top 5 providers by claim volume are: MedCenter Plus (127 claims), Regional Health Network (89 claims), City Medical Group (78 claims), Specialty Care Associates (56 claims), and Primary Health Solutions (43 claims)."
        else:
            response = f"I understand you're asking about: '{message}'. Based on your EDI claims data, I can help analyze various aspects like claim counts, financial totals, provider statistics, diagnosis patterns, and processing status. Could you be more specific about what information you'd like me to analyze?"
        
        # Stream the response word by word
        words = response.split()
        for i, word in enumerate(words):
            await asyncio.sleep(0.1)  # Simulate streaming delay
            content = word + (" " if i < len(words) - 1 else "")
            yield {
                'type': 'chunk',
                'content': content,
                'timestamp': datetime.now().isoformat()
            }
        
        # End event
        yield {
            'type': 'end',
            'total_tokens': len(words),
            'response_time_ms': len(words) * 100,
            'context_tokens': 150,
            'completion_tokens': len(words),
            'timestamp': datetime.now().isoformat()
        }
    
    async def _mock_index_file(self, file_id: str, parsed_data: pd.DataFrame, 
                               field_definitions: Dict[str, Any], file_metadata: Dict[str, Any]):
        """Mock file indexing for development"""
        await asyncio.sleep(2)  # Simulate indexing time
        
        # Store mock indexed data
        self.indexed_files[file_id] = {
            'parsed_data': parsed_data,
            'field_definitions': field_definitions,
            'file_metadata': file_metadata,
            'indexed_at': datetime.now(),
            'document_count': len(parsed_data) // 100 + 2,  # Chunks + metadata docs
            'chunk_count': len(parsed_data) // 50 + 5
        }
        
        return {
            'success': True,
            'file_id': file_id,
            'document_count': self.indexed_files[file_id]['document_count'],
            'chunk_count': self.indexed_files[file_id]['chunk_count'],
            'processing_time_seconds': 2.0,
            'indexed_at': datetime.now().isoformat()
        }
    
    def is_file_indexed(self, file_id: str) -> bool:
        """Check if a file is indexed for chat"""
        return file_id in self.indexed_files
    
    def get_conversation_history(self, conversation_id: str) -> Optional[List[Dict[str, Any]]]:
        """Get conversation message history"""
        if conversation_id in self.conversations:
            return self.conversations[conversation_id]['messages']
        return None
    
    def get_indexed_files_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all indexed files"""
        info = {}
        for file_id, data in self.indexed_files.items():
            info[file_id] = {
                'indexed_at': data['indexed_at'].isoformat(),
                'document_count': data.get('document_count', 0),
                'chunk_count': data.get('chunk_count', 0),
                'record_count': len(data['parsed_data']) if 'parsed_data' in data else 0
            }
        return info
    
    async def clear_file_index(self, file_id: str) -> bool:
        """Clear index for a specific file"""
        if file_id in self.indexed_files:
            del self.indexed_files[file_id]
            
            # Also clear related conversations
            conversations_to_remove = [
                conv_id for conv_id, conv_data in self.conversations.items()
                if conv_data.get('file_id') == file_id
            ]
            
            for conv_id in conversations_to_remove:
                del self.conversations[conv_id]
            
            logger.info(f"Cleared index and conversations for file {file_id}")
            return True
        
        return False
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            'indexed_files_count': len(self.indexed_files),
            'active_conversations_count': len(self.conversations),
            'mock_mode': self.use_mock,
            'llama_index_available': LLAMA_INDEX_AVAILABLE,
            'openai_available': OPENAI_AVAILABLE,
            'model_name': self.model_name,
            'embedding_model': self.embedding_model
        }


# Global AI Chat instance (will be configured by the application)
ai_chat_instance: Optional[AIChat] = None


def initialize_ai_chat(openai_api_key: Optional[str] = None, **kwargs) -> AIChat:
    """Initialize global AI Chat instance"""
    global ai_chat_instance
    ai_chat_instance = AIChat(openai_api_key=openai_api_key, **kwargs)
    return ai_chat_instance


def get_ai_chat() -> AIChat:
    """Get global AI Chat instance"""
    global ai_chat_instance
    if ai_chat_instance is None:
        # Initialize with mock mode
        ai_chat_instance = AIChat()
    return ai_chat_instance


async def quick_analyze_data(parsed_data: pd.DataFrame, 
                             field_definitions: Dict[str, Any],
                             query: str) -> str:
    """
    Quick analysis function for immediate insights without full indexing
    Useful for simple statistical queries
    """
    try:
        # Basic statistical analysis based on query
        if 'count' in query.lower() or 'how many' in query.lower():
            return f"The dataset contains {len(parsed_data)} records with {len(parsed_data.columns)} fields."
        
        elif 'total' in query.lower() and 'amount' in query.lower():
            amount_fields = [col for col, def_ in field_definitions.items() 
                           if def_.get('data_type') == 'decimal' and 'amount' in col.lower()]
            
            if amount_fields:
                field = amount_fields[0]
                if field in parsed_data.columns:
                    total = parsed_data[field].sum()
                    return f"Total amount in {field}: ${total:,.2f}"
            
            return "No amount fields found in the dataset."
        
        elif 'field' in query.lower() or 'column' in query.lower():
            fields_info = []
            for field, definition in field_definitions.items():
                data_type = definition.get('data_type', 'unknown')
                completeness = 100 - definition.get('null_percentage', 0)
                fields_info.append(f"{field} ({data_type}, {completeness:.1f}% complete)")
            
            return f"Fields in dataset:\n" + "\n".join(fields_info[:10])
        
        else:
            # Generic summary
            numeric_fields = sum(1 for def_ in field_definitions.values() 
                               if def_.get('data_type') in ['integer', 'decimal'])
            date_fields = sum(1 for def_ in field_definitions.values() 
                            if def_.get('data_type') == 'date')
            
            return (f"Dataset summary: {len(parsed_data)} records, {len(parsed_data.columns)} fields "
                   f"({numeric_fields} numeric, {date_fields} date fields)")
    
    except Exception as e:
        return f"Analysis error: {str(e)}"