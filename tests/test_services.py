"""
Unit tests for Stage 3: SessionRepository, LLMService, FormService.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.form import ApplicationForm, StudyProgramInfo



# Helpers / Fixtures


def _make_uuid() -> uuid.UUID:
    return uuid.uuid4()


def _make_session_orm(
    session_id: uuid.UUID | None = None,
    status: str = "active",
    form_data: dict | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id or _make_uuid()
    s.status = status
    s.form_data = form_data or {}
    s.template_filename = None
    s.created_at = datetime.now(timezone.utc)
    s.updated_at = datetime.now(timezone.utc)
    s.messages = []
    return s


def _make_message_orm(session_id: uuid.UUID, role: str = "user", content: str = "test") -> MagicMock:
    msg = MagicMock()
    msg.id = _make_uuid()
    msg.session_id = session_id
    msg.role = role
    msg.content = content
    msg.created_at = datetime.now(timezone.utc)
    return msg



# SessionRepository tests


class TestSessionRepository:

    @pytest.fixture
    def db(self) -> AsyncMock:
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        # execute returns a Result with scalars().first() / all()
        result_mock = MagicMock()
        session.execute = AsyncMock(return_value=result_mock)
        return session

    @pytest.fixture
    def repo(self, db: AsyncMock):
        from app.repositories.session_repo import SessionRepository
        return SessionRepository(db)

    @pytest.mark.asyncio
    async def test_create_session_returns_session(self, repo, db):
        from app.models.session import Session

        result = await repo.create(template_filename="formular.docx")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()
        added = db.add.call_args[0][0]
        assert isinstance(added, Session)
        assert added.template_filename == "formular.docx"

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo, db):
        sid = _make_uuid()
        mock_session = _make_session_orm(session_id=sid)

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = mock_session
        db.execute.return_value.scalars.return_value = scalars_mock

        result = await repo.get_by_id(sid)

        assert result is mock_session
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, db):
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        db.execute.return_value.scalars.return_value = scalars_mock

        result = await repo.get_by_id(_make_uuid())
        assert result is None

    @pytest.mark.asyncio
    async def test_add_message(self, repo, db):
        from app.models.message import Message

        sid = _make_uuid()
        result = await repo.add_message(session_id=sid, role="user", content="Ahoj")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()
        added = db.add.call_args[0][0]
        assert isinstance(added, Message)
        assert added.role == "user"
        assert added.content == "Ahoj"
        assert added.session_id == sid

    @pytest.mark.asyncio
    async def test_update_form_data_and_status(self, repo, db):
        sid = _make_uuid()
        mock_session = _make_session_orm(session_id=sid)

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = mock_session
        db.execute.return_value.scalars.return_value = scalars_mock

        new_data = {"personal_info": {"first_name": "Jana"}}
        result = await repo.update_form_data(sid, new_data, status="completed")

        assert mock_session.form_data == new_data
        assert mock_session.status == "completed"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_form_data_session_not_found(self, repo, db):
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        db.execute.return_value.scalars.return_value = scalars_mock

        result = await repo.update_form_data(_make_uuid(), {})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_messages(self, repo, db):
        sid = _make_uuid()
        msgs = [_make_message_orm(sid, "user", "Hi"), _make_message_orm(sid, "assistant", "Hello")]

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = msgs
        db.execute.return_value.scalars.return_value = scalars_mock

        result = await repo.get_messages(sid)
        assert result == msgs
        assert len(result) == 2



# LLMService tests


class TestLLMService:

    @pytest.fixture
    def llm_service(self):
        from app.services.llm_service import LLMService
        return LLMService()

    @pytest.mark.asyncio
    async def test_chat_returns_reply_and_extracted_data(self, llm_service):
        expected_payload = {
            "reply_to_user": "Aké je vaše meno?",
            "extracted_data": {},
        }

        mock_message = MagicMock()
        mock_message.content = json.dumps(expected_payload)

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_completion),
        ):
            result = await llm_service.chat(
                system_prompt="You are a helpful assistant.",
                history=[{"role": "user", "content": "Chcem sa prihlásiť"}],
            )

        assert result.reply_to_user == "Aké je vaše meno?"
        assert result.extracted_data == {}

    @pytest.mark.asyncio
    async def test_chat_with_extracted_data(self, llm_service):
        extracted = {"personal_info": {"first_name": "Jana", "last_name": "Nováková"}}
        payload = {"reply_to_user": "Ďakujem!", "extracted_data": extracted}

        mock_message = MagicMock()
        mock_message.content = json.dumps(payload)
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_completion),
        ):
            result = await llm_service.chat("sys", [])

        assert result.extracted_data == extracted
        assert result.reply_to_user == "Ďakujem!"

    @pytest.mark.asyncio
    async def test_chat_malformed_json_raises(self, llm_service):
        mock_message = MagicMock()
        mock_message.content = "not a json at all"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        with patch.object(
            llm_service._client.chat.completions,
            "create",
            new=AsyncMock(return_value=mock_completion),
        ):
            with pytest.raises(ValueError, match="LLM.*JSON"):
                await llm_service.chat("sys", [])

    def test_build_system_prompt_contains_missing_fields(self, llm_service):
        prompt = llm_service.build_system_prompt(missing=["personal_info", "education"])
        assert "personal_info" in prompt
        assert "education" in prompt

    def test_build_system_prompt_complete(self, llm_service):
        prompt = llm_service.build_system_prompt(missing=[])
        assert "complet" in prompt.lower() or "hotov" in prompt.lower() or "vš" in prompt.lower()



# FormService tests

class TestFormService:

    def _make_repo_mock(
        self,
        session_id: uuid.UUID,
        form_data: dict | None = None,
        messages: list | None = None,
    ) -> AsyncMock:
        repo = AsyncMock()
        mock_sess = _make_session_orm(session_id=session_id, form_data=form_data or {})
        repo.get_by_id.return_value = mock_sess
        repo.get_messages.return_value = messages or []
        repo.add_message.return_value = _make_message_orm(session_id, "user", "hi")
        repo.update_form_data.return_value = mock_sess
        return repo

    def _make_llm_mock(self, reply: str = "Next question?", extracted: dict | None = None):
        from app.services.llm_service import LLMResponse
        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(
            reply_to_user=reply,
            extracted_data=extracted or {},
        )
        llm.build_system_prompt.return_value = "system prompt"
        return llm

    @pytest.mark.asyncio
    async def test_process_message_returns_reply(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        repo = self._make_repo_mock(sid)
        llm = self._make_llm_mock(reply="Ako sa voláte?")
        service = FormService(repo=repo, llm=llm)

        response = await service.process_message(session_id=sid, user_text="Dobrý deň")
        assert response.reply == "Ako sa voláte?"

    @pytest.mark.asyncio
    async def test_process_message_session_not_found_raises(self):
        from app.services.form_service import FormService

        repo = AsyncMock()
        repo.get_by_id.return_value = None
        llm = self._make_llm_mock()
        service = FormService(repo=repo, llm=llm)

        with pytest.raises(ValueError, match="Session.*not found"):
            await service.process_message(_make_uuid(), "Hi")

    @pytest.mark.asyncio
    async def test_process_message_saves_user_message(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        repo = self._make_repo_mock(sid)
        llm = self._make_llm_mock()
        service = FormService(repo=repo, llm=llm)

        await service.process_message(session_id=sid, user_text="Jana Nováková")

        # add_message is called at least for user message and assistant reply
        assert repo.add_message.await_count >= 2

    @pytest.mark.asyncio
    async def test_process_message_merges_extracted_data(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        existing = {"personal_info": {"first_name": "Jana"}}
        repo = self._make_repo_mock(sid, form_data=existing)
        new_extracted = {"personal_info": {"last_name": "Nováková"}}
        llm = self._make_llm_mock(extracted=new_extracted)
        service = FormService(repo=repo, llm=llm)

        await service.process_message(session_id=sid, user_text="Nováková")

        repo.update_form_data.assert_awaited_once()
        call_args = repo.update_form_data.call_args
        saved_data = call_args[0][1]  # positional arg — dict
        assert saved_data.get("personal_info", {}).get("last_name") == "Nováková"

    @pytest.mark.asyncio
    async def test_process_message_status_completed_when_no_missing(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        repo = self._make_repo_mock(sid, form_data={})
        llm = self._make_llm_mock(extracted={})
        service = FormService(repo=repo, llm=llm)

        with patch.object(ApplicationForm, "missing_required_fields", return_value=[]):
            await service.process_message(session_id=sid, user_text="ok")

        call_args = repo.update_form_data.call_args
        saved_status = call_args[1].get("status") or (call_args[0][2] if len(call_args[0]) > 2 else None)
        assert saved_status == "completed"

    @pytest.mark.asyncio
    async def test_process_message_status_active_when_missing_fields(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        repo = self._make_repo_mock(sid, form_data={})
        llm = self._make_llm_mock(extracted={})
        service = FormService(repo=repo, llm=llm)

        with patch(
            "app.services.form_service.ApplicationForm.missing_required_fields",
            return_value=["personal_info", "study_program"],
        ):
            await service.process_message(session_id=sid, user_text="hi")

        call_args = repo.update_form_data.call_args
        saved_status = call_args[1].get("status") or (call_args[0][2] if len(call_args[0]) > 2 else None)
        assert saved_status == "active"

    @pytest.mark.asyncio
    async def test_get_session_form_returns_application_form(self):
        from app.services.form_service import FormService

        sid = _make_uuid()
        form_data = {
            "study_program": {
                "university": "UK",
                "faculty": "FMFI",
                "program": "Informatika",
                "form": "DENNÁ",
                "method": "PREZENČNÁ",
            }
        }
        repo = self._make_repo_mock(sid, form_data=form_data)
        service = FormService(repo=repo, llm=AsyncMock())

        app_form = await service.get_session_form(sid)
        assert isinstance(app_form, ApplicationForm)
        assert app_form.study_program is not None
        assert app_form.study_program.university == "UK"
