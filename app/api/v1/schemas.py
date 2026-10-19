"""
Pydantic schemas for API requests/responses for sessions.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateSessionResponse(BaseModel):
    session_id: uuid.UUID
    status: str = "active"


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User message text")


class MessageResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    status: Literal["in_progress", "completed"]
    form_data: dict[str, Any] = Field(default_factory=dict)


class SessionStatusResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    form_data: dict[str, Any] = Field(default_factory=dict)
