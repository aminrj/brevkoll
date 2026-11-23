from pydantic import ValidationError


class AppError(Exception):
    """An error with a fixed, safe message. Never put letter or model text in it."""

    status_code: int = 500
    message: str = "Internal error"

    def __init__(self) -> None:
        super().__init__(self.message)


class UnsupportedMedia(AppError):
    status_code = 415
    message = "Unsupported file type. Use PNG, JPEG or PDF."


class TooLarge(AppError):
    status_code = 413
    message = "File too large."


class BadLanguage(AppError):
    status_code = 422
    message = "Unsupported language."


class InvalidRequest(AppError):
    status_code = 422
    message = "Invalid request."


class BadModelOutput(AppError):
    status_code = 502
    message = "The model returned an unusable answer."

    @staticmethod
    def _detail_from_validation(exc: ValidationError) -> str:
        """Build a safe detail string from a Pydantic ValidationError.

        The Pydantic *str* representation includes the raw input value,
        which may contain model text.  Instead we extract only the error
        type (e.g. *missing*, *string_type*) which is a static label
        safe to show.
        """
        parts: list[str] = []
        for err in exc.errors():
            parts.append(err.get("type", "invalid"))
        return "; ".join(sorted(set(parts))) if parts else "validation_failed"

    def __init__(self, detail: str | ValidationError | None = None) -> None:
        super().__init__()
        if isinstance(detail, ValidationError):
            detail = self._detail_from_validation(detail)
        if detail is not None:
            self.message = f"{self.message} {detail}"


class ModelOutOfTokens(AppError):
    """The model stopped at the token cap, usually a thinking model whose reasoning used the whole
    budget (brevkoll#36: every letter failed with 'unusable answer' at a cap of 600). The message
    names the setting, never the model's text."""

    status_code = 502
    message = (
        "The model ran out of room before it finished answering. "
        "The operator needs to raise MODEL_MAX_TOKENS."
    )


class ModelUnavailable(AppError):
    status_code = 502
    message = "The model is unavailable."


class OcrFailed(AppError):
    status_code = 502
    message = "Could not read the letter."


class OcrBusy(AppError):
    status_code = 503
    message = "Busy. Try again in a moment."


class RateLimited(AppError):
    status_code = 429
    message = "Too many requests."


class BudgetExhausted(AppError):
    status_code = 503
    message = "Daily capacity reached. Try again tomorrow."
