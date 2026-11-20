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


class ModelUnavailable(AppError):
    status_code = 502
    message = "The model is unavailable."


class OcrFailed(AppError):
    status_code = 502
    message = "Could not read the letter."


class RateLimited(AppError):
    status_code = 429
    message = "Too many requests."


class BudgetExhausted(AppError):
    status_code = 503
    message = "Daily capacity reached. Try again tomorrow."
