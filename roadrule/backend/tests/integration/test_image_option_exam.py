from uuid import UUID

import pymupdf
import pytest
from sqlalchemy import func, select

from app.models.exam_bank import BankQuestion, BankRevision
from tests.integration.test_exam_access import HEADERS, REDEEM, client_for, make_promo
from tests.integration.test_exam_bank import guest, submit
from tests.integration.test_exam_execution import begin
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration


def vector_option_bank():
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 38), "RESTRICTED")
        page.insert_text((40, 55), "IKINYARWANDA")
        page.insert_text((40, 76), "1. Synthetic road sign options")
        for index, label in enumerate(("a)", "b)", "(c)", "d)")):
            y = 145 + index * 76
            page.insert_text((40, y), label)
            page.draw_rect(pymupdf.Rect(68, y - 36, 100 + 3 * index, y - 1))
        for number in range(2, 21):
            if number >= 4 and (number - 4) % 6 == 0:
                page = pdf.new_page()
            y = 435 + 60 * (number - 2) if number < 4 else 45 + 115 * ((number - 4) % 6)
            page.insert_text((40, y), f"{number}. Synthetic text question {number}")
            page.insert_text((40, y + 18), f"(a) First choice {number}")
            page.insert_text((40, y + 36), "b) Second choice")
        return pdf.tobytes()


def test_vector_choices_activate_and_use_current_question_media(environment):
    admin, database, settings = environment
    document, _ = submit(environment, vector_option_bank())
    with database.session_factory() as db:
        revision = db.scalar(select(BankRevision).where(BankRevision.document_id == UUID(document)))
        assert revision.active and revision.status == "READY"
        assert revision.counts["image_only_options"] == 4
        assert (
            db.scalar(select(func.count()).select_from(BankRevision).where(BankRevision.active))
            == 1
        )
        sign = db.scalar(
            select(BankQuestion).where(
                BankQuestion.revision_id == revision.id,
                BankQuestion.category == "ROAD_SIGN",
            )
        )
        assert [asset["option_label"] for asset in sign.assets] == list("ABCD")
        assert sign.correct_index == 2
    _, token = guest(database, settings)
    code = make_promo(admin)["code"]
    with client_for(settings, token) as student:
        grant = student.post(REDEEM, headers=HEADERS, json={"code": code}).json()["id"]
        exam = begin(student, grant)
        assert exam["total"] == 20
        while exam["question"] and not any(
            "image" in option for option in exam["question"]["options"]
        ):
            exam = student.post(
                f"/api/v1/exams/{exam['id']}/next",
                headers=HEADERS,
                json={"position": exam["position"]},
            ).json()["exam"]
        question = exam["question"]
        assert question is not None and question["images"] == []
        assert [option["label"] for option in question["options"]] == list("ABCD")
        assert all(
            set(option) == {"id", "label", "text", "image"} for option in question["options"]
        )
        for option in question["options"]:
            response = student.get("/api/v1/" + option["image"])
            assert response.status_code == 200 and response.content.startswith(b"\x89PNG")
