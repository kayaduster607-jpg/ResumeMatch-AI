import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger(__name__)


# ── Custom Exception Classes ──────────────────────────────────────

class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, code: str = "APP_ERROR", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class PDFParseError(AppException):
    def __init__(self, message: str = "Failed to parse PDF file"):
        super().__init__(message=message, code="PDF_PARSE_ERROR")


class ResumeExtractError(AppException):
    def __init__(self, message: str = "Failed to extract resume fields"):
        super().__init__(message=message, code="RESUME_EXTRACT_ERROR")


class JDParseError(AppException):
    def __init__(self, message: str = "Failed to parse job description"):
        super().__init__(message=message, code="JD_PARSE_ERROR")


class LLMCallError(AppException):
    def __init__(self, message: str = "LLM API call failed"):
        super().__init__(message=message, code="LLM_CALL_ERROR", status_code=502)


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource", resource_id: int = 0):
        super().__init__(
            message=f"{resource} with id {resource_id} not found",
            code="NOT_FOUND",
            status_code=404,
        )


# ── Exception Handlers (registered on app) ───────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "服务器内部错误"},
        )
