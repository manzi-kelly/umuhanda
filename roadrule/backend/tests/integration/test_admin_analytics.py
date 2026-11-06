from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.pdf_import import PdfImportJob
from app.models.refunds import RefundRequest
from app.services.exam_access import settle_mock
from tests.integration.test_exam_access import HEADERS, REDEEM, client_for, make_promo
from tests.integration.test_exam_bank import fixture_pdf, guest, submit
from tests.integration.test_exam_execution import begin, clock_at, prepared
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration


def test_analytics_use_persisted_records_and_require_admin(environment):
    admin, database, settings = environment
    _, token = guest(database, settings)
    path = "/api/v1/admin/analytics/overview"
    status = admin.get("/api/v1/admin/system").json()
    assert status["database"] == "HEALTHY"
    assert status["pdfWorker"]["status"] == "UNKNOWN"
    assert status["status"] == "DEGRADED"
    assert status["warnings"] == ["EXAM_BANK_UNAVAILABLE"]
    submit(environment, fixture_pdf(45))
    mock_settings = settings.model_copy(
        update={"mock_payments_enabled": True, "mock_exam_amount_rwf": 650}
    )
    with client_for(mock_settings, token) as client:
        assert client.get(path).status_code == 401
        assert client.get("/api/v1/admin/system").status_code == 401
        code = make_promo(admin, limit=2)["code"]
        for _ in range(2):
            assert client.post(REDEEM, headers=HEADERS, json={"code": code}).status_code == 200
        mock = client.post(
            "/api/v1/payments/mock/initiate",
            headers=HEADERS,
            json={"provider": "MTN", "idempotencyKey": str(uuid4())},
        )
        assert mock.status_code == 201
        payment_id = UUID(mock.json()["id"])
    with database.session_factory() as session:
        settle_mock(session, mock_settings, payment_id, "SUCCESSFUL")
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.add(RefundRequest(payment_id=payment_id, reason="Synthetic test case"))
    response = admin.get(path)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["students"]["records"] == data["students"]["uniqueIds"] == 1
    assert data["promos"]["generated"] == data["promos"]["redeemed"] == 1
    assert data["promos"]["remainingCapacity"] == 1
    assert data["payments"]["successful"] == data["payments"]["initiated"] == 1
    assert data["payments"]["simulatedSuccessfulRwf"] == 650
    assert data["payments"]["realVerifiedRevenue"] is None
    assert data["examinations"]["attempts"] == 0
    assert admin.get(path, params={"start": "2001-01-01"}).status_code == 422


@pytest.mark.parametrize("correct", [0, 12])
def test_exam_analytics_include_current_and_graded_attempts(environment, monkeypatch, correct):
    admin, database, settings = environment
    token, grant = prepared(environment)
    path = "/api/v1/admin/analytics/overview"
    with client_for(settings, token) as client:
        exam = begin(client, grant)
        stats = admin.get(path).json()["examinations"]
        assert stats["attempts"] == stats["active"] == 1
        assert stats["averageScore"] is None
        started, instant = clock_at(monkeypatch, exam)
        root = f"/api/v1/exams/{exam['id']}"
        for position in range(1, correct + 1):
            instant[0] = started + timedelta(seconds=position)
            assert (
                client.put(
                    root + "/answer",
                    headers=HEADERS,
                    json={"position": position, "optionId": 0, "answerVersion": 0},
                ).status_code
                == 200
            )
            assert (
                client.post(
                    root + "/next", headers=HEADERS, json={"position": position}
                ).status_code
                == 200
            )
        instant[0] = started + timedelta(minutes=21)
        assert client.get(root + "/result").status_code == 200
    stats = admin.get(path).json()["examinations"]
    assert stats["completed"] == 1
    assert stats["expired"] == int(correct == 0)
    assert stats["active"] == 0 and stats["averageScore"] == correct
    assert stats["passed"] == int(correct == 12)
    assert stats["failed"] == int(correct == 0)
    assert stats["passRate"] == (100 if correct == 12 else 0)
    assert stats["unanswered"] == 20 - correct
    _, replacement_job = submit(environment, fixture_pdf(2, variant="replacement"), process=False)
    with database.session_factory.begin() as session:
        job = session.get(PdfImportJob, replacement_job)
        job.status = "FAILED"
        job.completed_at = session.scalar(select(func.now()))
        job.failed_item_count = 1
    status = admin.get("/api/v1/admin/system").json()
    assert status["bank"]["counts"]["ELIGIBLE"] >= 20
    assert status["pdf"]["lastSuccessfulImport"] is not None
    assert status["pdf"]["jobs"]["FAILED"] == status["pdf"]["extractionErrors"] == 1
    assert status["status"] == "DEGRADED" and "PDF_IMPORT_ISSUES" in status["warnings"]
    assert status["pdfWorker"]["status"] == "UNKNOWN"
