# -*- coding: utf-8 -*-
"""大语言模型（LLM）适配器基类定义."""

from abc import ABC, abstractmethod
from typing import Any


class LLMAdapter(ABC):
    """LLM 统一适配器接口.
    
    采用适配器模式隔离底层不同的 LLM 实现（如 GPT4All, OpenAI, Qwen 等），
    向上层提供统一的接口。
    """

    @abstractmethod
    def initialize(self) -> bool:
        """初始化驱动及模型资源.
        
        Returns:
            bool: 初始化是否成功
        """
        pass

    @abstractmethod
    def get_langchain_llm(self) -> Any:
        """获取用于 LangChain 的底层模型实例.
        
        Returns:
            Any: LangChain 兼容的 LLM 对象
        """
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """直接生成文本内容（同步方法，适用于简单测试）.
        
        Args:
            prompt: 输入的提示词
            
        Returns:
            str: 生成的回答
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """释放模型及显存/内存资源."""
        pass
