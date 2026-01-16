# -*- coding: utf-8 -*-
"""安全相关的依赖项和中间件."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from loguru import logger

from app.core.config import ConfigConstants, get_config

config = get_config()

# 定义 API Key 头部
api_key_header = APIKeyHeader(name=ConfigConstants.API_KEY_HEADER_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """验证 API Key 的合法性.

    如果 API_AUTH_KEY 未设置，则跳过验证。
    """
    auth_key = config.api_auth_key
    if not auth_key:
        return None

    if api_key != auth_key:
        logger.warning(f"未经授权的访问尝试，提供的 API Key: {api_key[:4]}****")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key


def mask_sensitive_data(record):
    """日志脱敏处理，防止泄露 Key 和 Token."""
    # 需要脱敏的关键字
    sensitive_keys = [
        "TRILIUM_TOKEN",
        "API_KEY",
        "OPENAI_API_KEY",
        "QWEN_API_KEY",
        "API_AUTH_KEY",
    ]

    message = record["message"]
    for key in sensitive_keys:
        if key in message:
            # 简单的掩码逻辑，实际生产环境可使用更复杂的正则
            record["message"] = message.replace(key, f"{key} [MASKED]")
    return True
