# -*- coding: utf-8 -*-
"""问答缓存管理."""

import hashlib
import json
import time
from typing import Any, Dict, Optional

from app.core.config import Config


class CacheManager:
    """简单的内存 LRU 问答缓存."""

    def __init__(self, config: Config):
        self.config = config
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_order: list = []

    def _generate_key(self, question: str, session_id: str) -> str:
        """根据问题和会话 ID 生成缓存键."""
        data = f"{question}_{session_id}".encode("utf-8")
        return hashlib.md5(data).hexdigest()

    def get(self, question: str, session_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的回答."""
        key = self._generate_key(question, session_id)
        if key in self.cache:
            cache_item = self.cache[key]
            # 检查是否过期
            if time.time() - cache_item["timestamp"] < self.config.qa_cache_ttl:
                # 更新 LRU 顺序
                self.cache_order.remove(key)
                self.cache_order.append(key)
                return cache_item["response"]
            else:
                self._remove_key(key)
        return None

    def set(self, question: str, session_id: str, response: Dict[str, Any]) -> None:
        """保存回答到缓存."""
        key = self._generate_key(question, session_id)
        
        if key in self.cache:
            self.cache_order.remove(key)
            
        self.cache[key] = {
            "response": response,
            "timestamp": time.time()
        }
        self.cache_order.append(key)
        
        # 清理超出容量的旧缓存
        while len(self.cache) > self.config.qa_cache_size:
            oldest_key = self.cache_order.pop(0)
            self._remove_key(oldest_key)

    def _remove_key(self, key: str) -> None:
        """从缓存中移除指定的键."""
        if key in self.cache:
            del self.cache[key]
        if key in self.cache_order:
            self.cache_order.remove(key)

    def clear(self) -> None:
        """清空所有缓存."""
        self.cache.clear()
        self.cache_order.clear()
