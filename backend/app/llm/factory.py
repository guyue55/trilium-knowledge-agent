# -*- coding: utf-8 -*-
"""LLM 实例化工厂与智能降级自适应策略 (基于 LiteLLM)."""

import time
import asyncio
from typing import Any, AsyncGenerator
import requests
from loguru import logger
from litellm import acompletion, completion

from app.core.config import Config
from app.llm.base import LLMAdapter


class LiteLLMAdapter(LLMAdapter):
    """基于 LiteLLM 的通用大模型适配器，统一管理 100+ 种主流 LLM 调用."""
    
    def __init__(self, config: Config):
        self.config = config
        self.model_name = ""
        self.api_key = None
        self.api_base = None
        
        # 路由选择策略
        model_type = config.llm_model_type.lower()
        if model_type == "ollama":
            # 格式: ollama/qwen2:7b 或 ollama/llama3
            # 如果配置的是简写路径，则自动拼接为标准的 ollama 格式
            model_path = config.llm_model_path if config.llm_model_path else "qwen2:7b"
            if model_path.startswith("ollama/"):
                self.model_name = model_path
            else:
                self.model_name = f"ollama/{model_path}"
            self.api_base = config.openai_api_base or "http://localhost:11434"
            logger.info(f"Ollama 配置路由 -> 模型: {self.model_name}, Base: {self.api_base}")
        elif model_type == "qwen":
            self.model_name = config.llm_model_path if config.llm_model_path else "qwen-turbo"
            self.api_key = config.qwen_api_key
            self.api_base = config.openai_api_base or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            logger.info(f"Qwen 配置路由 -> 模型: {self.model_name}, Base: {self.api_base}")
        elif model_type == "deepseek":
            model_name_cfg = config.deepseek_model_name or "deepseek-chat"
            if model_name_cfg.startswith("deepseek/"):
                self.model_name = model_name_cfg
            else:
                self.model_name = f"deepseek/{model_name_cfg}"
            self.api_key = config.deepseek_api_key
            self.api_base = config.deepseek_api_base
            logger.info(f"DeepSeek 配置路由 -> 模型: {self.model_name}, Base: {self.api_base}")
        elif model_type == "gemini":
            model_name_cfg = config.gemini_model_name or "gemini-2.5-flash"
            if model_name_cfg.startswith("gemini/"):
                self.model_name = model_name_cfg
            else:
                self.model_name = f"gemini/{model_name_cfg}"
            self.api_key = config.gemini_api_key
            logger.info(f"Gemini 配置路由 -> 模型: {self.model_name}")
        elif model_type == "openai":
            model_name_cfg = config.openai_model_name or "gpt-3.5-turbo"
            if model_name_cfg and not model_name_cfg.startswith("openai/"):
                self.model_name = f"openai/{model_name_cfg}"
            else:
                self.model_name = model_name_cfg
            self.api_key = config.openai_api_key or "none"  # 注入防报错占位符
            self.api_base = config.openai_api_base or "https://api.openai.com/v1"
            logger.info(f"OpenAI 配置路由 -> 模型: {self.model_name}, Base: {self.api_base}")
        else: # 默认 fallback 到 OpenAI / 兼容第三方平台
            self.model_name = config.openai_model_name or "gpt-3.5-turbo"
            self.api_key = config.openai_api_key or "none"
            self.api_base = config.openai_api_base

    def initialize(self) -> bool:
        logger.info(f"成功挂载 LiteLLM 驱动器: [{self.model_name}]")
        return True

    def generate(self, prompt: str) -> str:
        try:
            # 根据 response_mode 映射自适应生成温度 (temperature)
            response_mode = getattr(self.config, "response_mode", "balanced").lower()
            if response_mode == "strict":
                temperature = 0.1
            elif response_mode == "creative":
                temperature = 0.7
            else: # balanced
                temperature = 0.4

            kwargs = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["api_base"] = self.api_base
                
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LiteLLM 同步生成失败: {e}")
            return f"生成失败: {e}"

    async def agenerate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        try:
            # 根据 response_mode 映射自适应生成温度 (temperature)
            response_mode = getattr(self.config, "response_mode", "balanced").lower()
            if response_mode == "strict":
                temperature = 0.1
            elif response_mode == "creative":
                temperature = 0.7
            else: # balanced
                temperature = 0.4

            kwargs = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "temperature": temperature,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["api_base"] = self.api_base
                
            response = await acompletion(**kwargs)
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LiteLLM 流式生成中断或失败: {e}")
            yield f"\n\n⚠️ [流式输出异常，问答管道中断: {e}]"

    def cleanup(self) -> None:
        pass


