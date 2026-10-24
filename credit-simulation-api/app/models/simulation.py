from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.session import Session

if TYPE_CHECKING:
    from app.models.bank_result import BankResult


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "monthly_income_cents BETWEEN 1 AND 9007199254740991",
            name="ck_simulations_monthly_income_cents_range",
        ),
        CheckConstraint(
            "requested_amount_cents BETWEEN 100 AND 9007199254740991",
            name="ck_simulations_requested_amount_cents_range",
        ),
        CheckConstraint(
            "term_months BETWEEN 1 AND 120", name="ck_simulations_term_months_range"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    session_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    monthly_income_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requested_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    term_months: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    session: Mapped[Session] = relationship(back_populates="simulations", lazy="raise")
    bank_results: Mapped[list["BankResult"]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="BankResult.bank",
    )


Index(
    "ix_simulations_session_created_at_id",
    Simulation.session_id,
    Simulation.created_at.desc(),
    Simulation.id.desc(),
)
