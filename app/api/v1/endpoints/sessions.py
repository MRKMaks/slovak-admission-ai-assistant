"""
Sessions router
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_document_service, get_form_service
from app.api.v1.schemas import (
    CreateSessionResponse,
    MessageRequest,
    MessageResponse,
    SessionStatusResponse,
)
from app.services.document_service import DocumentService
from app.services.form_service import FormService

router = APIRouter(prefix="/sessions", tags=["sessions"])



# Сreate a new session

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=CreateSessionResponse,
    summary="Create a new form-filling session",
)
async def create_session(
    template_filename: str | None = Query(
        None, description="Optional name of the template file"
    ),
    form_service: FormService = Depends(get_form_service),
) -> CreateSessionResponse:
    """
    Creates an empty session in the DB.
    Returns session ID and its initial status `active`.
    """
    session = await form_service.repo.create(template_filename=template_filename)
    return CreateSessionResponse(session_id=session.id, status=session.status)

# Send user message

@router.post(
    "/{session_id}/messages",
    response_model=MessageResponse,
    summary="Send a user message and get AI reply",
)
async def post_message(
    session_id: uuid.UUID,
    body: MessageRequest,
    form_service: FormService = Depends(get_form_service),
) -> MessageResponse:
    try:
        result = await form_service.process_message(
            session_id=session_id,
            user_text=body.content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM Error: {str(exc)}",
        ) from exc

    return MessageResponse(
        session_id=result.session_id,
        reply=result.reply,
        status="completed" if result.is_complete else "in_progress",
        form_data=result.form_data,
    )


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
    summary="Get session status",
)
async def get_session(
    session_id: uuid.UUID,
    form_service: FormService = Depends(get_form_service),
) -> SessionStatusResponse:
    session = await form_service.repo.get_by_id(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return SessionStatusResponse(
        session_id=session.id,
        status=session.status,
        form_data=session.form_data or {},
    )


# GET /sessions/{session_id}/export   — export filled form to PDF


@router.get(
    "/{session_id}/export",
    summary="Export completed form as PDF",
    response_class=FileResponse,
)
async def export_pdf(
    session_id: uuid.UUID,
    force: bool = Query(False, description="Force export even if not completed"),
    form_service: FormService = Depends(get_form_service),
    doc_service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    session = await form_service.repo.get_by_id(session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    if session.status != "completed" and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session {session_id} is not completed yet "
                f"(current status: '{session.status}'). "
                "Keep sending messages until the form is fully filled."
            ),
        )

    context = doc_service.form_to_context(session.form_data or {})
    pdf_path: Path = await doc_service.generate_pdf(context, cleanup=True)

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"prihlaška_{session_id}.pdf",
    )
