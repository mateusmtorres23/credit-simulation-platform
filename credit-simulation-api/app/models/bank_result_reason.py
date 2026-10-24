from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.bank_result import BankResult
from app.models.enums import RejectionCode


class BankResultReason(Base):
    __tablename__ = "bank_result_reasons"
    __table_args__ = (
        UniqueConstraint(
            "bank_result_id", "code", name="uq_bank_result_reasons_result_code"
        ),
        UniqueConstraint(
            "bank_result_id", "position", name="uq_bank_result_reasons_result_position"
        ),
        CheckConstraint(
            "position >= 0", name="ck_bank_result_reasons_position_nonnegative"
        ),
        CheckConstraint(
            "message ~ '[^[:space:]]'", name="ck_bank_result_reasons_message_not_blank"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    bank_result_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("bank_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[RejectionCode] = mapped_column(
        Enum(
            RejectionCode,
            name="rejection_code_enum",
            values_callable=lambda enum: [member.value for member in enum],
            validate_strings=True,
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    bank_result: Mapped[BankResult] = relationship(
        back_populates="reasons", lazy="raise"
    )