class MockLLMAdapter(LLMAdapter):
    """极致优雅的本地备用模拟大模型。保证即使在离线、网络隔离或无密钥环境下，全套系统仍能完美正常运转，不崩溃。"""
    
    def initialize(self) -> bool:
        return True
        
    def generate(self, prompt: str) -> str:
        time.sleep(1.0)
        return (
            "<answer>您好！这是本地内置的【模拟生成引擎 (MockLLM)】为您返回的答复。\n\n"
            "因为您当前未启动本地大模型服务（如 Ollama），或者没有在 .env 文件中配置有效的第三方云端 API Key（如 OpenAI、阿里云通义千问等），为了保证项目一键部署和开发体验能平滑运行而无需忍受崩溃打断，系统已自适应为您启用本模拟服务。\n\n"
            "请根据您的实际需要，在 `.env` 配置文件中写入您的 API Key 或启动您的本地 Ollama 服务来获取真实的智能解答！</answer>"
        )
        
    async def agenerate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        msg = (
            "<answer>您好！由于您当前未在本地启动 Ollama 服务，或未在 `.env` 中提供有效的 LLM 平台 API Key，"
            "本系统为了给您带来流畅的界面交互演示，已经无缝自适应降级到了【本地内置模拟流式大模型】。\n\n"
            "**配置指南：**\n"
            "1. 本地大模型：安装并启动 [Ollama](https://ollama.com/) 客户端（运行例如 `ollama run qwen2:7b` ），无需任何 API Key，秒变全本地隐私安全知识库。\n"
            "2. 在线大模型：在后端 `.env` 中将 `LLM_MODEL_TYPE` 设为 `openai`，并填入您的 `OPENAI_API_KEY` 与对应的 `OPENAI_API_BASE`，即刻体验极致智能。\n\n"
            "这证实了我们的智能问答 RAG 管道已全线贯通！您可以照常体验清空上下文、后台同步等一系列炫酷操作！</answer>"
        )
        # 流式切片发送，带来细腻动感的打字机效果
        for i in range(0, len(msg), 4):
            await asyncio.sleep(0.02)
            yield msg[i:i+4]
        
    def cleanup(self) -> None:
        pass


class LLMFactory:
    """LLM 适配器生成工厂，实现主动探测和软性安全退化逻辑."""

    @staticmethod
    def create_llm(config: Config) -> LLMAdapter:
        model_type = config.llm_model_type.lower()
        
        # 1. 密钥空置直接阻断与智能降级自适应
        # 如果不是本地 Ollama 模型，且不是 OpenAI 格式模型，但又没有提供任何第三方云端 API 凭证，直接在工厂层装载备用 Mock 引擎
        is_ollama = (model_type == "ollama")
        is_openai = (model_type == "openai")
        has_api_credentials = bool(
            config.openai_api_key.strip() or 
            config.qwen_api_key.strip() or 
            config.deepseek_api_key.strip() or 
            config.gemini_api_key.strip()
        )
        
        if not is_ollama and not is_openai and not has_api_credentials:
            logger.warning(f"大模型类型为 [{config.llm_model_type}]，但未配置有效 API 密钥。LLMFactory 将自动装载本地内置 MockLLMAdapter 保障全系统正常运转。")
            return LLMFactory._get_mock_fallback()

        # 2. Ollama 连通性极速探测（防止本地未开客户端导致 LiteLLM 在 completion 时长达数十秒的死等和连接超时）
        if model_type == "ollama":
            api_base = config.openai_api_base or "http://localhost:11434"
            try:
                # 极速探测 0.8 秒
                response = requests.get(api_base, timeout=0.8)
                if response.status_code != 200:
                    logger.warning(f"Ollama 服务端口返回异常代码 {response.status_code}，触发退化。")
                    return LLMFactory._get_mock_fallback()
                logger.info("Ollama 本地服务在线，成功连接到 Ollama。")
            except Exception as conn_err:
                logger.warning(f"无法连通 Ollama 本地服务 ({api_base}): {conn_err}。系统自动为您降级至模拟大模型。")
                return LLMFactory._get_mock_fallback()

        try:
            # 尝试通过 LiteLLM 实例化标准适配器
            adapter = LiteLLMAdapter(config)
            adapter.initialize()
            return adapter
        except Exception as e:
            logger.error(f"LiteLLM 驱动实例化异常: {e}")
            return LLMFactory._get_mock_fallback()

    @staticmethod
    def _get_mock_fallback() -> LLMAdapter:
        logger.info("🌟 系统启用自适应防崩溃退化防护网：装载本地 MockLLMAdapter 完成")
        mock = MockLLMAdapter()
        mock.initialize()
        return mock
