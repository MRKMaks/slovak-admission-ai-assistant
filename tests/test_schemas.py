"""
Unit tests for Pydantic schemas in form.py (Stage 2).
"""

import pytest
from pydantic import ValidationError

from app.schemas.form import (
    Address,
    ApplicationForm,
    EducationInfo,
    GradeRecord,
    MaturitySubject,
    PersonalInfo,
    StudyProgramInfo,
)

# Address

class TestAddress:
    def test_valid_minimal(self):
        addr = Address(street="Hlavná 1", city="Bratislava", postal_code="81101", country="SK")
        assert addr.city == "Bratislava"

    def test_optional_district(self):
        addr = Address(street="Dlhá 5", city="Košice", postal_code="04001", country="SK")
        assert addr.district is None

    def test_with_district(self):
        addr = Address(street="Moyzesova 3", city="Trnava", postal_code="91701", country="SK", district="Trnava")
        assert addr.district == "Trnava"



# PersonalInfo

class TestPersonalInfo:
    def test_valid_full(self):
        info = PersonalInfo(
            first_name="Ján",
            last_name="Novák",
            birth_date="1999-05-15",
            birth_place="Bratislava",
            birth_country="SK",
            rodne_cislo="990515/1234",
            gender="M",
            permanent_address=Address(street="Hlavná 1", city="Bratislava", postal_code="81101", country="SK"),
        )
        assert info.first_name == "Ján"

    def test_email_validation(self):
        with pytest.raises(ValidationError):
            PersonalInfo(
                first_name="X",
                last_name="Y",
                birth_date="2000-01-01",
                birth_place="Košice",
                birth_country="SK",
                gender="M",
                permanent_address=Address(street="A 1", city="Košice", postal_code="04001", country="SK"),
                email="not-an-email",
            )

    def test_gender_literal(self):
        with pytest.raises(ValidationError):
            PersonalInfo(
                first_name="X",
                last_name="Y",
                birth_date="2000-01-01",
                birth_place="Košice",
                birth_country="SK",
                gender="OTHER",
                permanent_address=Address(street="A 1", city="Košice", postal_code="04001", country="SK"),
            )



# StudyProgramInfo — normalization and Literal check

class TestStudyProgramInfo:
    def _base(self, **kw) -> dict:
        return {
            "university": "Univerzita Komenského v Bratislave",
            "faculty": "Fakulta matematiky, fyziky a informatiky",
            "program": "informatika",
            "form": "DENNÁ",
            "method": "PREZENČNÁ",
            **kw,
        }

    def test_fields_uppercased(self):
        sp = StudyProgramInfo(**self._base())
        assert sp.university == "UNIVERZITA KOMENSKÉHO V BRATISLAVE"
        assert sp.faculty == "FAKULTA MATEMATIKY, FYZIKY A INFORMATIKY"
        assert sp.program == "INFORMATIKA"

    def test_already_uppercase_unchanged(self):
        sp = StudyProgramInfo(**self._base(program="INFORMATIKA"))
        assert sp.program == "INFORMATIKA"

    def test_invalid_form_literal(self):
        with pytest.raises(ValidationError):
            StudyProgramInfo(**self._base(form="DIAĽKOVÁ"))

    def test_invalid_method_literal(self):
        with pytest.raises(ValidationError):
            StudyProgramInfo(**self._base(method="ONLINE"))

    def test_valid_externa_form(self):
        sp = StudyProgramInfo(**self._base(form="EXTERNÁ", method="DIŠTANČNÁ"))
        assert sp.form == "EXTERNÁ"
        assert sp.method == "DIŠTANČNÁ"

    def test_valid_kombinovana_method(self):
        sp = StudyProgramInfo(**self._base(method="KOMBINOVANÁ"))
        assert sp.method == "KOMBINOVANÁ"

    def test_foreign_language_optional(self):
        sp = StudyProgramInfo(**self._base())
        assert sp.foreign_language_exam is None

    def test_foreign_language_set(self):
        sp = StudyProgramInfo(**self._base(foreign_language_exam="anglický jazyk"))
        assert sp.foreign_language_exam == "anglický jazyk"



