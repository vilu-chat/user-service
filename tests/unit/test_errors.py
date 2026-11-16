from app.errors import (
    AccountDeletedError,
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
)


def test_status_codes():
    assert InvalidRequestError.status_code == 400
    assert ForbiddenError.status_code == 403
    assert NotFoundError.status_code == 404
    assert ConflictError.status_code == 409
    assert AccountDeletedError.status_code == 403


def test_account_deleted_has_a_stable_error_code():
    error = AccountDeletedError()
    assert isinstance(error, ForbiddenError) and isinstance(error, DomainError)
    assert error.error_code == "account_deleted"
    assert ForbiddenError("x").error_code is None
