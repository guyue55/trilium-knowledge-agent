# -*- coding: utf-8 -*-
"""GPT4All 适配器实现."""

import os
from typing import Any

from loguru import logger

from app.llm.base import LLMAdapter


class GPT4AllAdapter(LLMAdapter):
    """GPT4All 本地模型适配器."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.llm = None

    def initialize(self) -> bool:
        try:
            from langchain_community.llms import GPT4All

            if not os.path.exists(self.model_path):
                logger.error(f"GPT4All 模型文件不存在: {self.model_path}")
                return False

            self.llm = GPT4All(model=self.model_path, verbose=False)
            logger.info("GPT4All 适配器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 GPT4All 失败: {e}")
            return False

    def get_langchain_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm:
            return "GPT4All 模型未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None
        logger.info("GPT4All 资源已释放")
