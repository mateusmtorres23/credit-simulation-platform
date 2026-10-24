from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.simulation import Simulation


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        CheckConstraint(
            "octet_length(token_hash) = 32", name="ck_sessions_token_hash_length"
        ),
        CheckConstraint(
            "expires_at > created_at", name="ck_sessions_expiration_after_creation"
        ),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    simulations: Mapped[list["Simulation"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
