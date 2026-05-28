# -*- coding: utf-8 -*-
"""Qwen API 和 Local 适配器实现."""

import os
from typing import Any

from loguru import logger

from app.llm.base import LLMAdapter


class QwenAPIAdapter(LLMAdapter):
    """阿里千问 API 驱动适配器."""

    def __init__(self, api_key: str, model_name: str = "qwen-turbo"):
        self.api_key = api_key
        self.model_name = model_name
        self.llm = None

    def initialize(self) -> bool:
        try:
            from langchain_community.llms.tongyi import Tongyi

            if not self.api_key:
                logger.error("Qwen API Key 未设置")
                return False

            self.llm = Tongyi(dashscope_api_key=self.api_key, model_name=self.model_name)
            logger.info(f"Qwen API 适配器 ({self.model_name}) 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 Qwen API 失败: {e}")
            return False

    def get_langchain_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm:
            return "Qwen API 模型未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None
        logger.info("Qwen API 资源已释放")


class QwenLocalAdapter(LLMAdapter):
    """本地 Qwen 模型驱动 (Transformers) 适配器."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.llm = None

    def initialize(self) -> bool:
        try:
            import torch
            from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

            if not os.path.exists(self.model_path):
                logger.error(f"本地 Qwen 路径不存在: {self.model_path}")
                return False

            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map="auto",
                trust_remote_code=True,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )

            pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=512)
            self.llm = HuggingFacePipeline(pipeline=pipe)
            logger.info("本地 Qwen 适配器初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化本地 Qwen 失败: {e}")
            return False

    def get_langchain_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm:
            return "本地 Qwen 模型未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("本地 Qwen 资源及显存已清理")
