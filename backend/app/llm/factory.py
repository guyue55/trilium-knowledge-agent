# -*- coding: utf-8 -*-
"""LLM 实例化工厂与降级策略."""

import time
from typing import Any
from loguru import logger

from app.core.config import Config
from app.llm.adapters.gpt4all_adapter import GPT4AllAdapter
from app.llm.adapters.openai_adapter import OpenAIAdapter
from app.llm.adapters.qwen_adapter import QwenAPIAdapter, QwenLocalAdapter
from app.llm.base import LLMAdapter


class MockLLMAdapter(LLMAdapter):
    """降级备用大模型，当正式模型不可用时保证管道不中断."""
    
    def initialize(self) -> bool:
        return True
        
    def generate(self, prompt: str) -> str:
        time.sleep(1.5) # 模拟生成延迟
        return "<answer>这是一个 Mock 答案。由于真实的本地大模型加载失败，系统自动降级采用了模拟生成引擎，以保证问答管道的连通性。</answer>"
        
    async def agenerate_stream(self, prompt: str):
        import asyncio
        msg = "<answer>这是一个 Mock 答案。由于真实的本地大模型加载失败，系统自动降级采用了模拟生成引擎，以保证问答管道的连通性。</answer>"
        for i in range(0, len(msg), 3):
            await asyncio.sleep(0.05)
            yield msg[i:i+3]
        
    def get_langchain_llm(self) -> Any:
        # Mock 一个支持基本调用的占位对象
        class FakeLangchainLLM:
            def invoke(self, *args, **kwargs):
                return "Mock Content"
        return FakeLangchainLLM()
        
    def cleanup(self) -> None:
        pass


class LLMFactory:
    """LLM 适配器工厂类."""

    @staticmethod
    def create_llm(config: Config) -> LLMAdapter:
        """根据配置创建对应的 LLM 适配器实例并初始化，自带降级保护.

        Args:
            config: 系统配置

        Returns:
            LLMAdapter: 初始化成功的适配器，如果失败则返回 MockLLMAdapter 降级
        """
        model_type = config.llm_model_type.lower()
        use_api = config.llm_use_api
        adapter: LLMAdapter | None = None

        try:
            if model_type == "qwen":
                if use_api:
                    adapter = QwenAPIAdapter(config.qwen_api_key)
                else:
                    adapter = QwenLocalAdapter(config.llm_model_path)
            elif model_type == "openai":
                adapter = OpenAIAdapter(
                    api_key=config.openai_api_key,
                    base_url=config.openai_api_base,
                    model_name=config.openai_model_name,
                )
            elif model_type == "gpt4all":
                adapter = GPT4AllAdapter(config.llm_model_path)
            else:
                logger.error(f"不支持的 LLM 类型: {model_type}")
        except Exception as e:
            logger.error(f"实例化 LLM Adapter ({model_type}) 期间发生异常: {e}")

        if adapter:
            success = adapter.initialize()
            if success:
                return adapter
            else:
                logger.error(f"LLM 适配器 ({model_type}) 初始化失败，启动降级策略")

        logger.warning("正在使用 MockLLMAdapter 降级启动以保证系统可用性")
        mock = MockLLMAdapter()
        mock.initialize()
        return mock
