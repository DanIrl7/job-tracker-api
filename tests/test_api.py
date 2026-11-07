import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from tests.helpers import application_body, register_and_login


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_returns_user_without_password(client):
    response = client.post("/auth/register", json={"email": "Ada@Example.com", "password": "long-enough-pass"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert "password" not in body and "password_hash" not in body


def test_password_is_stored_hashed(client, app):
    client.post("/auth/register", json={"email": "hash@example.com", "password": "long-enough-pass"})
    with Session(app.state.engine) as db:
        stored = db.scalar(select(User.password_hash).where(User.email == "hash@example.com"))
    assert stored.startswith("pbkdf2_sha256$")
    assert "long-enough-pass" not in stored


def test_duplicate_email_is_rejected(client):
    payload = {"email": "dup@example.com", "password": "long-enough-pass"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 409


def test_short_password_is_rejected(client):
    response = client.post("/auth/register", json={"email": "short@example.com", "password": "abc"})
    assert response.status_code == 422


def test_login_with_wrong_password_fails(client):
    client.post("/auth/register", json={"email": "wrong@example.com", "password": "long-enough-pass"})
    response = client.post("/auth/login", json={"email": "wrong@example.com", "password": "not-the-password"})
    assert response.status_code == 401


def test_endpoints_require_a_token(client):
    assert client.get("/applications").status_code == 401
    assert client.get("/applications", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_create_and_get_application(client, auth):
    created = client.post("/applications", json=application_body(notes="Referred by Sam"), headers=auth)
    assert created.status_code == 201
    app_id = created.json()["id"]
    fetched = client.get(f"/applications/{app_id}", headers=auth).json()
    assert fetched["company"] == "Acme"
    assert fetched["status"] == "applied"
    assert fetched["notes"] == "Referred by Sam"


def test_list_filters_by_status(client, auth):
    client.post("/applications", json=application_body(company="One"), headers=auth)
    client.post("/applications", json=application_body(company="Two", status="interviewing"), headers=auth)
    interviewing = client.get("/applications", params={"status": "interviewing"}, headers=auth).json()
    assert [a["company"] for a in interviewing] == ["Two"]


def test_patch_changes_only_sent_fields(client, auth):
    app_id = client.post("/applications", json=application_body(notes="keep me"), headers=auth).json()["id"]
    updated = client.patch(f"/applications/{app_id}", json={"status": "offer"}, headers=auth).json()
    assert updated["status"] == "offer"
    assert updated["notes"] == "keep me"


def test_patch_rejects_null_for_required_field(client, auth):
    app_id = client.post("/applications", json=application_body(), headers=auth).json()["id"]
    response = client.patch(f"/applications/{app_id}", json={"company": None}, headers=auth)
    assert response.status_code == 422


def test_invalid_status_is_rejected(client, auth):
    response = client.post("/applications", json=application_body(status="maybe"), headers=auth)
    assert response.status_code == 422


def test_delete_application(client, auth):
    app_id = client.post("/applications", json=application_body(), headers=auth).json()["id"]
    assert client.delete(f"/applications/{app_id}", headers=auth).status_code == 204
    assert client.get(f"/applications/{app_id}", headers=auth).status_code == 404


def test_users_cannot_see_or_change_each_others_applications(client):
    alice = register_and_login(client, email="alice@example.com")
    bob = register_and_login(client, email="bob@example.com")
    app_id = client.post("/applications", json=application_body(company="Alice Co"), headers=alice).json()["id"]

    assert client.get(f"/applications/{app_id}", headers=bob).status_code == 404
    assert client.patch(f"/applications/{app_id}", json={"status": "rejected"}, headers=bob).status_code == 404
    assert client.delete(f"/applications/{app_id}", headers=bob).status_code == 404
    assert client.get("/applications", headers=bob).json() == []

    still_there = client.get(f"/applications/{app_id}", headers=alice).json()
    assert still_there["status"] == "applied"


def test_follow_ups_lists_only_active_applications_due_soon(client, auth):
    today = dt.date.today()

    def add(company, status, follow_up):
        client.post(
            "/applications",
            json=application_body(company=company, status=status, follow_up_on=follow_up.isoformat()),
            headers=auth,
        )

    add("Due soon", "applied", today + dt.timedelta(days=2))
    add("Due later", "applied", today + dt.timedelta(days=30))
    add("Overdue", "applied", today - dt.timedelta(days=1))
    add("Rejected", "rejected", today + dt.timedelta(days=1))
    add("Interviewing", "interviewing", today)

    due = client.get("/applications/follow-ups", params={"days": 7}, headers=auth).json()
    assert [a["company"] for a in due] == ["Interviewing", "Due soon"]


def test_follow_ups_is_per_user(client):
    alice = register_and_login(client, email="f1@example.com")
    bob = register_and_login(client, email="f2@example.com")
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    client.post("/applications", json=application_body(follow_up_on=tomorrow), headers=alice)
    assert client.get("/applications/follow-ups", headers=bob).json() == []
