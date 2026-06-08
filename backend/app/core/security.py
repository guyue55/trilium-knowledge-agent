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
        masked_key = (api_key[:4] + "****") if api_key else "None"
        logger.warning(f"未经授权的访问尝试，提供的 API Key: {masked_key}")
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key


import re

def mask_sensitive_data(record):
    """日志脱敏处理，防止泄露 Key 和 Token (通过 Loguru patcher 原地篡改)."""
    message = record.get("message", "")
    if not isinstance(message, str):
        return

    # 1. 匹配常见的特定 API Key 格式，如 sk-..., qwen-..., 并脱敏
    message = re.sub(
        r'\b(sk-[a-zA-Z0-9]{8,}|qwen-[a-zA-Z0-9]{8,})\b',
        lambda m: m.group(1)[:6] + "******" if len(m.group(1)) > 6 else "******",
        message
    )

    # 2. 匹配配置文件或 payload 赋值中的敏感 key-value，并脱敏其值
    sensitive_patterns = [
        r'(TRILIUM_TOKEN|API_KEY|OPENAI_API_KEY|QWEN_API_KEY|DEEPSEEK_API_KEY|GEMINI_API_KEY|API_AUTH_KEY)\s*([:=])\s*([\'"]?)([a-zA-Z0-9\-_]{6,})\3'
    ]
    for pattern in sensitive_patterns:
        message = re.sub(
            pattern,
            lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)[:4]}******{m.group(3)}" if len(m.group(4)) > 4 else f"{m.group(1)}{m.group(2)}{m.group(3)}******{m.group(3)}",
            message,
            flags=re.IGNORECASE
        )

    record["message"] = message
