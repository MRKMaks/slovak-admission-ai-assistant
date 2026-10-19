import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.message import Message


class Session(Base):
    """A user dialog session with the AI assistant."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # Name of the original template file uploaded by the user
    template_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Session status: active | completed | abandoned
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    # JSON state of ApplicationForm, accumulated during the dialog
    form_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, server_default="{}")

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Session id={self.id} status={self.status}>"
