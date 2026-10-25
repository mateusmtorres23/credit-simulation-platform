import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.models.session import Session
from app.repositories.session_repository import SessionRepository

SESSION_LIFETIME = timedelta(days=7)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}", flags=re.ASCII)


@dataclass(frozen=True)
class PreparedSession:
    """A staged session; disclose a new token only after the caller commits."""

    session: Session
    new_token: str | None = field(default=None, repr=False)


def _as_utc(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Session time must include a timezone.")
    return now.astimezone(UTC)


class SessionService:
    """Manage anonymous credentials without HTTP or transaction ownership.

    The caller supplies server time and owns the repository's transaction.
    Finish any lookup transaction before awaiting external bank responses.
    """

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    async def find_active(self, token: str | None, *, now: datetime) -> Session | None:
        """Resolve a browser credential without creating or renewing a session."""
        now = _as_utc(now)
        if token is None or TOKEN_PATTERN.fullmatch(token) is None:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        return await self._repository.find_active_by_token_hash(token_hash, now=now)

    async def revalidate_for_write(
        self, session_id: UUID, *, now: datetime
    ) -> Session | None:
        """Refresh and lock an existing session in the caller's write transaction."""
        return await self._repository.find_active_by_id(
            session_id, now=_as_utc(now), for_update=True
        )

    async def prepare_for_simulation(
        self, session_id: UUID | None, *, now: datetime
    ) -> PreparedSession:
        """Reuse a valid session or stage a replacement after bank evaluations.

        Use this same server instant for the simulation's created_at. A new
        session and its simulation must be saved in one transaction. Failure
        must not publish the new token; this method does not confirm any write.
        """
        now = _as_utc(now)
        if session_id is not None:
            session = await self.revalidate_for_write(session_id, now=now)
            if session is not None:
                return PreparedSession(session=session)

        token = secrets.token_urlsafe(32)
        session = Session(
            id=uuid4(),
            token_hash=hashlib.sha256(token.encode("utf-8")).digest(),
            created_at=now,
            expires_at=now + SESSION_LIFETIME,
        )
        self._repository.add(session)
        return PreparedSession(session=session, new_token=token)
