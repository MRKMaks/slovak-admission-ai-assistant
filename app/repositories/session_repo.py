from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.message import Message
from app.models.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # Session CRUD
    async def create(self, template_filename: str | None = None) -> Session:
        session = Session(
            template_filename=template_filename,
            status="active",
            form_data={},
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        stmt = (
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.messages))
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def update_form_data(
        self,
        session_id: uuid.UUID,
        form_data: dict[str, Any],
        status: str = "active",
    ) -> Session | None:
        session = await self.get_by_id(session_id)
        if session is None:
            return None
        session.form_data = form_data
        session.status = status
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def set_status(self, session_id: uuid.UUID, status: str) -> Session | None:
        session = await self.get_by_id(session_id)
        if session is None:
            return None
        session.status = status
        await self._db.commit()
        await self._db.refresh(session)
        return session

    # Message CRUD
    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
        )
        self._db.add(message)
        await self._db.commit()
        await self._db.refresh(message)
        return message

    async def get_messages(self, session_id: uuid.UUID) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        result = await self._db.execute(stmt)
        return result.scalars().all()