# EducationInfo — normalization and nested Address

class TestEducationInfo:
    def _addr(self) -> dict:
        return {"street": "Školská 1", "city": "Nitra", "postal_code": "94901", "country": "SK"}

    def _base(self, **kw) -> dict:
        return {
            "graduation_year": "2022",
            "school_name": "Gymnázium Jura Hronca",
            "school_address": self._addr(),
            "study_field": "matematika",
            **kw,
        }

    def test_school_name_uppercased(self):
        ed = EducationInfo(**self._base())
        assert ed.school_name == "GYMNÁZIUM JURA HRONCA"

    def test_study_field_uppercased(self):
        ed = EducationInfo(**self._base())
        assert ed.study_field == "MATEMATIKA"

    def test_optional_school_code(self):
        ed = EducationInfo(**self._base())
        assert ed.school_code is None

    def test_school_code_set(self):
        ed = EducationInfo(**self._base(school_code="712001"))
        assert ed.school_code == "712001"

    def test_optional_field_code(self):
        ed = EducationInfo(**self._base())
        assert ed.field_code is None

    def test_nested_address_parsed(self):
        ed = EducationInfo(**self._base())
        assert ed.school_address.city == "Nitra"



# GradeRecord — grades by year

class TestGradeRecord:
    def test_valid(self):
        gr = GradeRecord(subject="Matematika", grade_year1=1.5, grade_year2=1.8)
        assert gr.subject == "Matematika"

    def test_all_years_optional(self):
        gr = GradeRecord(subject="Fyzika")
        assert gr.grade_year1 is None
        assert gr.grade_year6 is None



# MaturitySubject

class TestMaturitySubject:
    def test_valid(self):
        ms = MaturitySubject(
            subject="Matematika",
            level="B",
            external_pct=72.5,
            external_percentile=65.0,
            internal_written_pct=80.0,
            internal_oral_grade=2,
        )
        assert ms.subject == "Matematika"

    def test_all_scores_optional(self):
        ms = MaturitySubject(subject="Slovenský jazyk")
        assert ms.external_pct is None



# ApplicationForm — root model, partial filling

class TestApplicationForm:
    def test_empty_form_valid(self):
        """Root model should accept completely empty data (dialog filling)."""
        form = ApplicationForm()
        assert form.personal_info is None
        assert form.study_program is None
        assert form.education is None

    def test_partial_form_valid(self):
        form = ApplicationForm(
            study_program=StudyProgramInfo(
                university="UK",
                faculty="FMFI",
                program="Informatika",
                form="DENNÁ",
                method="PREZENČNÁ",
            )
        )
        assert form.study_program is not None
        assert form.personal_info is None

    def test_full_form_valid(self):
        addr = Address(street="Hlavná 1", city="Bratislava", postal_code="81101", country="SK")
        form = ApplicationForm(
            personal_info=PersonalInfo(
                first_name="Anna",
                last_name="Kováčová",
                birth_date="2001-03-12",
                birth_place="Nitra",
                birth_country="SK",
                gender="F",
                permanent_address=addr,
            ),
            study_program=StudyProgramInfo(
                university="Univerzita Komenského",
                faculty="Lekárska fakulta",
                program="Všeobecné lekárstvo",
                form="DENNÁ",
                method="PREZENČNÁ",
            ),
            education=EducationInfo(
                graduation_year="2019",
                school_name="Gymnázium Golianova",
                school_address=addr,
                study_field="biológia",
            ),
        )
        assert form.personal_info.last_name == "Kováčová"
        assert form.study_program.university == "UNIVERZITA KOMENSKÉHO"
        assert form.education.study_field == "BIOLÓGIA"
