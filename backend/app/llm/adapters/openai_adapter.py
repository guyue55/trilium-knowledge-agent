# -*- coding: utf-8 -*-
"""OpenAI 适配器实现."""

from typing import Any

from loguru import logger

from app.llm.base import LLMAdapter


class OpenAIAdapter(LLMAdapter):
    """OpenAI API 驱动适配器."""

    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.llm = None

    def initialize(self) -> bool:
        try:
            from langchain_openai import ChatOpenAI

            if not self.api_key:
                logger.error("OpenAI API Key 未设置")
                return False

            self.llm = ChatOpenAI(
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
                model_name=self.model_name,
                temperature=0,
            )
            logger.info(f"OpenAI 适配器 ({self.model_name}) 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 OpenAI 失败: {e}")
            return False

    def get_langchain_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm:
            return "OpenAI 模型未就绪"
        return self.llm.invoke(prompt).content

    async def agenerate_stream(self, prompt: str):
        if not self.llm:
            yield "OpenAI 模型未就绪"
            return
        async for chunk in self.llm.astream(prompt):
            if hasattr(chunk, "content"):
                yield chunk.content
            else:
                yield str(chunk)

    def cleanup(self) -> None:
        self.llm = None
        logger.info("OpenAI 资源已释放")
