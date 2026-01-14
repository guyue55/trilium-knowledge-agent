# -*- coding: utf-8 -*-
"""LLM 基础接口和提供商驱动实现."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
import os
from loguru import logger

class LLMDriver(ABC):
    """LLM 驱动基类，定义统一的生成和管理接口."""
    
    @abstractmethod
    def initialize(self) -> bool:
        """初始化驱动及模型资源."""
        pass

    @abstractmethod
    def get_llm(self) -> Any:
        """获取用于 LangChain 的模型实例."""
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """直接生成文本内容."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """释放模型资源."""
        pass


class GPT4AllDriver(LLMDriver):
    """GPT4All 本地模型驱动."""
    
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
            logger.info("GPT4All 驱动初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 GPT4All 失败: {e}")
            return False

    def get_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm: return "GPT4All 模型未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None
        logger.info("GPT4All 资源已释放")


class QwenAPIDriver(LLMDriver):
    """阿里千问 API 驱动."""
    
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
            logger.info(f"Qwen API 驱动 ({self.model_name}) 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 Qwen API 失败: {e}")
            return False

    def get_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm: return "Qwen API 未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None


class QwenLocalDriver(LLMDriver):
    """本地 Qwen 模型驱动 (Transformers)."""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.llm = None

    def initialize(self) -> bool:
        try:
            from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            import torch

            if not os.path.exists(self.model_path):
                logger.error(f"本地 Qwen 路径不存在: {self.model_path}")
                return False

            tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
            model = AutoModelForCausalLM.from_pretrained(
                self.model_path, 
                device_map="auto", 
                trust_remote_code=True,
                dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
            
            pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=512)
            self.llm = HuggingFacePipeline(pipeline=pipe)
            logger.info("本地 Qwen 驱动初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化本地 Qwen 失败: {e}")
            return False

    def get_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm: return "本地 Qwen 未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("本地 Qwen 资源及显存已清理")


class OpenAIDriver(LLMDriver):
    """OpenAI API 驱动."""
    
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.llm = None

    def initialize(self) -> bool:
        try:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                openai_api_key=self.api_key,
                openai_api_base=self.base_url,
                model_name=self.model_name,
                temperature=0
            )
            logger.info(f"OpenAI 驱动 ({self.model_name}) 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化 OpenAI 失败: {e}")
            return False

    def get_llm(self) -> Any:
        return self.llm

    def generate(self, prompt: str) -> str:
        if not self.llm: return "OpenAI 未就绪"
        return self.llm.invoke(prompt)

    def cleanup(self) -> None:
        self.llm = None

