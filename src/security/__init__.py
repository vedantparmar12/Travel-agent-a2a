"""
Security module for Travel Agent System.
"""
from .auth import (
    security_manager,
    SecurityManager,
    A2ASecurityMiddleware,
    SecureConfig,
    get_ssl_context,
    require_api_key,
    require_jwt_token,
    rate_limit,
    API_KEY_HEADER,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

__all__ = [
    "security_manager",
    "SecurityManager",
    "A2ASecurityMiddleware",
    "SecureConfig",
    "get_ssl_context",
    "require_api_key",
    "require_jwt_token",
    "rate_limit",
    "API_KEY_HEADER",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
]