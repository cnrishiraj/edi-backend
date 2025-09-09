"""
Mapping service for managing field mapping operations
Integrates fuzzy matching engine for automatic mapping generation
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from ..database import Mapping, File, get_async_session
from ..models.mapping import (
    MappingGenerateRequest, MappingResponse, MappingDetailResponse,
    MappingStatus, TargetSchema, FieldMapping, UnmappedField,
    ValidationResults, FieldStatistics, MappingUpdateRequest
)
from ..lib.mapping_engine import generate_field_mappings, validate_mapping_quality
from .file_service import get_file_service

logger = logging.getLogger(__name__)


class MappingService:
    """Service for managing field mappings and generation"""
    
    def __init__(self):
        self.file_service = get_file_service()
        self.processing_jobs = {}  # Track async mapping generation jobs
        
    async def generate_mapping(self, 
                               file_id: str,
                               target_schema: TargetSchema,
                               confidence_threshold: float = 0.8,
                               use_excel_definitions: bool = False,
                               custom_mapping_rules: Optional[Dict[str, Any]] = None,
                               validate_with_samples: bool = True,
                               sample_size: int = 100,
                               async_processing: bool = False,
                               force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Generate field mappings for a file
        
        Args:
            file_id: File UUID to generate mappings for
            target_schema: Target schema to map to
            confidence_threshold: Minimum confidence for auto-mapping
            use_excel_definitions: Use Excel field definitions if available
            custom_mapping_rules: Custom mapping rules
            validate_with_samples: Validate with sample data
            sample_size: Number of samples for validation
            async_processing: Process asynchronously
            force_regenerate: Force regeneration if mapping exists
            
        Returns:
            Mapping generation result
        """
        try:
            logger.info(f"Generating mapping for file {file_id} with schema {target_schema}")
            
            # Check if file exists and is parsed
            file_data = await self.file_service.get_file_data(file_id)
            if not file_data['success']:
                return {
                    'success': False,
                    'error': f'File not ready: {file_data.get("error", "Unknown error")}',
                    'status_code': 404 if 'not found' in file_data.get('error', '').lower() else 400
                }
            
            # Check for existing mapping
            async with get_async_session() as session:
                existing_mapping = await session.execute(
                    select(Mapping).where(Mapping.file_id == file_id)
                )
                existing = existing_mapping.scalar_one_or_none()
                
                if existing and not force_regenerate:
                    return {
                        'success': False,
                        'error': 'Mapping already exists for this file',
                        'status_code': 409,
                        'existing_mapping_id': existing.id
                    }
                
                if existing and force_regenerate:
                    # Delete existing mapping
                    await session.delete(existing)
                    await session.commit()
            
            # Start mapping generation
            if async_processing:
                return await self._start_async_mapping_generation(
                    file_id, file_data['data'], target_schema, confidence_threshold,
                    use_excel_definitions, custom_mapping_rules, validate_with_samples, sample_size
                )
            else:
                return await self._generate_mapping_sync(
                    file_id, file_data['data'], target_schema, confidence_threshold,
                    use_excel_definitions, custom_mapping_rules, validate_with_samples, sample_size,
                    force_regenerate
                )
                
        except Exception as e:
            logger.error(f"Failed to generate mapping: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _generate_mapping_sync(self,
                                     file_id: str,
                                     file_data: Dict[str, Any],
                                     target_schema: TargetSchema,
                                     confidence_threshold: float,
                                     use_excel_definitions: bool,
                                     custom_mapping_rules: Optional[Dict[str, Any]],
                                     validate_with_samples: bool,
                                     sample_size: int,
                                     force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate mapping synchronously"""
        start_time = datetime.utcnow()
        
        try:
            # Extract field definitions from file data
            field_definitions = file_data.get('field_definitions', {})
            
            # Create mock parsed data for POC (would be actual data in production)
            mock_parsed_data = pd.DataFrame()
            
            # Generate mappings using the mapping engine
            mapping_result = generate_field_mappings(
                source_fields=field_definitions,
                parsed_data=mock_parsed_data,
                target_schema=target_schema.value,
                confidence_threshold=confidence_threshold,
                use_excel_definitions=use_excel_definitions,
                custom_rules=custom_mapping_rules
            )
            
            if not mapping_result['success']:
                return {
                    'success': False,
                    'error': f"Mapping generation failed: {mapping_result.get('error', 'Unknown error')}"
                }
            
            # Create mapping record in database
            mapping_id = str(uuid.uuid4())
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000  # Convert to ms
            
            async with get_async_session() as session:
                mapping_record = Mapping(
                    id=mapping_id,
                    file_id=file_id,
                    created_at=start_time,
                    field_mappings=mapping_result['field_mappings'],
                    confidence_score=mapping_result['overall_confidence'],
                    status=MappingStatus.COMPLETED.value
                )
                
                session.add(mapping_record)
                await session.commit()
                await session.refresh(mapping_record)
            
            # Create response
            response_data = MappingResponse(
                mapping_id=mapping_id,
                file_id=file_id,
                target_schema=target_schema,
                status=MappingStatus.COMPLETED,
                field_mappings=[FieldMapping(**fm) for fm in mapping_result['field_mappings']],
                unmapped_fields=[UnmappedField(**uf) for uf in mapping_result.get('unmapped_fields', [])],
                overall_confidence=mapping_result['overall_confidence'],
                created_at=start_time,
                validation_results=ValidationResults(**mapping_result['validation_results']) if validate_with_samples else None,
                used_excel_definitions=use_excel_definitions,
                custom_rules_applied=mapping_result.get('custom_rules_applied', 0),
                regenerated=force_regenerate,
                manual_review_required=mapping_result.get('manual_review_required', False),
                processing_time_ms=int(processing_time),
                correlation_id=str(uuid.uuid4())
            )
            
            logger.info(f"Successfully generated mapping {mapping_id} for file {file_id}")
            
            return {
                'success': True,
                'data': response_data.dict()
            }
            
        except Exception as e:
            logger.error(f"Sync mapping generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _start_async_mapping_generation(self,
                                              file_id: str,
                                              file_data: Dict[str, Any],
                                              target_schema: TargetSchema,
                                              confidence_threshold: float,
                                              use_excel_definitions: bool,
                                              custom_mapping_rules: Optional[Dict[str, Any]],
                                              validate_with_samples: bool,
                                              sample_size: int) -> Dict[str, Any]:
        """Start asynchronous mapping generation"""
        try:
            mapping_id = str(uuid.uuid4())
            job_id = str(uuid.uuid4())
            
            # Create mapping record with processing status
            async with get_async_session() as session:
                mapping_record = Mapping(
                    id=mapping_id,
                    file_id=file_id,
                    created_at=datetime.utcnow(),
                    field_mappings=[],  # Will be filled when processing completes
                    confidence_score=0.0,
                    status=MappingStatus.PROCESSING.value
                )
                
                session.add(mapping_record)
                await session.commit()
            
            # Track the async job
            self.processing_jobs[job_id] = {
                'mapping_id': mapping_id,
                'file_id': file_id,
                'status': 'processing',
                'started_at': datetime.utcnow(),
                'progress': 0
            }
            
            # Start async processing
            asyncio.create_task(
                self._process_mapping_async(
                    mapping_id, job_id, file_id, file_data, target_schema,
                    confidence_threshold, use_excel_definitions, custom_mapping_rules,
                    validate_with_samples, sample_size
                )
            )
            
            # Return async response
            estimated_completion = datetime.utcnow()  # Would calculate based on file size
            
            response_data = MappingResponse(
                mapping_id=mapping_id,
                file_id=file_id,
                target_schema=target_schema,
                status=MappingStatus.PROCESSING,
                field_mappings=[],
                unmapped_fields=[],
                overall_confidence=0.0,
                created_at=datetime.utcnow(),
                used_excel_definitions=use_excel_definitions,
                job_id=job_id,
                progress_url=f"/api/v1/jobs/{job_id}",
                estimated_completion=estimated_completion,
                correlation_id=str(uuid.uuid4())
            )
            
            return {
                'success': True,
                'data': response_data.dict(),
                'status_code': 202  # Accepted for async processing
            }
            
        except Exception as e:
            logger.error(f"Failed to start async mapping generation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _process_mapping_async(self,
                                     mapping_id: str,
                                     job_id: str,
                                     file_id: str,
                                     file_data: Dict[str, Any],
                                     target_schema: TargetSchema,
                                     confidence_threshold: float,
                                     use_excel_definitions: bool,
                                     custom_mapping_rules: Optional[Dict[str, Any]],
                                     validate_with_samples: bool,
                                     sample_size: int):
        """Process mapping generation asynchronously"""
        try:
            logger.info(f"Starting async mapping generation for job {job_id}")
            
            # Update progress
            self.processing_jobs[job_id]['progress'] = 25
            await asyncio.sleep(1)  # Simulate processing time
            
            # Generate mappings
            field_definitions = file_data.get('field_definitions', {})
            mock_parsed_data = pd.DataFrame()
            
            mapping_result = generate_field_mappings(
                source_fields=field_definitions,
                parsed_data=mock_parsed_data,
                target_schema=target_schema.value,
                confidence_threshold=confidence_threshold,
                use_excel_definitions=use_excel_definitions,
                custom_rules=custom_mapping_rules
            )
            
            self.processing_jobs[job_id]['progress'] = 75
            await asyncio.sleep(1)
            
            if mapping_result['success']:
                # Update mapping record
                async with get_async_session() as session:
                    mapping_record = await session.get(Mapping, mapping_id)
                    if mapping_record:
                        mapping_record.field_mappings = mapping_result['field_mappings']
                        mapping_record.confidence_score = mapping_result['overall_confidence']
                        mapping_record.status = MappingStatus.COMPLETED.value
                        await session.commit()
                
                # Update job status
                self.processing_jobs[job_id].update({
                    'status': 'completed',
                    'progress': 100,
                    'completed_at': datetime.utcnow(),
                    'result': mapping_result
                })
                
                logger.info(f"Async mapping generation completed for job {job_id}")
                
            else:
                # Update mapping record as failed
                async with get_async_session() as session:
                    mapping_record = await session.get(Mapping, mapping_id)
                    if mapping_record:
                        mapping_record.status = MappingStatus.FAILED.value
                        await session.commit()
                
                # Update job status
                self.processing_jobs[job_id].update({
                    'status': 'failed',
                    'completed_at': datetime.utcnow(),
                    'error': mapping_result.get('error', 'Unknown error')
                })
                
        except Exception as e:
            logger.error(f"Async mapping generation failed for job {job_id}: {str(e)}")
            
            # Update job as failed
            self.processing_jobs[job_id].update({
                'status': 'failed',
                'completed_at': datetime.utcnow(),
                'error': str(e)
            })
            
            # Update mapping record as failed
            try:
                async with get_async_session() as session:
                    mapping_record = await session.get(Mapping, mapping_id)
                    if mapping_record:
                        mapping_record.status = MappingStatus.FAILED.value
                        await session.commit()
            except:
                pass  # Ignore database errors during cleanup
    
    async def get_mapping(self, 
                          mapping_id: str,
                          include_statistics: bool = False,
                          include_preview: bool = False,
                          include_history: bool = False) -> Dict[str, Any]:
        """
        Get mapping details
        
        Args:
            mapping_id: Mapping UUID
            include_statistics: Include field statistics
            include_preview: Include transformation preview
            include_history: Include change history
            
        Returns:
            Mapping details
        """
        try:
            async with get_async_session() as session:
                mapping_record = await session.get(Mapping, mapping_id)
                
                if not mapping_record:
                    return {
                        'success': False,
                        'error': 'Mapping not found',
                        'status_code': 404
                    }
                
                # Get file information
                file_record = await session.get(File, mapping_record.file_id)
                
                # Convert field mappings to model objects
                field_mappings = [FieldMapping(**fm) for fm in mapping_record.field_mappings or []]
                
                # Create base response
                response_data = MappingDetailResponse(
                    mapping_id=mapping_record.id,
                    file_id=mapping_record.file_id,
                    target_schema=TargetSchema.VBA_STANDARD,  # Default for POC
                    status=MappingStatus(mapping_record.status),
                    field_mappings=field_mappings,
                    overall_confidence=mapping_record.confidence_score,
                    created_at=mapping_record.created_at,
                    correlation_id=str(uuid.uuid4())
                )
                
                # Add optional data
                if include_statistics:
                    response_data.field_statistics = self._calculate_field_statistics(field_mappings)
                
                if include_preview and file_record:
                    # Mock transformation preview
                    response_data.transformation_preview = {
                        'sample_records': [
                            {
                                'before': {'CLAIM_ID': 'CLM001', 'AMOUNT': '100.50'},
                                'after': {'claim_number': 'CLM001', 'claim_amount': 100.50},
                                'transformation_applied': ['field_rename', 'type_conversion']
                            }
                        ],
                        'transformation_summary': {
                            'total_transformations': len(field_mappings),
                            'data_type_conversions': 3,
                            'field_renames': len(field_mappings)
                        }
                    }
                
                if include_history:
                    # Mock change history
                    response_data.change_history = [
                        {
                            'version': 1,
                            'changed_by': 'mapping_engine',
                            'change_type': 'initial_generation',
                            'timestamp': mapping_record.created_at.isoformat(),
                            'changes': f'Generated {len(field_mappings)} field mappings'
                        }
                    ]
                
                return {
                    'success': True,
                    'data': response_data.dict()
                }
                
        except Exception as e:
            logger.error(f"Failed to get mapping: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_field_statistics(self, field_mappings: List[FieldMapping]) -> FieldStatistics:
        """Calculate field mapping statistics"""
        total_fields = len(field_mappings)
        high_confidence = sum(1 for fm in field_mappings if fm.confidence_score >= 0.9)
        medium_confidence = sum(1 for fm in field_mappings if 0.7 <= fm.confidence_score < 0.9)
        low_confidence = sum(1 for fm in field_mappings if fm.confidence_score < 0.7)
        manual_review = sum(1 for fm in field_mappings if fm.confidence_score < 0.8)
        
        return FieldStatistics(
            total_fields=total_fields,
            mapped_fields=total_fields,
            unmapped_fields=0,  # All provided mappings are mapped
            high_confidence_mappings=high_confidence,
            medium_confidence_mappings=medium_confidence,
            low_confidence_mappings=low_confidence,
            manual_review_required=manual_review
        )
    
    async def update_mapping(self, 
                             mapping_id: str,
                             field_mappings: List[Dict[str, Any]],
                             notes: Optional[str] = None,
                             status: Optional[MappingStatus] = None) -> Dict[str, Any]:
        """
        Update mapping configuration
        
        Args:
            mapping_id: Mapping UUID
            field_mappings: Updated field mappings
            notes: Optional notes
            status: Optional status update
            
        Returns:
            Update result
        """
        try:
            async with get_async_session() as session:
                mapping_record = await session.get(Mapping, mapping_id)
                
                if not mapping_record:
                    return {
                        'success': False,
                        'error': 'Mapping not found',
                        'status_code': 404
                    }
                
                # Update field mappings
                if field_mappings:
                    mapping_record.field_mappings = field_mappings
                    
                    # Recalculate overall confidence
                    confidence_scores = [fm.get('confidence_score', 0) for fm in field_mappings]
                    mapping_record.confidence_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
                
                # Update status if provided
                if status:
                    mapping_record.status = status.value
                
                await session.commit()
                
                logger.info(f"Updated mapping {mapping_id}")
                
                return {
                    'success': True,
                    'message': 'Mapping updated successfully'
                }
                
        except Exception as e:
            logger.error(f"Failed to update mapping: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def delete_mapping(self, mapping_id: str) -> Dict[str, Any]:
        """
        Delete a mapping
        
        Args:
            mapping_id: Mapping UUID
            
        Returns:
            Deletion result
        """
        try:
            async with get_async_session() as session:
                mapping_record = await session.get(Mapping, mapping_id)
                
                if not mapping_record:
                    return {
                        'success': False,
                        'error': 'Mapping not found',
                        'status_code': 404
                    }
                
                await session.delete(mapping_record)
                await session.commit()
                
                logger.info(f"Deleted mapping {mapping_id}")
                
                return {
                    'success': True,
                    'message': 'Mapping deleted successfully'
                }
                
        except Exception as e:
            logger.error(f"Failed to delete mapping: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def list_mappings(self, 
                            file_id: Optional[str] = None,
                            status: Optional[MappingStatus] = None,
                            page: int = 1,
                            page_size: int = 20) -> Dict[str, Any]:
        """
        List mappings with optional filtering
        
        Args:
            file_id: Optional file filter
            status: Optional status filter
            page: Page number
            page_size: Items per page
            
        Returns:
            List of mappings
        """
        try:
            async with get_async_session() as session:
                query = select(Mapping)
                
                if file_id:
                    query = query.where(Mapping.file_id == file_id)
                    
                if status:
                    query = query.where(Mapping.status == status.value)
                
                # Add pagination
                offset = (page - 1) * page_size
                query = query.offset(offset).limit(page_size).order_by(Mapping.created_at.desc())
                
                result = await session.execute(query)
                mappings = result.scalars().all()
                
                # Convert to response format
                mapping_responses = []
                for mapping in mappings:
                    field_mappings = [FieldMapping(**fm) for fm in mapping.field_mappings or []]
                    
                    response = MappingResponse(
                        mapping_id=mapping.id,
                        file_id=mapping.file_id,
                        target_schema=TargetSchema.VBA_STANDARD,
                        status=MappingStatus(mapping.status),
                        field_mappings=field_mappings,
                        unmapped_fields=[],
                        overall_confidence=mapping.confidence_score,
                        created_at=mapping.created_at
                    )
                    mapping_responses.append(response)
                
                return {
                    'success': True,
                    'data': {
                        'mappings': [mapping.dict() for mapping in mapping_responses],
                        'total_count': len(mapping_responses),
                        'page': page,
                        'page_size': page_size,
                        'has_more': len(mapping_responses) == page_size
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to list mappings: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get async job status"""
        if job_id not in self.processing_jobs:
            return {
                'success': False,
                'error': 'Job not found',
                'status_code': 404
            }
        
        job = self.processing_jobs[job_id]
        return {
            'success': True,
            'data': {
                'job_id': job_id,
                'mapping_id': job['mapping_id'],
                'status': job['status'],
                'progress': job['progress'],
                'started_at': job['started_at'].isoformat(),
                'completed_at': job.get('completed_at').isoformat() if job.get('completed_at') else None,
                'error': job.get('error')
            }
        }


# Global mapping service instance
_mapping_service: Optional[MappingService] = None


def get_mapping_service() -> MappingService:
    """Get global mapping service instance"""
    global _mapping_service
    if _mapping_service is None:
        _mapping_service = MappingService()
    return _mapping_service