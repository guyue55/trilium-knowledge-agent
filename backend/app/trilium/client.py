# -*- coding: utf-8 -*-
"""Trilium ETAPI 网络客户端封装."""

import requests
import trilium_py.client
from loguru import logger
from requests.adapters import HTTPAdapter
from trilium_py.client import ETAPI
from urllib3.util.retry import Retry

from app.core.config import get_config


class TimeoutSession(requests.Session):
    """高雅的、带默认超时防御的 Session，杜绝底层 requests 连接挂起."""
    def __init__(self, timeout: int = 30):
        super().__init__()
        self.default_timeout = timeout

    def request(self, method, url, *args, **kwargs):
        if "timeout" not in kwargs or kwargs["timeout"] is None:
            kwargs["timeout"] = self.default_timeout
        return super().request(method, url, *args, **kwargs)


def _get_shared_session() -> requests.Session:
    """创建带有重试策略的共享Session."""
    config = get_config()
    session = TimeoutSession(timeout=config.trilium_api_timeout)
    retry_strategy = Retry(
        total=config.max_retries,
        backoff_factor=config.retry_backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# 全局共享会话，Monkey Patch 给 trilium_py
_shared_session = _get_shared_session()
trilium_py.client.requests = _shared_session


class TriliumClient:
    """封装底层的 ETAPI 通信逻辑."""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.api: ETAPI | None = None
        self._connect()

    def _connect(self) -> None:
        try:
            logger.info(f"正在连接 Trilium: {self.base_url} ...")
            self.api = ETAPI(self.base_url, self.token)
            # 简单验证
            app_info = self.api.app_info()
            logger.info(f"Trilium 连接成功. AppInfo: {app_info}")
        except Exception as e:
            logger.error(f"连接 Trilium 失败: {e}")
            self.api = None

    def is_connected(self) -> bool:
        return self.api is not None

    def cleanup(self) -> None:
        global _shared_session
        if _shared_session:
            logger.info("关闭 Trilium 共享 Session...")
            _shared_session.close()
