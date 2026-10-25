import argparse
import asyncio
import sys
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import create_database_engine, create_session_factory
from app.repositories.session_repository import SessionRepository


async def cleanup_expired_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Own one cleanup transaction; equality with expires_at is expired.

    The supplied session must have no active transaction. The cutoff comes
    from the server, never from a browser, and valid sessions are preserved.
    """
    cutoff = now if now is not None else datetime.now(UTC)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Cleanup time must include a timezone.")
    async with db.begin():
        count = await SessionRepository(db).delete_expired(now=cutoff.astimezone(UTC))
    return count


async def run_cleanup(settings: Settings) -> int:
    engine = create_database_engine(settings)
    try:
        async with create_session_factory(engine)() as db:
            return await cleanup_expired_sessions(db)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove expired anonymous sessions and their saved simulations."
    )
    parser.parse_args()
    try:
        # BaseSettings obtains required fields from environment variables or .env.
        settings = Settings()  # pyright: ignore[reportCallIssue]
        count = asyncio.run(run_cleanup(settings))
    except (ValidationError, SQLAlchemyError, OSError):
        print(
            "Não foi possível concluir a limpeza. Verifique a configuração e o banco.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        return 130
    print(f"Sessões expiradas removidas: {count}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
