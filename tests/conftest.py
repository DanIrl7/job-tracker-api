import os

import pytest
from fastapi.testclient import TestClient

from app.db import Base
from app.main import create_app
from tests.helpers import register_and_login

TEST_SECRET = "test-secret-key-that-is-long-enough-123456"


@pytest.fixture
def app(tmp_path):
    # CI sets DATABASE_URL to a real PostgreSQL server. Locally, each test gets a fresh SQLite file.
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    application = create_app(database_url=url, secret_key=TEST_SECRET)
    Base.metadata.drop_all(application.state.engine)
    Base.metadata.create_all(application.state.engine)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth(client):
    return register_and_login(client)
