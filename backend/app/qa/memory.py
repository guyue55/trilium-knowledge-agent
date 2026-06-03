# -*- coding: utf-8 -*-
"""问答系统的会话内存与历史记录管理."""

import asyncio
from typing import Dict, List
from pydantic import BaseModel
from loguru import logger


class ChatMessage(BaseModel):
    """原生会话消息结构，完全脱离 LangChain 依赖."""
    role: str  # "user" 或 "assistant"
    content: str


class SessionManager:
    """管理多用户的多轮对话上下文 (线程/协程安全)."""

    def __init__(self, max_history: int = 5):
        self.sessions: Dict[str, List[ChatMessage]] = {}
        self.max_history = max_history
        self._lock = asyncio.Lock()

    async def get_history(self, session_id: str) -> List[ChatMessage]:
        """获取指定会话的历史记录."""
        async with self._lock:
            return self.sessions.get(session_id, [])

    async def add_interaction(self, session_id: str, human_text: str, ai_text: str) -> None:
        """向会话中添加一轮交互，并自动裁剪超出最大历史长度的旧消息."""
        async with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = []
            
            self.sessions[session_id].append(ChatMessage(role="user", content=human_text))
            self.sessions[session_id].append(ChatMessage(role="assistant", content=ai_text))
            
            # 控制历史长度：每一轮为 2 条消息（1 用户 + 1 AI）
            max_msg_len = self.max_history * 2
            if len(self.sessions[session_id]) > max_msg_len:
                self.sessions[session_id] = self.sessions[session_id][-max_msg_len:]

    async def clear_session(self, session_id: str) -> bool:
        """清空指定会话."""
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"会话 {session_id} 已清除")
                return True
            return False
