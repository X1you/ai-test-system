#!/usr/bin/env python3
"""
统一异常层次结构 — 错误码 + 分类 + HTTP 状态映射

所有业务异常继承 AppError，携带：
  - error_code: 机器可读的错误码（如 PIPELINE_NOT_FOUND）
  - message: 人类可读的错误描述
  - status_code: 对应的 HTTP 状态码
  - detail: 额外上下文信息（可选）
"""


class AppError(Exception):
    """应用异常基类"""

    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str = "", detail: str | None = None):
        self.message = message or self.error_code
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """转换为 API 响应 dict"""
        result = {
            "error": self.error_code,
            "detail": self.message,
        }
        if self.detail:
            result["extra_detail"] = self.detail
        return result


class PipelineNotFoundError(AppError):
    error_code = "PIPELINE_NOT_FOUND"
    status_code = 404

    def __init__(self, pipeline_id: str):
        super().__init__(f"Pipeline 不存在: {pipeline_id}")


class LLMTimeoutError(AppError):
    error_code = "LLM_TIMEOUT"
    status_code = 504

    def __init__(self, provider: str = "", detail: str | None = None):
        super().__init__(f"LLM 调用超时: {provider}" if provider else "LLM 调用超时", detail)


class LLMUnavailableError(AppError):
    error_code = "LLM_UNAVAILABLE"
    status_code = 503

    def __init__(self, detail: str | None = None):
        super().__init__("所有 LLM Provider 均不可用", detail)


class ValidationError(AppError):
    error_code = "VALIDATION_ERROR"
    status_code = 400

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(message, detail)


class FileSizeExceededError(AppError):
    error_code = "FILE_SIZE_EXCEEDED"
    status_code = 400

    def __init__(self, max_size: str = "10MB"):
        super().__init__(f"文件过大（>{max_size}）")


class ConcurrencyLimitError(AppError):
    error_code = "CONCURRENCY_LIMIT"
    status_code = 429

    def __init__(self):
        super().__init__("并发任务已达上限，请等待现有任务完成")


class AuthenticationError(AppError):
    error_code = "AUTHENTICATION_FAILED"
    status_code = 401

    def __init__(self, message: str = "认证失败"):
        super().__init__(message)


class AuthorizationError(AppError):
    error_code = "AUTHORIZATION_FAILED"
    status_code = 403

    def __init__(self, message: str = "权限不足"):
        super().__init__(message)


# ─── 错误码注册表 ───

ERROR_REGISTRY: dict[str, type[AppError]] = {
    cls.error_code: cls
    for cls in [
        PipelineNotFoundError,
        LLMTimeoutError,
        LLMUnavailableError,
        ValidationError,
        FileSizeExceededError,
        ConcurrencyLimitError,
        AuthenticationError,
        AuthorizationError,
    ]
}


def app_error_handler(request, exc: AppError):
    """FastAPI 异常处理器 — 将 AppError 转换为标准 JSON 响应"""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )
