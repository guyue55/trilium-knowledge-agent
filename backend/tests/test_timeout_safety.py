# -*- coding: utf-8 -*-
"""网络层超时控制与安全熔断机制的单元测试.

验证：
1. LiteLLMAdapter 同步及流式请求调用 LiteLLM completion/acompletion 时，能够透传 llm_generation_timeout 超时配置。
2. TimeoutSession 能够拦截底层 requests 网络请求，并在未设置 timeout 时自动注入默认的 trilium_api_timeout 保护。
"""

import os
from unittest.mock import patch, MagicMock

import pytest
import requests

from app.core.config import Config
from app.llm.factory import LiteLLMAdapter
from app.trilium.client import TimeoutSession


class TestTimeoutSafety:
    """超时控制与安全熔断测试用例集."""

    @patch("app.llm.factory.completion")
    @patch.dict(
        os.environ,
        {
            "TRILIUM_BASE_URL": "http://localhost:8080",
            "TRILIUM_TOKEN": "test_token_123",
            "LLM_MODEL_TYPE": "openai",
            "OPENAI_MODEL_NAME": "gpt-3.5-turbo",
            "OPENAI_API_KEY": "some-key",
            "LLM_GENERATION_TIMEOUT": "45",  # 设为 45 秒
        },
    )
    def test_litellm_sync_generation_timeout_injection(self, mock_completion):
        """测试同步大模型生成请求能够正确透传自定义超时参数."""
        # 准备 Mock
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked content"
        mock_completion.return_value = mock_response

        config = Config()
        assert config.llm_generation_timeout == 45

        adapter = LiteLLMAdapter(config)
        result = adapter.generate("Hello")

        assert result == "Mocked content"
        # 验证 completion 被调用，且 kwargs 中传入了 timeout=45
        mock_completion.assert_called_once()
        called_kwargs = mock_completion.call_args[1]
        assert called_kwargs.get("timeout") == 45

    @pytest.mark.asyncio
    @patch("app.llm.factory.acompletion")
    @patch.dict(
        os.environ,
        {
            "TRILIUM_BASE_URL": "http://localhost:8080",
            "TRILIUM_TOKEN": "test_token_123",
            "LLM_MODEL_TYPE": "openai",
            "OPENAI_MODEL_NAME": "gpt-3.5-turbo",
            "OPENAI_API_KEY": "some-key",
            "LLM_GENERATION_TIMEOUT": "25",  # 设为 25 秒
        },
    )
    async def test_litellm_stream_generation_timeout_injection(self, mock_acompletion):
        """测试流式大模型生成请求能够正确透传自定义超时参数."""
        # 准备 Async Mock
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock()]
        mock_chunk.choices[0].delta.content = "stream chunk"

        async def mock_async_generator():
            yield mock_chunk

        mock_acompletion.return_value = mock_async_generator()

        config = Config()
        assert config.llm_generation_timeout == 25

        adapter = LiteLLMAdapter(config)
        chunks = []
        async for chunk in adapter.agenerate_stream("Hello"):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0] == "stream chunk"

        # 验证 acompletion 被调用，且 kwargs 中传入了 timeout=25
        mock_acompletion.assert_called_once()
        called_kwargs = mock_acompletion.call_args[1]
        assert called_kwargs.get("timeout") == 25

    def test_timeout_session_injects_default_timeout(self):
        """测试自定义 TimeoutSession 在未显式指定时，自动对所有 HTTP 方法注入超时."""
        session = TimeoutSession(timeout=15)
        
        # Mock requests.Session.request 底层真实调用
        with patch("requests.Session.request") as mock_super_request:
            mock_super_request.return_value = MagicMock()
            
            # 1. 没传 timeout 参数
            session.get("http://localhost:8080/api/info")
            called_args_list = mock_super_request.call_args_list
            assert len(called_args_list) == 1
            called_kwargs = called_args_list[0][1]
            assert called_kwargs.get("timeout") == 15

            # 2. 传了 timeout 为 None
            session.post("http://localhost:8080/api/data", timeout=None)
            called_args_list = mock_super_request.call_args_list
            assert len(called_args_list) == 2
            called_kwargs = called_args_list[1][1]
            assert called_kwargs.get("timeout") == 15

            # 3. 显式指定了别的 timeout，则不予覆盖
            session.get("http://localhost:8080/api/quick", timeout=5)
            called_args_list = mock_super_request.call_args_list
            assert len(called_args_list) == 3
            called_kwargs = called_args_list[2][1]
            assert called_kwargs.get("timeout") == 5
