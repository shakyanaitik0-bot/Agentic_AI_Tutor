"""
Document upload and management API endpoints.

Allows students to upload their own study materials (PDF, TXT, DOCX)
which are processed and added to their personal vector store.
"""

import logging
import os
import tempfile
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSessionType

from app.api.dependencies import get_current_student, get_db, verify_student_access
from app.models.student import Student
from app.services.document_processor import DocumentProcessor
from app.services.rag_service import get_rag_service
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload"""

    success: bool
    filename: str
    num_chunks: int
    message: str


class DocumentListResponse(BaseModel):
    """Response schema for listing documents"""

    student_id: str
    documents: List[dict]
    total_chunks: int


ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".doc", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    student_id: str = Form(...),
    subject: str = Form(None),
    current_student: Student = Depends(get_current_student),
    db: DBSessionType = Depends(get_db),
):
    """
    Upload a study material document for a student.

    Supported formats: PDF, TXT, DOCX, MD
    Max file size: 10MB

    Args:
        file: Uploaded file
        student_id: Student ID
        subject: Optional subject/topic classification
        db: Database session

    Returns:
        DocumentUploadResponse: Upload status and statistics

    Raises:
        HTTPException: 400 for invalid file, 404 if student not found
    """
    verify_student_access(student_id, current_student)
    student = current_student

    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large ({file_size / 1024 / 1024:.1f}MB). Max size: {MAX_FILE_SIZE / 1024 / 1024}MB",
        )

    logger.info(
        f"Processing document upload: {file.filename} ({file_size} bytes) for student {student.name}"
    )

    try:
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Process document
        processor = DocumentProcessor()
        chunks = processor.process_document(
            file_path=tmp_path,
            filename=file.filename,
            student_id=student_id,
            subject=subject or "General",
        )

        # Clean up temp file
        os.unlink(tmp_path)

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from document",
            )

        # Add to vector store
        from datetime import datetime

        rag_service = get_rag_service()
        rag_service.add_documents(
            chunks=chunks,
            metadata={
                "student_id": student_id,
                "filename": file.filename,
                "subject": subject or "General",
                "exam_type": student.exam_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(
            f"Added document to vector store with student_id={student_id}, filename={file.filename}"
        )

        logger.info(
            f"Successfully processed {file.filename}: {len(chunks)} chunks added to vector store"
        )

        return DocumentUploadResponse(
            success=True,
            filename=file.filename,
            num_chunks=len(chunks),
            message=f"Document processed successfully. {len(chunks)} text chunks added to your knowledge base.",
        )

    except Exception as e:
        logger.error(f"Error processing document {file.filename}: {e}", exc_info=True)
        # Clean up temp file if it exists
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}",
        )


@router.get("/list/{student_id}", response_model=DocumentListResponse)
def list_student_documents(
    student_id: str,
    current_student: Student = Depends(get_current_student),
    db: DBSessionType = Depends(get_db),
):
    """
    List all documents uploaded by the authenticated student.

    Args:
        student_id: Student ID (must be the caller's own)
        current_student: Student resolved from the access token
        db: Database session

    Returns:
        DocumentListResponse: List of documents and statistics

    Raises:
        HTTPException: 401 if unauthenticated, 403 if listing another
            student's documents
    """
    verify_student_access(student_id, current_student)

    try:
        # Query vector store for student's documents
        rag_service = get_rag_service()
        documents = rag_service.list_student_documents(student_id)

        return DocumentListResponse(
            student_id=student_id,
            documents=documents,
            total_chunks=sum(doc.get("num_chunks", 0) for doc in documents),
        )

    except Exception as e:
        logger.error(f"Error listing documents for student {student_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving documents: {str(e)}",
        )
