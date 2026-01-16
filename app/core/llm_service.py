# -*- coding: utf-8 -*-
"""Trilium知识体代理的语言模型服务."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.core.config import Config
from app.core.llm_drivers import GPT4AllDriver, LLMDriver, OpenAIDriver, QwenAPIDriver, QwenLocalDriver


class LLMService:
    """用于管理语言模型的服务，支持多驱动扩展."""

    def __init__(self, config: Config) -> None:
        """初始化LLM服务.

        Args:
            config: 应用程序配置.
        """
        self.config = config
        self.driver: LLMDriver | None = None
        self._initialize_driver()

    def _initialize_driver(self) -> None:
        """根据配置初始化对应的模型驱动."""
        model_type = self.config.llm_model_type.lower()
        use_api = self.config.llm_use_api

        if model_type == "qwen":
            if use_api:
                self.driver = QwenAPIDriver(self.config.qwen_api_key)
            else:
                self.driver = QwenLocalDriver(self.config.llm_model_path)
        elif model_type == "openai":
            self.driver = OpenAIDriver(
                self.config.openai_api_key,
                self.config.openai_api_base,
                self.config.openai_model_name,
            )
        elif model_type == "gpt4all":
            self.driver = GPT4AllDriver(self.config.llm_model_path)
        else:
            logger.error(f"不支持的模型类型: {model_type}")
            return

        if self.driver:
            success = self.driver.initialize()
            if not success:
                logger.error(f"驱动 {model_type} 初始化失败")
                self.driver = None

    def get_llm(self) -> Any | None:
        """获取用于 LangChain 的模型实例."""
        return self.driver.get_llm() if self.driver else None

    def generate_text(self, prompt: str) -> str:
        """使用语言模型生成文本."""
        if not self.driver:
            return "语言模型不可用。"
        try:
            return self.driver.generate(prompt)
        except Exception as e:
            logger.error(f"生成文本时出错: {e}")
            return f"生成响应时出错: {str(e)}"

    def cleanup(self) -> None:
        """释放模型资源."""
        if self.driver:
            self.driver.cleanup()
            self.driver = None
