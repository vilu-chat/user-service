from http import HTTPStatus

from flask import jsonify


class DomainError(Exception):
    """Raised by services; mapped to flask-smorest's error format (code, status, message).

    Errors that clients must tell apart from other errors with the same HTTP status also carry
    a stable `error_code` string in the body.
    """

    status_code = 400
    error_code: str | None = None

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRequestError(DomainError):
    status_code = 400


class ForbiddenError(DomainError):
    status_code = 403


class NotFoundError(DomainError):
    status_code = 404


class ConflictError(DomainError):
    status_code = 409


class AccountDeletedError(ForbiddenError):
    error_code = "account_deleted"

    def __init__(self, message: str = "This account has been deleted.") -> None:
        super().__init__(message)


def register_error_handlers(app) -> None:
    @app.errorhandler(DomainError)
    def handle_domain_error(error: DomainError):
        status = HTTPStatus(error.status_code)
        body = {"code": status.value, "status": status.phrase, "message": error.message}
        if error.error_code:
            body["error_code"] = error.error_code
        return jsonify(body), status.value
