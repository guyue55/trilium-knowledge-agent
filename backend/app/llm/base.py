# -*- coding: utf-8 -*-
"""大语言模型（LLM）适配器基类定义."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class LLMAdapter(ABC):
    """LLM 统一适配器接口."""

    @abstractmethod
    def initialize(self) -> bool:
        """初始化驱动及模型资源.
        
        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """直接生成文本内容（同步方法）.
        
        Args:
            prompt: 输入的提示词
            
        Returns:
            str: 生成的回答
        """
        pass

    @abstractmethod
    async def agenerate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """异步生成文本流.
        
        Args:
            prompt: 输入的提示词
            
        Yields:
            str: 生成的文本片段
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """释放模型及显存/内存资源."""
        pass
