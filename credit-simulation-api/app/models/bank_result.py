from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Bank, BankErrorCode, BankResultStatus
from app.models.simulation import Simulation

if TYPE_CHECKING:
    from app.models.bank_result_reason import BankResultReason


class BankResult(Base):
    __tablename__ = "bank_results"
    __table_args__ = (
        UniqueConstraint(
            "simulation_id", "bank", name="uq_bank_results_simulation_bank"
        ),
        CheckConstraint(
            "(status = 'approved' AND amount_cents IS NOT NULL "
            "AND term_months IS NOT NULL AND monthly_interest_rate_bps IS NOT NULL "
            "AND installment_cents IS NOT NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'rejected' AND amount_cents IS NULL "
            "AND term_months IS NULL AND monthly_interest_rate_bps IS NULL "
            "AND installment_cents IS NULL "
            "AND error_code IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND amount_cents IS NULL "
            "AND term_months IS NULL AND monthly_interest_rate_bps IS NULL "
            "AND installment_cents IS NULL "
            "AND error_code IS NOT NULL AND error_message IS NOT NULL)",
            name="ck_bank_results_status_fields",
        ),
        CheckConstraint(
            "amount_cents BETWEEN 1 AND 9007199254740991",
            name="ck_bank_results_amount_cents_range",
        ),
        CheckConstraint(
            "term_months BETWEEN 1 AND 120", name="ck_bank_results_term_months_range"
        ),
        CheckConstraint(
            "monthly_interest_rate_bps BETWEEN 0 AND 9007199254740991",
            name="ck_bank_results_monthly_interest_rate_bps_range",
        ),
        CheckConstraint(
            "installment_cents BETWEEN 1 AND 9007199254740991",
            name="ck_bank_results_installment_cents_range",
        ),
        CheckConstraint(
            "error_message ~ '[^[:space:]]'",
            name="ck_bank_results_error_message_not_blank",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    simulation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    bank: Mapped[Bank] = mapped_column(
        Enum(
            Bank,
            name="bank_enum",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[BankResultStatus] = mapped_column(
        Enum(
            BankResultStatus,
            name="bank_result_status_enum",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    term_months: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    monthly_interest_rate_bps: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    installment_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_code: Mapped[BankErrorCode | None] = mapped_column(
        Enum(
            BankErrorCode,
            name="bank_error_code_enum",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    simulation: Mapped[Simulation] = relationship(
        back_populates="bank_results", lazy="raise"
    )
    reasons: Mapped[list["BankResultReason"]] = relationship(
        back_populates="bank_result",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        order_by="BankResultReason.position",
    )
