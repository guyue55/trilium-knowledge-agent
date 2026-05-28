# -*- coding: utf-8 -*-
"""LLM 实例化工厂."""

from loguru import logger

from app.core.config import Config
from app.llm.adapters.gpt4all_adapter import GPT4AllAdapter
from app.llm.adapters.openai_adapter import OpenAIAdapter
from app.llm.adapters.qwen_adapter import QwenAPIAdapter, QwenLocalAdapter
from app.llm.base import LLMAdapter


class LLMFactory:
    """LLM 适配器工厂类."""

    @staticmethod
    def create_llm(config: Config) -> LLMAdapter | None:
        """根据配置创建对应的 LLM 适配器实例并初始化.

        Args:
            config: 系统配置

        Returns:
            LLMAdapter | None: 初始化成功的适配器，如果失败则返回 None
        """
        model_type = config.llm_model_type.lower()
        use_api = config.llm_use_api
        adapter: LLMAdapter | None = None

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
            return None

        if adapter:
            success = adapter.initialize()
            if not success:
                logger.error(f"LLM 适配器 ({model_type}) 初始化失败")
                return None

        return adapter
