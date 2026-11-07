import datetime as dt


def register_and_login(client, email="ada@example.com", password="correct-horse-battery"):
    assert client.post("/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def application_body(**overrides):
    body = {
        "company": "Acme",
        "role_title": "Junior Developer",
        "status": "applied",
        "applied_on": dt.date.today().isoformat(),
    }
    body.update(overrides)
    return body
