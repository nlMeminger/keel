import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

AccountType = Literal[
    "checking", "savings", "credit_card", "investment", "loan", "mortgage", "student_loan"
]


class CheckingDetail(BaseModel):
    overdraft_limit: float | None = None


class SavingsDetail(BaseModel):
    interest_rate: float | None = None


class CreditCardDetail(BaseModel):
    credit_limit: float
    apr: float | None = None


class InvestmentDetail(BaseModel):
    account_subtype: str | None = None


class LoanDetail(BaseModel):
    principal: float
    interest_rate: float | None = None
    term_months: int | None = None


class MortgageDetail(BaseModel):
    principal: float
    interest_rate: float | None = None
    term_months: int | None = None
    escrow_balance: float | None = None


class StudentLoanDetail(BaseModel):
    principal: float
    interest_rate: float | None = None
    servicer: str | None = None


_DETAIL_SCHEMAS: dict[str, type[BaseModel]] = {
    "checking": CheckingDetail,
    "savings": SavingsDetail,
    "credit_card": CreditCardDetail,
    "investment": InvestmentDetail,
    "loan": LoanDetail,
    "mortgage": MortgageDetail,
    "student_loan": StudentLoanDetail,
}


def validate_detail_for_type(account_type: str, detail: dict[str, object]) -> dict[str, object]:
    """Validates `detail` against its account_type's schema, raising ValueError on mismatch."""
    schema = _DETAIL_SCHEMAS[account_type]
    try:
        validated = schema.model_validate(detail)
    except ValidationError as exc:
        raise ValueError(f"detail is invalid for account_type '{account_type}': {exc}") from exc
    return validated.model_dump(mode="json")


class AccountCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    account_type: AccountType
    balance: Decimal = Field(ge=0)
    detail: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_detail(self) -> "AccountCreateRequest":
        self.detail = validate_detail_for_type(self.account_type, self.detail)
        return self


class AccountUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    account_type: AccountType | None = None
    balance: Decimal | None = Field(default=None, ge=0)
    detail: dict[str, object] | None = None


class AccountPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    account_type: str
    balance: Decimal
    detail: dict[str, object]
    is_active: bool
    is_plaid_linked: bool
    created_at: datetime
    updated_at: datetime
