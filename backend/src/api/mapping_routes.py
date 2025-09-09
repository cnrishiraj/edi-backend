from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any

from ..database import get_db
from ..services.mapping_service import get_mapping_service
from ..models.mapping import (
    MappingResponse,
    MappingGenerateRequest,
    ValidationResults,
    MappingBulkOperation,
    MappingStatus
)

router = APIRouter(prefix="/mappings", tags=["mappings"])

@router.post("/generate", response_model=MappingResponse)
async def generate_mapping(
    request: MappingGenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate field mappings for a processed file using AI and fuzzy matching
    
    - **file_id**: UUID of the processed file
    - **target_schema**: Target schema name (e.g., 'VBA', 'Custom')
    - **mapping_name**: Optional custom name for the mapping
    - **user_id**: Optional user ID for ownership
    - **confidence_threshold**: Minimum confidence for auto-mapping (0.0-1.0)
    - **include_suggestions**: Whether to include low-confidence suggestions
    - **custom_rules**: Optional custom mapping rules
    
    Returns the created mapping record and starts background generation
    """
    try:
        mapping_service = get_mapping_service()
        
        # Validate file exists and is processed
        from ..services.file_service import get_file_service
        file_service = get_file_service()
        file_result = await file_service.get_file_data(request.file_id)
        
        if not file_result['success']:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        file_record = file_result['data']
        
        # Create mapping record
        mapping_data = {
            "file_id": request.file_id,
            "target_schema": request.target_schema,
            "mapping_name": getattr(request, 'mapping_name', None) or f"Mapping for {file_record['filename']}",
            "user_id": getattr(request, 'user_id', None),
            "mapping_status": MappingStatus.GENERATING,
            "confidence_threshold": getattr(request, 'confidence_threshold', 0.8),
            "custom_rules": getattr(request, 'custom_rules', {})
        }
        
        created_mapping = await mapping_service.create_mapping(mapping_data)
        
        # Start background mapping generation
        background_tasks.add_task(
            mapping_service.generate_mapping_async,
            created_mapping.id,
            getattr(request, 'confidence_threshold', 0.8),
            getattr(request, 'include_suggestions', True),
            getattr(request, 'custom_rules', {})
        )
        
        return created_mapping
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Mapping generation failed: {str(e)}"
        )


@router.get("/{mapping_id}", response_model=MappingResponse)
async def get_mapping(
    mapping_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get mapping details including field mappings and metadata
    
    - **mapping_id**: UUID of the mapping to retrieve
    
    Returns the complete mapping record with all field mappings
    """
    try:
        mapping_service = get_mapping_service()
        mapping = await mapping_service.get_mapping(mapping_id)
        
        if not mapping:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found"
            )
        
        return mapping
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve mapping: {str(e)}"
        )


@router.get("/", response_model=List[MappingResponse])
async def list_mappings(
    skip: int = 0,
    limit: int = 50,
    file_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[MappingStatus] = None,
    target_schema: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List mappings with optional filtering
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (max 100)
    - **file_id**: Filter by source file
    - **user_id**: Filter by user ID
    - **status**: Filter by mapping status
    - **target_schema**: Filter by target schema
    
    Returns list of mapping records
    """
    try:
        if limit > 100:
            limit = 100
        
        mapping_service = get_mapping_service()
        mappings = await mapping_service.list_mappings(
            skip=skip,
            limit=limit,
            file_id=file_id,
            user_id=user_id,
            status=status,
            target_schema=target_schema
        )
        
        return mappings
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list mappings: {str(e)}"
        )


@router.post("/{mapping_id}/validate", response_model=ValidationResults)
async def validate_mapping(
    mapping_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate mapping rules and field compatibility
    
    - **mapping_id**: UUID of the mapping to validate
    - **validation_rules**: Custom validation rules to apply
    - **strict_mode**: Whether to use strict validation
    
    Returns validation results with errors and warnings
    """
    try:
        mapping_service = get_mapping_service()
        
        # Check mapping exists
        mapping = await mapping_service.get_mapping(mapping_id)
        if not mapping:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found"
            )
        
        # Validate mapping
        validation_result = await mapping_service.validate_mapping(
            mapping_id,
            request.get('validation_rules', {}),
            request.get('strict_mode', False)
        )
        
        return validation_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Mapping validation failed: {str(e)}"
        )


@router.put("/{mapping_id}", response_model=MappingResponse)
async def update_mapping(
    mapping_id: str,
    mapping_updates: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Update mapping configuration and field mappings
    
    - **mapping_id**: UUID of the mapping to update
    - **mapping_updates**: Dictionary of fields to update
    
    Returns the updated mapping record
    """
    try:
        mapping_service = get_mapping_service()
        
        # Check mapping exists
        existing_mapping = await mapping_service.get_mapping(mapping_id)
        if not existing_mapping:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found"
            )
        
        # Update mapping
        updated_mapping = await mapping_service.update_mapping(mapping_id, mapping_updates)
        
        return updated_mapping
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update mapping: {str(e)}"
        )


@router.delete("/{mapping_id}")
async def delete_mapping(
    mapping_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a mapping and all associated field mappings
    
    - **mapping_id**: UUID of the mapping to delete
    
    Returns success message
    """
    try:
        mapping_service = get_mapping_service()
        success = await mapping_service.delete_mapping(mapping_id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found"
            )
        
        return {"message": "Mapping deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete mapping: {str(e)}"
        )


@router.post("/{mapping_id}/export")
async def export_mapping(
    mapping_id: str,
    export_format: str = "json",
    db: AsyncSession = Depends(get_db)
):
    """
    Export mapping in various formats (JSON, CSV, Excel)
    
    - **mapping_id**: UUID of the mapping to export
    - **export_format**: Export format (json, csv, excel)
    
    Returns the mapping in the requested format
    """
    try:
        if export_format not in ["json", "csv", "excel"]:
            raise HTTPException(
                status_code=400,
                detail="Export format must be one of: json, csv, excel"
            )
        
        mapping_service = get_mapping_service()
        
        # Check mapping exists
        mapping = await mapping_service.get_mapping(mapping_id)
        if not mapping:
            raise HTTPException(
                status_code=404,
                detail="Mapping not found"
            )
        
        # Export mapping
        export_data = await mapping_service.export_mapping(mapping_id, export_format)
        
        return {
            "mapping_id": mapping_id,
            "format": export_format,
            "data": export_data,
            "exported_at": mapping.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export mapping: {str(e)}"
        )


@router.post("/bulk")
async def bulk_mapping_operations(
    request: MappingBulkOperation,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Perform bulk operations on multiple mappings
    
    - **operation**: Type of bulk operation (generate, validate, delete, export)
    - **mapping_ids**: List of mapping IDs to operate on
    - **file_ids**: Alternative: list of file IDs to generate mappings for
    - **parameters**: Operation-specific parameters
    
    Returns bulk operation status and starts background processing
    """
    try:
        mapping_service = get_mapping_service()
        
        # Start bulk operation in background
        background_tasks.add_task(
            mapping_service.bulk_operations_async,
            getattr(request, 'operation', 'generate'),
            getattr(request, 'mapping_ids', []),
            getattr(request, 'file_ids', []),
            getattr(request, 'parameters', {})
        )
        
        total_items = len(getattr(request, 'mapping_ids', []) or getattr(request, 'file_ids', []) or [])
        operation = getattr(request, 'operation', 'generate')
        
        return {
            "operation": operation,
            "total_items": total_items,
            "status": "processing",
            "message": f"Bulk {operation} operation started",
            "estimated_time_minutes": total_items * 0.5
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Bulk operation failed: {str(e)}"
        )