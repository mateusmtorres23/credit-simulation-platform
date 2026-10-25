from datetime import UTC, datetime
from unittest.mock import create_autospec

import pytest

from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService


@pytest.fixture
def session_context():
    repository = create_autospec(SessionRepository, instance=True)
    repository.find_active_by_id.return_value = None
    repository.find_active_by_token_hash.return_value = None
    now = datetime(2026, 10, 24, tzinfo=UTC)
    return repository, SessionService(repository, clock=lambda: now), now
