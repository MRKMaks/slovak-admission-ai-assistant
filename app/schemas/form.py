"""
Pydantic V2 schemas for the Slovak application form for university admission
(Ministerstvo školstva SR, form 04/2022).

Form structure:
  - Personal data (PersonalInfo) + addresses
  - Study program information (StudyProgramInfo)
  - Secondary education information (EducationInfo)
  - Grades by year (GradeRecord) + maturity results (MaturitySubject)
  - Root ApplicationForm (all fields Optional — for step-by-step filling)
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional, List

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Helper utility
# ---------------------------------------------------------------------------

def _to_upper(v: str | None) -> str | None:
    """Converts a string to uppercase; None is passed unchanged."""
    return v.upper() if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# Address — common address block (permanent, correspondence, foreign)
# ---------------------------------------------------------------------------

class Address(BaseModel):
    """Ulica a číslo / Mesto / PSČ / Okres / Štát."""

    street: Optional[str] = Field(None, description="Ulica a číslo")
    city: Optional[str] = Field(None, description="Mesto (obec)")
    postal_code: Optional[str] = Field(None, description="PSČ")
    country: Optional[str] = Field(None, description="Štát (ISO 3166-1 alpha-2 or full name)")
    district: Optional[str] = Field(None, description="Okres")



# ---------------------------------------------------------------------------
# PersonalInfo — first page of the form, personal data block
# ---------------------------------------------------------------------------

class PersonalInfo(BaseModel):
    """Osobné údaje uchádzača."""

    first_name: Optional[str] = Field(None, description="Meno")
    last_name: Optional[str] = Field(None, description="Priezvisko")
    birth_last_name: Optional[str] = Field(None, description="Rodné priezvisko")
    academic_title: Optional[str] = Field(None, description="Akademický titul")

    birth_date: Optional[date] = Field(None, description="Dátum narodenia")
    birth_place: Optional[str] = Field(None, description="Miesto narodenia")
    birth_country: Optional[str] = Field(None, description="Štát narodenia")

    rodne_cislo: Optional[str] = Field(
        None,
        description="Rodné číslo (format YYMMDD/XXXX, or any placeholder for foreigners)",
    )

    citizenship: Optional[str] = Field(None, description="Štátne občianstvo (e.g., SLOVENSKÉ, UKRAJINSKÉ)")

    gender: Optional[Literal["M", "F"]] = Field(None, description="Pohlavie: M=muž, F=žena")

    @field_validator("gender", mode="before")
    @classmethod
    def _normalize_gender(cls, v: object) -> object:
        """Normalizes gender values from LLM to M/F."""
        _MAP = {
            "muž": "M", "muz": "M", "man": "M", "male": "M",
            "m": "M", "chlapec": "M",
            "žena": "F", "zena": "F", "woman": "F", "female": "F",
            "f": "F", "dievča": "F", "dievca": "F",
        }
        if isinstance(v, str):
            normalized = _MAP.get(v.lower().strip())
            if normalized:
                return normalized
        return v

    phone: Optional[str] = Field(None, description="Tel. č.")
    email: Optional[EmailStr] = Field(None, description="E-mailová adresa")

    permanent_address: Optional[Address] = Field(None, description="Adresa trvalého bydliska")
    correspondence_address: Optional[Address] = Field(
        None, description="Korešpondenčná adresa (ak je iná)"
    )
    foreign_residence: Optional[Address] = Field(
        None, description="Miesto pobytu u cudzinca"
    )


# ---------------------------------------------------------------------------
# StudyProgramInfo — "University / faculty / program" block
# ---------------------------------------------------------------------------

class StudyProgramInfo(BaseModel):
    """
    Vysoká škola, Fakulta, Študijný program, Forma a Metóda štúdia.

    Fields university, faculty, program are normalized to uppercase.
    """

    university: Optional[str] = Field(None, description="Vysoká škola")
    faculty: Optional[str] = Field(None, description="Fakulta")
    detached_workplace: Optional[str] = Field(None, description="Detašované pracovisko")
    program: Optional[str] = Field(None, description="Študijný program")

    form: Optional[Literal["DENNÁ", "EXTERNÁ"]] = Field(None, description="Forma štúdia")
    method: Optional[Literal["PREZENČNÁ", "DIŠTANČNÁ", "KOMBINOVANÁ"]] = Field(
        None, description="Metóda štúdia"
    )

    foreign_language_exam: Optional[str] = Field(
        None, description="Prijímaciu skúšku budem robiť z cudzieho jazyka"
    )

    @field_validator("university", "faculty", "program", mode="before")
    @classmethod
    def normalise_to_upper(cls, v: str) -> str:
        return _to_upper(v)  # type: ignore[return-value]

    @field_validator("form", mode="before")
    @classmethod
    def _normalize_form(cls, v: object) -> object:
        """DENNA/denna/denná → DENNÁ, EXTERNA/externa → EXTERNÁ."""
        _MAP = {
            "denna": "DENNÁ", "denná": "DENNÁ", "denn": "DENNÁ", "den": "DENNÁ",
            "externá": "EXTERNÁ", "externa": "EXTERNÁ", "extern": "EXTERNÁ",
        }
        if isinstance(v, str):
            normalized = _MAP.get(v.lower().strip())
            if normalized:
                return normalized
        return v

    @field_validator("method", mode="before")
    @classmethod
    def _normalize_method(cls, v: object) -> object:
        """prezencna/prezenčná → PREZENČNÁ etc."""
        _MAP = {
            "prezenčná": "PREZENČNÁ", "prezencna": "PREZENČNÁ", "prezencná": "PREZENČNÁ",
            "prezenčna": "PREZENČNÁ", "prezentna": "PREZENČNÁ",
            "dištančná": "DIŠTANČNÁ", "distancna": "DIŠTANČNÁ", "distančná": "DIŠTANČNÁ",
            "kombinovaná": "KOMBINOVANÁ", "kombinovana": "KOMBINOVANÁ", "kombina": "KOMBINOVANÁ",
        }
        if isinstance(v, str):
            normalized = _MAP.get(v.lower().strip())
            if normalized:
                return normalized
        return v



# ---------------------------------------------------------------------------
# EducationInfo — secondary education block (page 2 of the form)
# ---------------------------------------------------------------------------

from enum import Enum

class TemplateType(str, Enum):
    VZOR1 = "vzor1"
    VZOR2 = "vzor2"
    VZOR3 = "vzor3"

_SCHOOL_TYPES = Literal[
    "gymnázium",
    "stredná odborná škola",
    "stredné odborné učilište",
    "konzervatórium",
    "združená stredná škola",
    "iná",
]


class EducationInfo(BaseModel):
    """
    Absolvovaná stredná škola, maturitný rok, odbor a stupeň vzdelania.

    Fields school_name, study_field are normalized to uppercase.
    """

    graduation_year: Optional[str] = Field(
        None,
        description="Rok maturitnej skúšky (e.g., 2024 or 05/2024)",
    )
    school_code: Optional[str] = Field(None, description="Kód strednej školy")
    school_type: Optional[_SCHOOL_TYPES] = Field(None, description="Typ absolvovanej strednej školy")
    school_name: Optional[str] = Field(None, description="Názov strednej školy")
    school_address: Optional[Address] = Field(None, description="Adresa strednej školy")

    study_field: Optional[str] = Field(None, description="Študijný odbor")
    field_code: Optional[str] = Field(None, description="Kód študijného odboru")

    education_level: Optional[str] = Field(
        None, description="Stupeň dosiahnutého vzdelania (e.g., úplné stredné odborné)"
    )

    maturity_date: Optional[str] = Field(None, description="Dátum maturitnej skúšky (e.g., 05/2024)")
    maturity_avg: Optional[float] = Field(
        None, description="Priemer maturitnej skúšky", ge=1.0, le=5.0
    )

    @field_validator("school_name", "study_field", mode="before")
    @classmethod
    def normalise_to_upper(cls, v: str) -> str:
        return _to_upper(v)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# GradeRecord — grades for each year of secondary school (table, page 2)
# ---------------------------------------------------------------------------

class GradeRecord(BaseModel):
    """Priemerný prospech podľa koncoročného vysvedčenia (I.–VI. ročník)."""

    subject: str = Field(..., description="Predmet")
    grade_year1: Optional[float] = Field(None, description="I. ročník", ge=1.0, le=5.0)
    grade_year2: Optional[float] = Field(None, description="II. ročník", ge=1.0, le=5.0)
    grade_year3: Optional[float] = Field(None, description="III. ročník", ge=1.0, le=5.0)
    grade_year4: Optional[float] = Field(None, description="IV. ročník", ge=1.0, le=5.0)
    grade_year5: Optional[float] = Field(None, description="V. ročník", ge=1.0, le=5.0)
    grade_year6: Optional[float] = Field(None, description="VI. ročník", ge=1.0, le=5.0)


# ---------------------------------------------------------------------------
# MaturitySubject — results of a single maturita subject (page 2, table)
# ---------------------------------------------------------------------------

class MaturitySubject(BaseModel):
    """Predmet maturitnej skúšky — externá a interná časť."""

    subject: str = Field(..., description="Predmet maturitnej skúšky")
    level: Optional[str] = Field(None, description="Úroveň (e.g., B, C)")
    external_pct: Optional[float] = Field(None, description="Externá časť — %", ge=0.0, le=100.0)
    external_percentile: Optional[float] = Field(None, description="Externá časť — Percentil", ge=0.0, le=100.0)
    internal_written_pct: Optional[float] = Field(
        None, description="Interná časť — Písomná forma (%)", ge=0.0, le=100.0
    )
    internal_oral_grade: Optional[int] = Field(
        None, description="Interná časť — Ústna forma (známka)", ge=1, le=5
    )

# ---------------------------------------------------------------------------
# SubjectGrade and MaturitaExam — for Jinja2 Template rendering
# ---------------------------------------------------------------------------

class SubjectGrade(BaseModel):
    name: str = Field(..., description="Názov predmetu")
    g1: Optional[str] = None
    g2: Optional[str] = None
    g3: Optional[str] = None
    g4: Optional[str] = None
    g5: Optional[str] = None
    g6: Optional[str] = None

class MaturitaExam(BaseModel):
    predmet: str
    uroven: Optional[str] = None
    percenta: Optional[str] = None
    percentil: Optional[str] = None
    pisomna: Optional[str] = None
    ustna: Optional[str] = None

# ---------------------------------------------------------------------------
# ApplicationForm — root model of the entire form
# ---------------------------------------------------------------------------

class ApplicationForm(BaseModel):
    """
    Prihláška na vysokoškolské štúdium (Ministerstvo školstva SR, 04/2022).
    """

    personal_info: Optional[PersonalInfo] = Field(None)
    study_program: Optional[StudyProgramInfo] = Field(None)
    education: Optional[EducationInfo] = Field(None)
    grade_records: Optional[list[GradeRecord]] = Field(None)
    maturity_subjects: Optional[list[MaturitySubject]] = Field(None)

    vzor_type: Literal['1', '2', '3'] = Field('1', description="Typ profilu")

    subjects: Optional[List[SubjectGrade]] = Field(None)
    maturita_exams: Optional[List[MaturitaExam]] = Field(None)
    prilohy: List[str] = Field(default_factory=list)

    vs_nazov: Optional[str] = None
    vs_fakulta: Optional[str] = None
    vs_program: Optional[str] = None
    vs_odbor: Optional[str] = None
    vs_stupen: Optional[str] = None
    vs_zaciatok: Optional[str] = None
    vs_koniec: Optional[str] = None
    vs_titul: Optional[str] = None
    zamestnanie_predch: Optional[str] = None
    zamestnanie_sucasne: Optional[str] = None
    suhlas_text: Optional[str] = None
    datum_vyplnenia: Optional[str] = None
    previous_university_study_asked: bool = Field(False, description="Flag indicating if the user was asked about previous study")

    muz_x: Optional[str] = None
    zena_x: Optional[str] = None
    skola_gym: Optional[str] = None
    skola_sos: Optional[str] = None
    skola_sou: Optional[str] = None
    skola_kom: Optional[str] = None
    skola_zss: Optional[str] = None
    skola_ina: Optional[str] = None

    d1: Optional[str] = None; d2: Optional[str] = None
    m1: Optional[str] = None; m2: Optional[str] = None
    r1: Optional[str] = None; r2: Optional[str] = None; r3: Optional[str] = None; r4: Optional[str] = None

    model_config = {"extra": "allow"}

    def missing_required_fields(self) -> list[str]:
        """
        Returns a list of unfilled important fields.
        Used by the LLM agent for Gap Analysis.
        The AI will ask the user until all these fields are filled.
        """
        missing: list[str] = []

        # ── personal_info ─────────────────────────────────────────────────
        pi = self.personal_info
        if pi is None:
            missing.append("personal_info (meno, priezvisko, dátum a miesto narodenia, rodné číslo, pohlavie, adresa, tel, email)")
        else:
            if not pi.first_name:
                missing.append("personal_info.first_name (Meno)")
            if not pi.last_name:
                missing.append("personal_info.last_name (Priezvisko)")
            if not pi.birth_date:
                missing.append("personal_info.birth_date (Dátum narodenia)")
            if not pi.birth_place:
                missing.append("personal_info.birth_place (Miesto narodenia)")
            if not pi.birth_country:
                missing.append("personal_info.birth_country (Štát narodenia)")
            if not pi.rodne_cislo:
                missing.append("personal_info.rodne_cislo (Rodné číslo)")
            if not pi.citizenship:
                missing.append("personal_info.citizenship (Štátne občianstvo)")
            if not pi.gender:
                missing.append("personal_info.gender (Pohlavie: M alebo F)")
            if not pi.phone:
                missing.append("personal_info.phone (Telefonné číslo)")
            if not pi.email:
                missing.append("personal_info.email (E-mail)")
                
            # Address checks
            addr = pi.permanent_address
            forn = pi.foreign_residence
            has_address = False
            if addr and (addr.street or addr.city):
                has_address = True
            if forn and (forn.street or forn.city):
                has_address = True
            if not has_address:
                missing.append("personal_info.permanent_address / foreign_residence (Adresa: ulica, mesto, PSČ)")

        # ── study_program ─────────────────────────────────────────────────
        sp = self.study_program
        if sp is None:
            missing.append("study_program (Vysoká škola, Fakulta, Program, Forma, Metóda)")
        else:
            if not sp.university:
                missing.append("study_program.university (Vysoká škola)")
            if not sp.faculty:
                missing.append("study_program.faculty (Fakulta)")
            if not sp.program:
                missing.append("study_program.program (Študijný program)")
            if not sp.form:
                missing.append("study_program.form (Forma štúdia: DENNÁ / EXTERNÁ)")
            if not sp.method:
                missing.append("study_program.method (Metóda štúdia: PREZENČNÁ / DIŠTANČNÁ / KOMBINOVANÁ)")

        # ── education ─────────────────────────────────────────────────────
        ed = self.education
        if ed is None:
            missing.append("education (Škola, Rok maturity, Študijný odbor)")
        else:
            if not ed.school_name:
                missing.append("education.school_name (Názov strednej školy)")
            if not ed.school_type:
                missing.append("education.school_type (Typ absolvovanej strednej školy: gymnázium / iná atď.)")
            if not ed.graduation_year:
                missing.append("education.graduation_year (Rok maturitnej skúšky)")
            if not ed.maturity_date:
                missing.append("education.maturity_date (Presný mesiac a rok maturitnej skúšky vo formáte MM/YYYY)")
            if not ed.study_field:
                missing.append("education.study_field (Študijný odbor)")

        # ── subjects and maturita ───────────────────────────────────────────
        if self.subjects is None:
            missing.append("subjects (Zoznam známok zo strednej školy za jednotlivé ročníky. Ak uchádzač nemá známky, odošli prázdny zoznam [])")
        
        if self.maturita_exams is None:
            missing.append("maturita_exams (Zoznam maturitných predmetov a ich výsledkov. Ak uchádzač ešte nematuroval alebo nemá výsledky, odošli prázdny zoznam [])")

        # ── previous study ────────────────────────────────────────
        if not self.previous_university_study_asked:
            missing.append("previous_university_study_asked (Opýtaj sa uchádzača, či už v minulosti študoval na nejakej inej vysokej škole, aj keď ju nedokončil)")
        
        return missing

    def is_complete(self) -> bool:
        """True if all critical fields are filled."""
        return len(self.missing_required_fields()) == 0

