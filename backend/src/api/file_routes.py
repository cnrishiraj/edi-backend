from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid
import os
from datetime import datetime
from io import BytesIO

from ..database import get_db
from ..services.file_service import get_file_service
from ..models.file import FileResponse, FileStatus, FileType

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(default=None),
    companion_docs: Optional[UploadFile] = File(None)
):
    """
    Upload and process a file with optional companion documentation
    
    - **file**: The file to upload (multipart/form-data) 
    - **project_id**: Optional project ID for file ownership
    - **companion_docs**: Optional Excel file with field definitions and mappings
    
    Returns the created file record with processing started in background
    """
    try:
        # Validate file type
        allowed_extensions = ['.csv', '.txt', '.xlsx', '.xls']
        file_extension = os.path.splitext(file.filename or "")[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )
        
        # Process companion docs if provided
        companion_docs_content = None
        if companion_docs:
            companion_content = await companion_docs.read()
            companion_docs_content = BytesIO(companion_content)
        
        # Get file service
        file_service = get_file_service()
        
        # Upload file using service
        result = await file_service.upload_file(
            file_content=BytesIO(file_content),
            filename=file.filename or f"upload_{uuid.uuid4().hex[:8]}{file_extension}",
            file_type=FileType.SMITHRX_CLAIMS,  # Default to SmithRx claims
            project_id=project_id or str(uuid.uuid4()),
            excel_definitions=companion_docs_content
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=400,
                detail=result.get('error', 'Upload failed')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/{file_id}/status")
async def get_file_status(file_id: str):
    """
    Get file processing status and metadata
    
    - **file_id**: UUID of the file to check
    
    Returns the current file record with processing status
    """
    try:
        file_service = get_file_service()
        result = await file_service.get_file_status(file_id)
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to get file status')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve file status: {str(e)}"
        )


@router.get("/")
async def list_files(
    skip: int = 0,
    limit: int = 20,
    project_id: Optional[str] = None,
    status: Optional[FileStatus] = None
):
    """
    List files with optional filtering
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return (max 100)
    - **project_id**: Filter by project ID
    - **status**: Filter by processing status
    
    Returns list of file records
    """
    try:
        if limit > 100:
            limit = 100
        
        page = (skip // limit) + 1 if limit > 0 else 1
        
        file_service = get_file_service()
        result = await file_service.list_files(
            project_id=project_id,
            status=status,
            page=page,
            page_size=limit
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to list files')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """
    Delete a file and its associated data
    
    - **file_id**: UUID of the file to delete
    
    Returns success message
    """
    try:
        file_service = get_file_service()
        result = await file_service.delete_file(file_id)
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to delete file')
            )
        
        return {"message": result.get('message', 'File deleted successfully')}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/{file_id}/data")
async def get_file_data(file_id: str):
    """
    Get parsed file data and metadata
    
    - **file_id**: UUID of the file
    
    Returns the parsed file data and metadata
    """
    try:
        file_service = get_file_service()
        result = await file_service.get_file_data(file_id)
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to get file data')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file data: {str(e)}"
        )


@router.get("/{file_id}/chat-data")
async def get_file_for_chat(file_id: str):
    """
    Get file data optimized for chat/AI processing
    
    - **file_id**: UUID of the file
    
    Returns file data with chat context
    """
    try:
        file_service = get_file_service()
        result = await file_service.get_file_for_chat(file_id)
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to get file for chat')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file for chat: {str(e)}"
        )


@router.get("/{file_id}/extract-json")
async def extract_json_data(
    file_id: str,
    include_metadata: bool = True,
    format_type: str = "structured"
):
    """
    Extract parsed file data as structured JSON
    
    - **file_id**: UUID of the file
    - **include_metadata**: Whether to include file metadata
    - **format_type**: Format type ("structured", "flat", or "raw")
    
    Returns structured JSON data with records and metadata
    """
    try:
        file_service = get_file_service()
        result = await file_service.extract_json_data(
            file_id=file_id,
            include_metadata=include_metadata,
            format_type=format_type
        )
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to extract JSON data')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract JSON data: {str(e)}"
        )


@router.get("/{file_id}/json-summary")
async def get_json_summary(file_id: str):
    """
    Get a JSON summary of the file data with analytics
    
    - **file_id**: UUID of the file
    
    Returns JSON summary with key metrics and sample data
    """
    try:
        file_service = get_file_service()
        result = await file_service.export_json_summary(file_id)
        
        if not result['success']:
            status_code = result.get('status_code', 500)
            raise HTTPException(
                status_code=status_code,
                detail=result.get('error', 'Failed to get JSON summary')
            )
        
        return result['data']
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get JSON summary: {str(e)}"
        )