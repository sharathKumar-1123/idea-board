import os
import tempfile

import pytest

# Must be set before the app (and its engine) is imported.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/idea-board-test-{os.getpid()}.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
