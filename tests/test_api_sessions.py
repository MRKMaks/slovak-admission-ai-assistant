"""
REST API tests 
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.dependencies import get_form_service, get_document_service
from app.services.form_service import FormServiceResponse



# Helpers

def _make_session_id() -> uuid.UUID:
    return uuid.uuid4()


def _mock_form_service(
    session_id: uuid.UUID | None = None,
    reply: str = "Ako sa voláte?",
    is_complete: bool = False,
) -> AsyncMock:
    sid = session_id or _make_session_id()
    svc = AsyncMock()

    mock_session = MagicMock()
    mock_session.id = sid
    mock_session.status = "active"
    mock_session.form_data = {}
    svc.repo = AsyncMock()
    svc.repo.create.return_value = mock_session

    svc.process_message.return_value = FormServiceResponse(
        reply=reply,
        is_complete=is_complete,
        form_data={},
        session_id=sid,
    )

    svc.get_session_form.return_value = MagicMock(is_complete=lambda: is_complete)
    return svc, sid, mock_session


def _mock_document_service(tmp_path: Path) -> AsyncMock:
    svc = AsyncMock()
    fake_pdf = tmp_path / "output.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 test")
    svc.generate_pdf.return_value = fake_pdf
    svc.form_to_context = MagicMock(return_value={})
    return svc, fake_pdf



# POST /api/v1/sessions/

class TestCreateSession:

    @pytest.mark.asyncio
    async def test_create_session_returns_201(self):
        sid = _make_session_id()
        form_svc, sid, mock_sess = _mock_form_service(session_id=sid)

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/sessions/")

            assert response.status_code == 201
            body = response.json()
            assert "session_id" in body
            assert "status" in body
            assert body["status"] == "active"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_session_calls_repo_create(self):
        form_svc, sid, _ = _mock_form_service()

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/api/v1/sessions/")

            form_svc.repo.create.assert_awaited_once()
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_session_with_filename(self):
        form_svc, sid, _ = _mock_form_service()

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/sessions/",
                    params={"template_filename": "formular.docx"},
                )
            assert response.status_code == 201
            form_svc.repo.create.assert_awaited_once_with(
                template_filename="formular.docx"
            )
        finally:
            app.dependency_overrides.clear()



# POST /api/v1/sessions/{id}/messages


class TestPostMessage:

    @pytest.mark.asyncio
    async def test_post_message_returns_200(self):
        sid = _make_session_id()
        form_svc, sid, _ = _mock_form_service(session_id=sid, reply="Vaše meno?")

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/sessions/{sid}/messages",
                    json={"content": "Dobrý deň"},
                )

            assert response.status_code == 200
            body = response.json()
            assert body["reply"] == "Vaše meno?"
            assert body["status"] == "in_progress"
            assert body["session_id"] == str(sid)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_message_status_completed(self):
        sid = _make_session_id()
        form_svc, sid, _ = _mock_form_service(
            session_id=sid, reply="Dakujem!", is_complete=True
        )

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/sessions/{sid}/messages",
                    json={"content": "ok"},
                )

            assert response.status_code == 200
            assert response.json()["status"] == "completed"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_message_missing_content_422(self):
        sid = _make_session_id()
        form_svc, sid, _ = _mock_form_service(session_id=sid)

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/sessions/{sid}/messages",
                    json={},
                )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_message_session_not_found_404(self):
        sid = _make_session_id()
        form_svc = AsyncMock()
        form_svc.process_message.side_effect = ValueError(f"Session {sid} not found")

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/api/v1/sessions/{sid}/messages",
                    json={"content": "hello"},
                )
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_message_calls_process_message(self):
        sid = _make_session_id()
        form_svc, sid, _ = _mock_form_service(session_id=sid)

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post(
                    f"/api/v1/sessions/{sid}/messages",
                    json={"content": "Jana"},
                )

            form_svc.process_message.assert_awaited_once_with(
                session_id=sid, user_text="Jana"
            )
        finally:
            app.dependency_overrides.clear()



# GET /api/v1/sessions/{id}/export


class TestExportPdf:

    @pytest.mark.asyncio
    async def test_export_returns_pdf_file(self, tmp_path):
        sid = _make_session_id()

        form_svc = AsyncMock()
        mock_orm_session = MagicMock()
        mock_orm_session.status = "completed"
        mock_orm_session.form_data = {}
        form_svc.repo = AsyncMock()
        form_svc.repo.get_by_id.return_value = mock_orm_session

        doc_svc, fake_pdf = _mock_document_service(tmp_path)

        app.dependency_overrides[get_form_service] = lambda: form_svc
        app.dependency_overrides[get_document_service] = lambda: doc_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/sessions/{sid}/export")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_export_session_not_found_404(self):
        sid = _make_session_id()

        form_svc = AsyncMock()
        form_svc.repo = AsyncMock()
        form_svc.repo.get_by_id.return_value = None

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/sessions/{sid}/export")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_export_incomplete_session_409(self):
        sid = _make_session_id()

        form_svc = AsyncMock()
        mock_orm_session = MagicMock()
        mock_orm_session.status = "active"
        mock_orm_session.form_data = {}
        form_svc.repo = AsyncMock()
        form_svc.repo.get_by_id.return_value = mock_orm_session

        app.dependency_overrides[get_form_service] = lambda: form_svc

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(f"/api/v1/sessions/{sid}/export")
            assert response.status_code == 409
        finally:
            app.dependency_overrides.clear()
