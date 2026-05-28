# -*- coding: utf-8 -*-
"""问答系统的会话内存与历史记录管理."""

import asyncio
from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger


class SessionManager:
    """管理多用户的多轮对话上下文."""

    def __init__(self, max_history: int = 5):
        self.sessions: Dict[str, List[Any]] = {}
        self.max_history = max_history
        self._lock = asyncio.Lock()

    async def get_history(self, session_id: str) -> List[Any]:
        """获取指定会话的历史记录."""
        async with self._lock:
            return self.sessions.get(session_id, [])

    async def add_interaction(self, session_id: str, human_text: str, ai_text: str) -> None:
        """向会话中添加一轮交互."""
        async with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = []
            
            self.sessions[session_id].append(HumanMessage(content=human_text))
            self.sessions[session_id].append(AIMessage(content=ai_text))
            
            # 控制历史长度
            if len(self.sessions[session_id]) > self.max_history * 2:
                self.sessions[session_id] = self.sessions[session_id][-(self.max_history * 2):]

    async def clear_session(self, session_id: str) -> bool:
        """清空指定会话."""
        async with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"会话 {session_id} 已清除")
                return True
            return False
