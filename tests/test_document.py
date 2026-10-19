"""
Unit and integration tests for DocumentService (Stage 4).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Fixtures

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"
TEMPLATE_PATH = TEMPLATES_DIR / "formular.docx"


@pytest.fixture
def minimal_context() -> dict:
    return {
        "first_name": "Jana",
        "last_name": "Novakova",
        "birth_day": "12",
        "birth_month": "03",
        "birth_year": "2001",
        "birth_place": "Nitra",
        "birth_country": "SK",
        "citizenship": "SK",
        "gender_m": False,
        "gender_f": True,
        "perm_street": "Hlavna 1",
        "perm_city": "Nitra",
        "perm_postal_code": "94901",
        "perm_country": "SK",
        "university": "UNIVERZITA KOMENSKEHO",
        "faculty": "FMFI",
        "program": "INFORMATIKA",
        "study_form": "DENNA",
        "study_method": "PREZENCNA",
        "graduation_year": "2019",
        "school_name": "GYMNAZIUM GOLIANOVA",
        "school_street": "Golianova 1",
        "school_city": "Nitra",
        "school_postal_code": "94901",
        "school_country": "SK",
        "study_field": "MATEMATIKA",
    }


@pytest.fixture
def doc_service(tmp_path: Path):
    from app.services.document_service import DocumentService
    svc = DocumentService()
    svc._template_path = TEMPLATE_PATH
    svc._output_dir = tmp_path
    return svc

class TestFillTemplate:

    def test_fill_template_returns_path(self, doc_service, minimal_context, tmp_path):
        result = doc_service.fill_template(minimal_context)
        assert isinstance(result, Path)
        assert result.exists()
        assert result.suffix == ".docx"

    def test_fill_template_file_in_output_dir(self, doc_service, minimal_context, tmp_path):
        result = doc_service.fill_template(minimal_context)
        assert result.parent == tmp_path

    def test_fill_template_unique_filenames(self, doc_service, minimal_context):
        p1 = doc_service.fill_template(minimal_context)
        p2 = doc_service.fill_template(minimal_context)
        assert p1 != p2

    def test_fill_template_empty_context_ok(self, doc_service):
        result = doc_service.fill_template({})
        assert result.exists()

    def test_fill_template_template_not_found_raises(self, tmp_path):
        from app.services.document_service import DocumentService
        svc = DocumentService()
        svc._template_path = tmp_path / "nonexistent.docx"
        svc._output_dir = tmp_path
        with pytest.raises(FileNotFoundError):
            svc.fill_template({})

    @pytest.mark.asyncio
    async def test_fill_template_async_runs_in_thread(self, doc_service, minimal_context):
        result = await doc_service.fill_template_async(minimal_context)
        assert result.exists()

class TestConvertToPdf:

    def _make_fake_docx(self, tmp_path: Path) -> Path:
        p = tmp_path / f"test_{uuid.uuid4().hex}.docx"
        p.write_bytes(b"PK\x03\x04")  # minimal ZIP signature
        return p

    def _mock_libreoffice_success(self, tmp_path: Path, docx_path: Path):
        expected_pdf = tmp_path / (docx_path.stem + ".pdf")

        def _fake_run(cmd, *args, **kwargs):
            # LibreOffice creates PDF in --outdir
            outdir = tmp_path
            pdf = outdir / (Path(cmd[-1]).stem + ".pdf")
            pdf.write_bytes(b"%PDF-1.4")
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        return _fake_run, expected_pdf

    def test_convert_to_pdf_calls_libreoffice(self, doc_service, tmp_path):
        docx_path = tmp_path / "form.docx"
        docx_path.write_bytes(b"PK\x03\x04")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            # Create fake PDF in output_dir
            (tmp_path / "form.pdf").write_bytes(b"%PDF-1.4")

            doc_service.convert_to_pdf(docx_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  
        assert "libreoffice" in call_args[0]
        assert "--headless" in call_args
        assert "--convert-to" in call_args
        assert "pdf" in call_args
        assert str(docx_path) in call_args

    def test_convert_to_pdf_returns_pdf_path(self, doc_service, tmp_path):
        docx_path = tmp_path / "filled_form.docx"
        docx_path.write_bytes(b"PK\x03\x04")

        fake_run, _ = self._mock_libreoffice_success(tmp_path, docx_path)
        with patch("subprocess.run", side_effect=fake_run):
            result = doc_service.convert_to_pdf(docx_path)

        assert result.suffix == ".pdf"
        assert result.exists()

    def test_convert_to_pdf_raises_on_libreoffice_error(self, doc_service, tmp_path):
        docx_path = tmp_path / "bad.docx"
        docx_path.write_bytes(b"PK\x03\x04")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="conversion failed")
            with pytest.raises(RuntimeError, match="LibreOffice"):
                doc_service.convert_to_pdf(docx_path)

    def test_convert_to_pdf_raises_if_pdf_not_created(self, doc_service, tmp_path):
        docx_path = tmp_path / "ghost.docx"
        docx_path.write_bytes(b"PK\x03\x04")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            # Intentionally do not create PDF
            with pytest.raises(RuntimeError, match="PDF"):
                doc_service.convert_to_pdf(docx_path)

    @pytest.mark.asyncio
    async def test_convert_to_pdf_async_runs_in_thread(self, doc_service, tmp_path):
        docx_path = tmp_path / "async_test.docx"
        docx_path.write_bytes(b"PK\x03\x04")

        fake_run, _ = self._mock_libreoffice_success(tmp_path, docx_path)
        with patch("subprocess.run", side_effect=fake_run):
            result = await doc_service.convert_to_pdf_async(docx_path)
        assert result.suffix == ".pdf"

class TestGeneratePdf:

    @pytest.mark.asyncio
    async def test_generate_pdf_full_pipeline(self, doc_service, minimal_context, tmp_path):
        fake_pdf = tmp_path / "output.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with patch.object(doc_service, "convert_to_pdf_async", new=AsyncMock(return_value=fake_pdf)), \
             patch.object(doc_service, "append_static_pdf_async", new=AsyncMock(return_value=fake_pdf)):
            result = await doc_service.generate_pdf(minimal_context)

        assert result == fake_pdf
        assert result.exists()

    @pytest.mark.asyncio
    async def test_generate_pdf_cleans_up_docx(self, doc_service, minimal_context, tmp_path):
        fake_pdf = tmp_path / "clean.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        captured_docx: list[Path] = []

        async def _capture_and_return(docx_path: Path) -> Path:
            captured_docx.append(docx_path)
            return fake_pdf

        async def _async_echo(p: Path) -> Path:
            return p

        with patch.object(doc_service, "convert_to_pdf_async", side_effect=_capture_and_return), \
             patch.object(doc_service, "append_static_pdf_async", side_effect=_async_echo):
            await doc_service.generate_pdf(minimal_context, cleanup=True)

        assert captured_docx, "convert_to_pdf_async was never called"
        # .docx should be deleted
        assert not captured_docx[0].exists()

    @pytest.mark.asyncio
    async def test_generate_pdf_keeps_docx_when_cleanup_false(self, doc_service, minimal_context, tmp_path):
        fake_pdf = tmp_path / "keep.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        captured_docx: list[Path] = []

        async def _capture_and_return(docx_path: Path) -> Path:
            captured_docx.append(docx_path)
            return fake_pdf

        async def _async_echo(p: Path) -> Path:
            return p

        with patch.object(doc_service, "convert_to_pdf_async", side_effect=_capture_and_return), \
             patch.object(doc_service, "append_static_pdf_async", side_effect=_async_echo):
            await doc_service.generate_pdf(minimal_context, cleanup=False)

        assert captured_docx[0].exists()

class TestTemplateRouting:
    def test_uppercase_dict(self):
        from app.services.document_service import DocumentService
        svc = DocumentService()
        data = {
            "name": "john",
            "age": 20,
            "nested": {
                "city": "bratislava"
            },
            "none_val": None
        }
        res = svc._uppercase_dict(data)
        assert res["name"] == "JOHN"
        assert res["age"] == 20
        assert res["nested"]["city"] == "BRATISLAVA"
        assert res["none_val"] is None

def test_template_slicing_logic():
    from app.services.document_service import DocumentService
    
    svc = DocumentService()
    # Mock data from LLM
    raw_data = {
        "personal_info": {
            "birth_date": "2005-08-12",
            "rodne_cislo": "050812/123", # 9 chars (without slash)
            "gender": "M"
        },
        "education": {
            "school_code": "1234",
            "field_code": "56"
        }
    }
    
    ctx = svc.form_to_context(raw_data)
    
    # Check date slicing
    assert ctx.get("r1") == "2" and ctx.get("r4") == "5"
    assert ctx.get("m1") == "0" and ctx.get("m2") == "8"
    assert ctx.get("d1") == "1" and ctx.get("d2") == "2"
    
    # Check rodne_cislo slicing
    assert ctx.get("rc1") == "0"
    assert ctx.get("rc6") == "2"
    assert ctx.get("rc9") == "3"
    assert ctx.get("rc10") == ""  # Protection against IndexError, padding

    # Check ks and ko slicing
    assert ctx.get("ks1") == "1"
    assert ctx.get("ks9") == ""
    assert ctx.get("ko1") == "5"

    # Check gender
    assert ctx.get("muz_x") == "X"
    assert ctx.get("zena_x") == ""
