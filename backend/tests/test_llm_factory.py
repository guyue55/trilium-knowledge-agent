# -*- coding: utf-8 -*-
"""大模型工厂与 LiteLLMAdapter 的测试用例.

验证 OpenAI 自定义配置支持、空密钥豁免、模型前缀自适应等功能。
"""

import os
from unittest.mock import patch

import pytest

from app.core.config import Config
from app.llm.factory import LLMFactory, LiteLLMAdapter, MockLLMAdapter


class TestLLMFactoryAndAdapter:
    """测试大模型工厂及 LiteLLMAdapter 适配器逻辑."""

    @patch.dict(
        os.environ,
        {
            "TRILIUM_BASE_URL": "http://localhost:8080",
            "TRILIUM_TOKEN": "test_token_123",
            "LLM_MODEL_TYPE": "openai",
            "OPENAI_MODEL_NAME": "custom-gpt-model",
            "OPENAI_API_KEY": "",  # 故意置空密钥
            "OPENAI_API_BASE": "https://custom-api-base.com/v1",
        },
    )
    def test_openai_keyless_exemption_and_prefix(self):
        """测试 OpenAI 格式大模型无密钥时的豁免拦截，以及模型前缀自动拼接."""
        config = Config()
        assert config.llm_model_type == "openai"
        assert config.openai_api_key == ""

        # 调用工厂创建 LLM，应当顺利返回 LiteLLMAdapter 而不退化到 MockLLMAdapter
        llm = LLMFactory.create_llm(config)
        assert isinstance(llm, LiteLLMAdapter)
        
        # 验证是否自动添加了 'openai/' 前缀
        assert llm.model_name == "openai/custom-gpt-model"
        # 验证是否自动填充了安全占位符 "none"
        assert llm.api_key == "none"
        # 验证 Base URL
        assert llm.api_base == "https://custom-api-base.com/v1"

    @patch.dict(
        os.environ,
        {
            "TRILIUM_BASE_URL": "http://localhost:8080",
            "TRILIUM_TOKEN": "test_token_123",
            "LLM_MODEL_TYPE": "openai",
            "OPENAI_MODEL_NAME": "openai/already-prefixed-model",
            "OPENAI_API_KEY": "some-valid-key",
            "OPENAI_API_BASE": "",  # 留空
        },
    )
    def test_openai_with_prefix_and_default_base(self):
        """测试已带有前缀的模型名，以及 Base URL 留空时的缺省值."""
        config = Config()
        llm = LLMFactory.create_llm(config)
        assert isinstance(llm, LiteLLMAdapter)
        
        # 验证不重复添加前缀
        assert llm.model_name == "openai/already-prefixed-model"
        # 验证 API Key 被正常读取
        assert llm.api_key == "some-valid-key"
        # 验证 API Base 自动兜底官方地址
        assert llm.api_base == "https://api.openai.com/v1"

    @patch.dict(
        os.environ,
        {
            "TRILIUM_BASE_URL": "http://localhost:8080",
            "TRILIUM_TOKEN": "test_token_123",
            "LLM_MODEL_TYPE": "deepseek",  # deepseek 类型，且没有密钥
            "DEEPSEEK_API_KEY": "",
        },
    )
    def test_other_provider_still_degrades_without_key(self):
        """测试其他云端模型提供商在无 Key 时依然正常退化降级到 MockLLMAdapter."""
        config = Config()
        # 由于 deepseek 无密钥，应该被强制拦截降级到 MockLLMAdapter
        llm = LLMFactory.create_llm(config)
        assert isinstance(llm, MockLLMAdapter)
