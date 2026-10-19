"""
DocumentService — filling .docx template and converting to PDF.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid
from pathlib import Path

from docxtpl import DocxTemplate


# Default paths


_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_DEFAULT_TEMPLATE = _TEMPLATES_DIR / "formular.docx"
_LAST_PDF = _TEMPLATES_DIR / "last.pdf"
_DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent.parent / "generated"


class DocumentService:

    def __init__(
        self,
        template_path: Path | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._template_path: Path = template_path or _DEFAULT_TEMPLATE
        self._last_pdf_path: Path = _LAST_PDF
        self._output_dir: Path = output_dir or _DEFAULT_OUTPUT
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def fill_template(self, context: dict) -> Path:
        template_path = self._template_path
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template not found: {template_path}"
            )

        import jinja2
        jinja_env = jinja2.Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )
        
        doc = DocxTemplate(template_path)
        doc.render(context, jinja_env=jinja_env)

        output_filename = f"filled_{uuid.uuid4().hex}.docx"
        output_path = self._output_dir / output_filename
        doc.save(output_path)
        return output_path


    def convert_to_pdf(self, docx_path: Path) -> Path:
        outdir = docx_path.parent  # PDF will be next to docx

        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(outdir),
            str(docx_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (code {result.returncode}): {result.stderr}"
            )

        pdf_path = outdir / (docx_path.stem + ".pdf")
        if not pdf_path.exists():
            raise RuntimeError(
                f"PDF not found after conversion. Expected: {pdf_path}. "
                f"LibreOffice output: {result.stderr}"
            )

        return pdf_path

    def append_static_pdf(self, main_pdf_path: Path) -> Path:

        if not self._last_pdf_path.exists():
            # If the last.pdf file does not exist, just return the generated PDF unchanged.
            return main_pdf_path

        try:
            from pypdf import PdfReader, PdfWriter
        except ImportError:
            # If the library is missing, return as is
            return main_pdf_path

        writer = PdfWriter()

        main_reader = PdfReader(main_pdf_path)
        for page in main_reader.pages:
            writer.add_page(page)

        static_reader = PdfReader(self._last_pdf_path)
        for page in static_reader.pages:
            writer.add_page(page)

        with open(main_pdf_path, "wb") as f:
            writer.write(f)

        return main_pdf_path

    # Asynchronous wrappers do not block the FastAPI event loop

    async def fill_template_async(self, context: dict) -> Path:
        return await asyncio.to_thread(self.fill_template, context)

    async def convert_to_pdf_async(self, docx_path: Path) -> Path:
        return await asyncio.to_thread(self.convert_to_pdf, docx_path)

    async def append_static_pdf_async(self, main_pdf_path: Path) -> Path:
        return await asyncio.to_thread(self.append_static_pdf, main_pdf_path)

    # Generate pdf — high-level pipeline

    def _uppercase_dict(self, data: dict) -> dict:
        result = {}
        for k, v in data.items():
            if isinstance(v, str):
                result[k] = v.upper()
            elif isinstance(v, dict):
                result[k] = self._uppercase_dict(v)
            elif isinstance(v, list):
                result[k] = self._uppercase_list(v)
            else:
                result[k] = v
        return result

    def _uppercase_list(self, lst: list) -> list:
        result = []
        for item in lst:
            if isinstance(item, dict):
                result.append(self._uppercase_dict(item))
            elif isinstance(item, str):
                result.append(item.upper())
            elif isinstance(item, list):
                result.append(self._uppercase_list(item))
            else:
                result.append(item)
        return result

    async def generate_pdf(
        self,
        context: dict,
        cleanup: bool = True,
    ) -> Path:
        upper_context = self._uppercase_dict(context)
        docx_path = await self.fill_template_async(upper_context)
        try:
            pdf_path = await self.convert_to_pdf_async(docx_path)
            pdf_path = await self.append_static_pdf_async(pdf_path)
        finally:
            if cleanup and docx_path.exists():
                docx_path.unlink()
        return pdf_path

    # Converting ApplicationForm → flat context for the template

    @staticmethod
    def _slice_to_dict(prefix: str, value: str, max_len: int) -> dict:
        clean_val = str(value or "").replace("/", "").replace(" ", "").replace("-", "").strip()
        res = {f"{prefix}{i+1}": "" for i in range(max_len)}
        for i in range(min(len(clean_val), max_len)):
            res[f"{prefix}{i+1}"] = clean_val[i]
        return res

    @staticmethod
    def _ensure_list_of_dicts(items) -> list[dict]:
        if not items:
            return []
        result = []
        for item in items:
            if isinstance(item, dict):
                result.append(item)
            elif hasattr(item, 'model_dump'):
                result.append(item.model_dump())
            elif hasattr(item, '__dict__'):
                result.append(dict(item.__dict__))
            else:
                result.append(item)
        return result

    @staticmethod
    def form_to_context(form_data: dict) -> dict:
        context = {}
        vzor_type = str(form_data.get("vzor_type") or "")
        
        # 1. Personal Data 
        pi = form_data.get("personal_info") or {}
        bdate_raw = pi.get("birth_date")
        if hasattr(bdate_raw, "strftime"):
            bdate = bdate_raw.strftime("%Y-%m-%d")
        else:
            bdate = str(bdate_raw or "").strip()
            
        rc = str(pi.get("rodne_cislo", "") or "")
        
        context.update({
            "meno": pi.get("first_name") or "",
            "priezvisko": pi.get("last_name") or "",
            "rodne_priezvisko": pi.get("birth_last_name") or pi.get("last_name") or "",
            "stat_narodenia": pi.get("birth_country") or "",
            "miesto_narodenia": pi.get("birth_place") or "",
            "statne_obcianstvo": pi.get("citizenship") or "",
            "email": pi.get("email") or "",
            "telefon": pi.get("phone") or "",
        })

        if len(bdate) >= 10 and bdate[4] == "-" and bdate[7] == "-":
            context.update({
                "r1": bdate[0], "r2": bdate[1], "r3": bdate[2], "r4": bdate[3],
                "m1": bdate[5], "m2": bdate[6],
                "d1": bdate[8], "d2": bdate[9],
            })
        else:
            for key in ["r1", "r2", "r3", "r4", "m1", "m2", "d1", "d2"]:
                context[key] = ""
            
        context.update(DocumentService._slice_to_dict("rc", rc, 10))
        
        gender = pi.get("gender") or ""
        context["muz_x"] = "X" if gender == "M" else ""
        context["zena_x"] = "X" if gender == "F" else ""

        # Addresses 
        perm = pi.get("permanent_address") or {}
        context.update({
            "trvale_ulica": perm.get("street") or "",
            "trvale_mesto": perm.get("city") or "",
            "trvale_psc": perm.get("postal_code") or "",
            "trvale_okres": perm.get("district") or "",
            "trvale_stat": perm.get("country") or "",
        })
        
        corr = pi.get("correspondence_address") or {}
        context.update({
            "koresp_ulica": corr.get("street") or "",
            "koresp_mesto": corr.get("city") or "",
            "koresp_psc": corr.get("postal_code") or "",
            "koresp_okres": corr.get("district") or "",
            "koresp_stat": corr.get("country") or "",
        })
        
        forn = pi.get("foreign_residence") or {}
        context.update({
            "cudzinec_ulica": forn.get("street") or "",
            "cudzinec_mesto": forn.get("city") or "",
            "cudzinec_psc": forn.get("postal_code") or "",
            "cudzinec_okres": forn.get("district") or "",
            "cudzinec_stat": forn.get("country") or "",
        })

        # 2. Secondary Education
        edu = form_data.get("education") or {}
        school_addr = edu.get("school_address") or {}
        if not isinstance(school_addr, dict):
            school_addr = {}
        context.update({
            "skola_nazov": edu.get("school_name") or "",
            "nazov_skoly": edu.get("school_name") or "",
            "ulica_skoly": school_addr.get("street") or "",
            "mesto_skoly": school_addr.get("city") or "",
            "psc_skoly": school_addr.get("postal_code") or "",
            "okres_skoly": school_addr.get("district") or "",
            "stat_skoly": school_addr.get("country") or "",
            "rok_maturity": str(edu.get("graduation_year") or ""),
            "datum_maturity": str(edu.get("maturity_date") or ""),
            "studijny_odbor": edu.get("study_field") or "",
            "stupen_vzdelania": edu.get("education_level") or "",
        })
        
        stype = str(edu.get("school_type") or "").lower()
        is_ina = (
            "iná" in stype
            or stype == "ina"
            or "lýceum" in stype
            or "lyceum" in stype
            or "licej" in stype
        )
        context.update({
            "skola_gym": "X" if ("gymn" in stype and not is_ina) else "",
            "skola_sos": "X" if (("odborná" in stype or "odborn" in stype) and "učil" not in stype and not is_ina) else "",
            "skola_sou": "X" if ("učil" in stype or "ucil" in stype) else "",
            "skola_kom": "X" if "konzervat" in stype else "",
            "skola_zss": "X" if ("združená" in stype or "zdruzena" in stype) else "",
            "skola_ina": "X" if is_ina else "",
        })
        
        context.update(DocumentService._slice_to_dict("ks", str(edu.get("school_code") or ""), 9))
        context.update(DocumentService._slice_to_dict("ko", str(edu.get("field_code") or ""), 7))
        
        # 3. Higher Education (where applying)
        sp = form_data.get("study_program") or {}
        context.update({
            "univerzita": sp.get("university") or "",
            "fakulta": sp.get("faculty") or "",
            "vs_detasovane": sp.get("detached_workplace") or "",
            "studijny_program": sp.get("program") or "",
            "forma_studia": sp.get("form") or "",
            "metod_studia": sp.get("method") or "",
            "cudzi_jazyk": sp.get("foreign_language_exam") or "",
        })

        # 4. Additional Flags 
        if vzor_type == "3":
            context["is_cudzinec"] = True
        else:
            context["is_cudzinec"] = False
        
        # 5. Lists for Jinja2 loops 
        if vzor_type == "3":
            context["subjects"] = []
            context["maturita_exams"] = []
        else:
            context["subjects"] = DocumentService._ensure_list_of_dicts(
                form_data.get("subjects") or []
            )
            context["maturita_exams"] = DocumentService._ensure_list_of_dicts(
                form_data.get("maturita_exams") or []
            )
            
        if vzor_type == "3":
            context["prilohy"] = ["KÓPIA DOKLADU O VZDELANÍ", "ÚRADNÝ PREKLAD DOKLADU"]
        elif vzor_type == "2":
            context["prilohy"] = ["KÓPIA MATURITNÉHO VYSVEDČENIA", "KÓPIA VŠ DIPLOMU"]
        elif vzor_type == "1":
            context["prilohy"] = ["ROČNÍKOVÉ VYSVEDČENIA"]
        else:
            context["prilohy"] = form_data.get("prilohy") or []
        
        # 6. Other flat fields 
        
        def clean_x(val):
            val_str = str(val or "")
            return "" if val_str.upper() == "X" else val_str

        from datetime import datetime
        current_year = datetime.now().year
        # If the form is submitted before autumn, the academic year usually starts this year (e.g., 2024/2025).
        # If submitted in autumn/winter, it's for admission the following year.
        default_rok = str(current_year)
        default_rok_koniec = str(current_year + 1)
        if datetime.now().month >= 9:
            default_rok = str(current_year + 1)
            default_rok_koniec = str(current_year + 2)

        def format_rok(rok_val, default_val):
            val = str(rok_val or default_val).strip()
            return val[-2:] if len(val) >= 2 else val

        context.update({
            "vs_nazov": form_data.get("vs_nazov") or "",
            "vs_fakulta": form_data.get("vs_fakulta") or "",
            "vs_program": form_data.get("vs_program") or "",
            "vs_odbor": form_data.get("vs_odbor") or "",
            "vs_stupen": form_data.get("vs_stupen") or "",
            "vs_zaciatok": form_data.get("vs_zaciatok") or "",
            "vs_koniec": form_data.get("vs_koniec") or "",
            "vs_titul": form_data.get("vs_titul") or "",
            "akademicky_rok": format_rok(form_data.get("akademicky_rok"), default_rok),
            "akademicky_rok_koniec": format_rok(form_data.get("akademicky_rok_koniec"), default_rok_koniec),
            "zamestnanie_sucasne": form_data.get("zamestnanie_sucasne") or form_data.get("current_employment") or "",
            "zamestnanie_predch": form_data.get("zamestnanie_predch") or form_data.get("previous_employment") or "",
            "suhlas_text": form_data.get("suhlas_text") or "",
            "datum_vyplnenia": datetime.now().strftime("%d.%m.%Y"),
            "studijny_program_2": clean_x(form_data.get("studijny_program_2")),
            "forma_studia_2": clean_x(form_data.get("forma_studia_2")),
            "metod_studia_2": clean_x(form_data.get("metod_studia_2")),
            "studijny_program_3": clean_x(form_data.get("studijny_program_3")),
            "forma_studia_3": clean_x(form_data.get("forma_studia_3")),
            "metod_studia_3": clean_x(form_data.get("metod_studia_3")),
            "priem_2": form_data.get("priem_2") or "",
            "priem_3": form_data.get("priem_3") or "",
        })

        return context
