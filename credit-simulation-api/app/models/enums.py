from enum import StrEnum


class Bank(StrEnum):
    BANK_A = "bank_a"
    BANK_B = "bank_b"


class BankResultStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class BankErrorCode(StrEnum):
    TIMEOUT = "TIMEOUT"
    BANK_UNAVAILABLE = "BANK_UNAVAILABLE"
    INVALID_BANK_RESPONSE = "INVALID_BANK_RESPONSE"


class RejectionCode(StrEnum):
    INCOME_BELOW_MINIMUM = "INCOME_BELOW_MINIMUM"
    AMOUNT_ABOVE_LIMIT = "AMOUNT_ABOVE_LIMIT"
    TERM_NOT_SUPPORTED = "TERM_NOT_SUPPORTED"
    INSTALLMENT_ABOVE_MARGIN = "INSTALLMENT_ABOVE_MARGIN"
