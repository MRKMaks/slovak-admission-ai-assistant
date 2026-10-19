"""
Dependency Injection providers for FastAPI Depends().
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.session_repo import SessionRepository
from app.services.document_service import DocumentService
from app.services.form_service import FormService
from app.services.llm_service import LLMService

# Singleton-like singletons (created once per application lifetime)

def get_llm_service() -> LLMService:
    """LLMService provider (stateless — can be shared)."""
    return LLMService()


def get_document_service() -> DocumentService:
    """DocumentService provider."""
    return DocumentService()



# Per-request dependencies

def get_session_repo(
    db: AsyncSession = Depends(get_db),
) -> SessionRepository:
    return SessionRepository(db)


def get_form_service(
    repo: SessionRepository = Depends(get_session_repo),
    llm: LLMService = Depends(get_llm_service),
) -> FormService:
    return FormService(repo=repo, llm=llm)
