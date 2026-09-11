"""Center adapter for Dee's read-only Gmail interface."""

from dee_klutter import (
    AuthenticationError,
    DeeGmailError,
    GmailApiError,
    InvalidAccountError,
    InvalidRequestError,
    MalformedResponseError,
    NotFoundError,
    PaginationError,
    RateLimitError,
    get_message,
    get_thread,
    search_gmail,
)

OPERATIONS = {"search_gmail", "get_message", "get_thread"}
DEE_ERRORS = (
    DeeGmailError,
    AuthenticationError,
    InvalidAccountError,
    InvalidRequestError,
    GmailApiError,
    RateLimitError,
    NotFoundError,
    MalformedResponseError,
    PaginationError,
)


def _result(ok: bool, operation, account, data=None, error=None) -> dict:
    return {
        "ok": ok,
        "operation": operation,
        "account": account,
        "data": data,
        "error": error,
    }


def _error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _request_from_task(task: dict) -> dict:
    metadata = task.get("metadata") if isinstance(task, dict) else None
    if not isinstance(metadata, dict):
        raise InvalidRequestError("task metadata must contain a Gmail request")
    request = metadata.get("gmail_request", metadata)
    if not isinstance(request, dict):
        raise InvalidRequestError("gmail_request must be an object")
    return request


def _validate_request(request: dict) -> tuple[str, str]:
    operation = request.get("operation")
    account = request.get("account")
    if operation not in OPERATIONS:
        raise InvalidRequestError("unsupported Gmail operation")
    if not isinstance(account, str) or not account.strip():
        raise InvalidRequestError("account is required")
    if operation == "search_gmail":
        if not isinstance(request.get("query"), str) or not request["query"].strip():
            raise InvalidRequestError("query is required for search_gmail")
        if "max_results" in request and (
            not isinstance(request["max_results"], int)
            or isinstance(request["max_results"], bool)
        ):
            raise InvalidRequestError("max_results must be an integer")
    elif operation == "get_message":
        if not isinstance(request.get("message_id"), str) or not request["message_id"].strip():
            raise InvalidRequestError("message_id is required for get_message")
    elif operation == "get_thread":
        if not isinstance(request.get("thread_id"), str) or not request["thread_id"].strip():
            raise InvalidRequestError("thread_id is required for get_thread")
    return operation, account


def handle_task(task: dict) -> dict:
    operation = None
    account = None
    try:
        request = _request_from_task(task)
        operation, account = _validate_request(request)

        if operation == "search_gmail":
            data = search_gmail(
                query=request["query"],
                account=account,
                max_results=request.get("max_results", 20),
            )
        elif operation == "get_message":
            data = get_message(message_id=request["message_id"], account=account)
        else:
            data = get_thread(thread_id=request["thread_id"], account=account)
        return _result(True, operation, account, data=data)
    except DEE_ERRORS as exc:
        return _result(
            False,
            operation,
            account,
            error=_error(getattr(exc, "code", "gmail_error"), str(exc)),
        )
    except Exception:
        return _result(
            False,
            operation,
            account,
            error=_error("adapter_error", "Unable to complete the Gmail request"),
        )
