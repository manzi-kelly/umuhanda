import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.models.exam_access import ExamEntitlement, PaymentTransaction, PromoCode
from app.models.exam_bank import BankRevision, ExamAttempt
from app.services.exam_access import AccessError, settle_mock, start_with_entitlement, verifier
from app.services.exam_generation import ExamUnavailable
from tests.integration.test_exam_bank import fixture_pdf, guest, submit
from tests.integration.test_pdf_import import environment as environment

pytestmark = pytest.mark.integration
ROOT = "/api/v1"
HEADERS = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}
PROMOS = ROOT + "/admin/promo-codes"
PAY = ROOT + "/payments/mock/initiate"
REDEEM = ROOT + "/promos/redeem"
ACCESS = ROOT + "/exam-access/me"


def client_for(settings, token):
    client = TestClient(create_app(settings), base_url="http://localhost")
    client.cookies.set(settings.guest_cookie_name, token)
    return client


def make_promo(admin, limit=1, code=None, hours=24):
    code = code or "QA-" + secrets.token_hex(8).upper()
    response = admin.post(
        PROMOS,
        headers=HEADERS,
        json={"code": code, "usageLimit": limit, "expiresInHours": hours},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["code"] == code.strip().upper()
    return created


def test_promo_issuance_scope_expiry_and_redemption_concurrency(environment):
    admin, database, settings = environment
    submit(environment, fixture_pdf(30))
    code = "ROAD-TEST-" + secrets.token_hex(8).upper()
    created = make_promo(admin, code=code.lower())
    assert created["code"] == code
    assert datetime.fromisoformat(created["expiresAt"]) - datetime.fromisoformat(
        created["createdAt"]
    ) == timedelta(hours=24)
    assert created["publishedAt"] is not None
    listing = admin.get(PROMOS).json()["items"][0]
    assert listing["status"] == "ACTIVE" and listing["code"] == code and "verifier" not in listing
    with database.session_factory() as session:
        row = session.get(PromoCode, UUID(created["id"]))
        assert row.code == code
        assert row.verifier == verifier(code)
        assert code not in row.verifier
    tokens = [guest(database, settings)[1] for _ in range(2)]

    def redeem(token):
        with client_for(settings, token) as client:
            return client.post(REDEEM, headers=HEADERS, json={"code": created["code"]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, tokens))
    assert sorted(r.status_code for r in results) == [200, 422]
    losing = next(r for r in results if r.status_code == 422)
    assert losing.json()["error"]["code"] == "PROMO_EXHAUSTED"
    winning = next(i for i, r in enumerate(results) if r.status_code == 200)
    assert redeem(tokens[winning]).json() == results[winning].json()
    with client_for(settings, tokens[1 - winning]) as client:
        assert not client.get(ACCESS).json()["entitlements"]
        assert (
            client.post(PROMOS, headers=HEADERS, json={"code": "ADMIN-ONLY"}).status_code == 401
        )
    assert admin.get(PROMOS).json()["items"][0]["status"] == "EXHAUSTED"
    assert len(admin.get(PROMOS + f"/{created['id']}/redemptions").json()) == 1


def test_admin_promo_management_duplicate_edit_enable_and_delete(environment):
    admin, database, settings = environment
    _, token = guest(database, settings)
    created = make_promo(admin, limit=2, code="VIP-2026")
    duplicate = admin.post(
        PROMOS, headers=HEADERS, json={"code": "vip-2026", "usageLimit": 1}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PROMO_DUPLICATE"
    invalid = admin.post(PROMOS, headers=HEADERS, json={"code": "bad code!", "usageLimit": 1})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "PROMO_CODE_INVALID"
    assert (
        admin.post(PROMOS, headers=HEADERS, json={"code": " ", "usageLimit": 1}).json()["error"][
            "code"
        ]
        == "PROMO_CODE_INVALID"
    )
    assert (
        admin.post(PROMOS, headers=HEADERS, json={"code": "", "usageLimit": 1}).json()["error"][
            "code"
        ]
        == "VALIDATION_ERROR"
    )
    expiry = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    edited = admin.patch(
        PROMOS + f"/{created['id']}",
        headers=HEADERS,
        json={"code": "vip-2027", "usageLimit": 3, "expiresAt": expiry},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["code"] == "VIP-2027"
    assert edited.json()["usageLimit"] == 3
    assert admin.patch(PROMOS + f"/{created['id']}", headers=HEADERS, json={}).status_code == 422
    disabled = admin.post(PROMOS + f"/{created['id']}/disable", headers=HEADERS)
    assert disabled.status_code == 200 and disabled.json()["status"] == "DISABLED"
    with client_for(settings, token) as client:
        rejected = client.post(REDEEM, headers=HEADERS, json={"code": "VIP-2027"})
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "PROMO_DISABLED"
    enabled = admin.post(PROMOS + f"/{created['id']}/enable", headers=HEADERS)
    assert enabled.status_code == 200 and enabled.json()["status"] == "ACTIVE"
    deleted = admin.delete(PROMOS + f"/{created['id']}", headers=HEADERS)
    assert deleted.status_code == 200 and deleted.json()["status"] == "DELETED"
    assert all(item["id"] != created["id"] for item in admin.get(PROMOS).json()["items"])
    with client_for(settings, token) as client:
        assert (
            client.post(REDEEM, headers=HEADERS, json={"code": "VIP-2027"}).json()["error"][
                "code"
            ]
            == "PROMO_INVALID"
        )
    recreated = make_promo(admin, code="VIP-2027")
    assert recreated["id"] != created["id"] and recreated["status"] == "ACTIVE"


def test_unpublished_promo_cannot_be_redeemed(environment):
    admin, database, settings = environment
    submit(environment, fixture_pdf(30))
    created = make_promo(admin, code="DRAFT-2026")
    with database.session_factory.begin() as session:
        session.execute(
            text("UPDATE promo_codes SET published_at = NULL WHERE id = :id"),
            {"id": UUID(created["id"])},
        )
    assert admin.get(PROMOS).json()["items"][0]["status"] == "DRAFT"
    _, token = guest(database, settings)
    with client_for(settings, token) as client:
        rejected = client.post(REDEEM, headers=HEADERS, json={"code": "DRAFT-2026"})
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "PROMO_NOT_PUBLISHED"


def test_invalid_disabled_expired_rate_limited_and_csrf(environment):
    admin, database, settings = environment
    _, token = guest(database, settings)
    disabled, expired = make_promo(admin), make_promo(admin)
    assert admin.post(PROMOS + f"/{disabled['id']}/disable", headers=HEADERS).status_code == 200
    with database.session_factory.begin() as session:
        session.execute(
            text(
                "UPDATE promo_codes SET created_at = created_at - interval '25 hours', "
                "expires_at = expires_at - interval '25 hours' WHERE id = :id"
            ),
            {"id": UUID(expired["id"])},
        )
    with client_for(settings, token) as client:
        assert client.post(REDEEM, json={"code": disabled["code"]}).status_code == 403
        cases = [
            (disabled["code"], "PROMO_DISABLED"),
            (expired["code"], "PROMO_EXPIRED"),
            *[("invalid", "PROMO_INVALID")] * 6,
        ]
        for code, reason in cases:
            rejected = client.post(REDEEM, headers=HEADERS, json={"code": code})
            assert rejected.status_code == 422
            assert rejected.json()["error"]["code"] == reason
        assert client.post(REDEEM, headers=HEADERS, json={"code": "invalid"}).status_code == 429
        assert client.get(ACCESS).json()["entitlements"] == []


def test_mock_initiation_concurrency_settlement_and_isolation(environment):
    _, database, settings = environment
    _, token = guest(database, settings)
    mock = settings.model_copy(update={"mock_payments_enabled": True, "mock_exam_amount_rwf": 650})
    key = str(uuid4())
    payload = {"provider": "MTN", "idempotencyKey": key}
    with client_for(settings, token) as client:
        assert client.post(PAY, headers=HEADERS, json=payload).status_code == 403
    with client_for(mock, token) as client:
        assert (
            client.post(PAY, headers=HEADERS, json=payload).json()["error"]["code"]
            == "EXAM_UNAVAILABLE"
        )
    submit(environment, fixture_pdf(30))

    def initiate(_):
        with client_for(mock, token) as client:
            result = client.post(PAY, headers=HEADERS, json=payload)
            assert result.status_code == 201, result.text
            return result.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        payments = list(pool.map(initiate, range(2)))
    assert payments[0] == payments[1]
    payment = payments[0]
    assert (payment["status"], payment["amount"], payment["currency"]) == ("PENDING", 650, "RWF")
    identifier = UUID(payment["id"])
    with client_for(mock, token) as client:
        assert client.get(ACCESS).json()["entitlements"] == []
        assert (
            client.post(PAY, headers=HEADERS, json={**payload, "status": "SUCCESSFUL"}).status_code
            == 422
        )
        assert (
            client.post(ROOT + f"/payments/{identifier}/success", headers=HEADERS).status_code
            == 404
        )
    _, other_token = guest(database, settings)
    with client_for(mock, other_token) as client:
        assert client.get(ROOT + f"/payments/{identifier}/status").status_code == 404

    def settle(_):
        with database.session_factory() as session:
            return settle_mock(session, mock, identifier, "SUCCESSFUL")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(row["status"] == "SUCCESSFUL" for row in pool.map(settle, range(2)))
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(PaymentTransaction)) == 1
        assert session.scalar(select(func.count()).select_from(ExamEntitlement)) == 1
    with database.session_factory() as session:
        with pytest.raises(AccessError, match="INVALID_PAYMENT_STATE"):
            settle_mock(session, mock, identifier, "FAILED")
    with client_for(mock, token) as client:
        assert client.get(ACCESS).json()["examReady"]


def test_production_guard_even_with_flag(environment):
    _, database, settings = environment
    production = settings.model_copy(
        update={"app_env": "production", "mock_payments_enabled": True}
    )
    assert not production.mock_allowed
    _, token = guest(database, settings)
    production = production.model_copy(update={"database_url": settings.test_database_url})
    with TestClient(create_app(production), base_url="https://localhost") as client:
        client.cookies.set(production.guest_cookie_name, token)
        response = client.post(
            PAY, headers=HEADERS, json={"provider": "MTN", "idempotencyKey": str(uuid4())}
        )
        assert response.status_code == 403 and response.json()["error"]["code"] == "MOCK_DISABLED"
    with database.session_factory() as session:
        with pytest.raises(AccessError, match="MOCK_DISABLED"):
            settle_mock(session, production, uuid4(), "SUCCESSFUL")


def test_unavailable_retains_grant_and_snapshot_consumption_is_idempotent(environment):
    admin, database, settings = environment
    _, token = guest(database, settings)
    created = make_promo(admin)
    with client_for(settings, token) as client:
        assert (
            client.post(REDEEM, headers=HEADERS, json={"code": created["code"]}).status_code == 503
        )
        assert admin.get(PROMOS).json()["items"][0]["used"] == 0
        submit(environment, fixture_pdf(30))
        response = client.post(REDEEM, headers=HEADERS, json={"code": created["code"]})
        assert response.status_code == 200
        identifier = UUID(response.json()["id"])
        with database.session_factory.begin() as session:
            active = session.scalar(select(BankRevision).where(BankRevision.active))
            revision = active.id
            active.active = False
        with database.session_factory() as session:
            assert isinstance(
                start_with_entitlement(session, settings, token, identifier), ExamUnavailable
            )
        state = client.get(ACCESS).json()
        assert not state["examReady"] and state["entitlements"][0]["status"] == "AVAILABLE"
        assert state["accessStatus"] == "ACTIVE" and state["bankReason"] == "NO_ACTIVE_BANK"
        assert state["entitlements"][0]["accessStatus"] == "ACTIVE"
    with database.session_factory.begin() as session:
        session.get(BankRevision, revision).active = True

    def start(_):
        with database.session_factory() as session:
            return start_with_entitlement(session, settings, token, identifier)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(start, range(2))
    assert first == second and len(first["questions"]) == 20
    with database.session_factory() as session:
        grant = session.get(ExamEntitlement, identifier)
        assert grant.status == "CONSUMED" and str(grant.attempt_id) == first["id"]
        assert session.scalar(select(func.count()).select_from(ExamAttempt)) == 1
    with pytest.raises(IntegrityError), database.session_factory.begin() as session:
        session.execute(text("UPDATE exam_entitlements SET status='AVAILABLE'"))


def test_settlement_rolls_back_when_entitlement_insert_fails(environment, monkeypatch):
    _, database, settings = environment
    submit(environment, fixture_pdf(30))
    mock = settings.model_copy(update={"mock_payments_enabled": True})
    _, token = guest(database, settings)
    with client_for(mock, token) as client:
        response = client.post(
            PAY, headers=HEADERS, json={"provider": "AIRTEL", "idempotencyKey": str(uuid4())}
        )
    assert response.status_code == 201
    identifier = UUID(response.json()["id"])

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic insert failure")

    monkeypatch.setattr("app.services.exam_access.ExamEntitlement", fail)
    with pytest.raises(RuntimeError), database.session_factory() as session:
        settle_mock(session, mock, identifier, "SUCCESSFUL")
    with database.session_factory() as session:
        assert session.get(PaymentTransaction, identifier).status == "PENDING"
        assert session.scalar(select(func.count()).select_from(ExamEntitlement)) == 0


def test_promo_request_contract_and_whitespace(environment):
    admin, database, settings = environment
    submit(environment, fixture_pdf(30))
    _, token = guest(database, settings)
    promo = make_promo(admin)
    with client_for(settings, token) as client:
        for body in (None, {}, {"promoCode": "placeholder"}, {"code": []}):
            response = client.post(REDEEM, headers=HEADERS, json=body)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        rejected = client.post(REDEEM, headers=HEADERS, json={"code": " "})
        assert rejected.status_code == 422 and rejected.json()["error"]["code"] == "PROMO_INVALID"
        valid = client.post(
            REDEEM, headers=HEADERS, json={"code": " " + promo["code"].lower() + " "}
        )
        assert valid.status_code == 200
        assert client.get(ACCESS).json()["entitlements"][0]["id"] == valid.json()["id"]
    with client_for(settings, token) as anonymous:
        anonymous.cookies.clear()
        assert (
            anonymous.post(REDEEM, headers=HEADERS, json={"code": promo["code"]}).status_code == 401
        )
