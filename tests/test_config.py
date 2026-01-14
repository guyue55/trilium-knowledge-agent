# -*- coding: utf-8 -*-
"""配置管理模块的测试用例.

测试Config类的验证逻辑和配置加载功能。
"""

import os
import pytest
from unittest.mock import patch
from app.core.config import Config, ConfigError, ConfigConstants


class TestConfigConstants:
    """测试ConfigConstants类."""
    
    def test_constants_values(self):
        """测试常量值是否正确定义."""
        assert ConfigConstants.DEFAULT_CHUNK_SIZE == 2000
        assert ConfigConstants.DEFAULT_CHUNK_OVERLAP == 500
        assert ConfigConstants.DEFAULT_SEARCH_K == 10
        assert ConfigConstants.MAX_SEARCH_RESULTS == 20
        assert ConfigConstants.VECTOR_DB_BATCH_SIZE == 5000
        assert ConfigConstants.DEFAULT_MAX_RETRIES == 5
        assert ConfigConstants.MIN_CONTENT_LENGTH == 10
        
    def test_valid_note_types(self):
        """测试有效笔记类型列表."""
        assert 'text' in ConfigConstants.VALID_NOTE_TYPES
        assert 'code' in ConfigConstants.VALID_NOTE_TYPES
        assert 'doc' in ConfigConstants.VALID_NOTE_TYPES
        assert 'book' in ConfigConstants.VALID_NOTE_TYPES
        
    def test_binary_mime_prefixes(self):
        """测试二进制MIME类型前缀."""
        assert 'image/' in ConfigConstants.BINARY_MIME_PREFIXES
        assert 'audio/' in ConfigConstants.BINARY_MIME_PREFIXES
        assert 'video/' in ConfigConstants.BINARY_MIME_PREFIXES


class TestConfigValidation:
    """测试Config类的验证逻辑."""
    
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token_123',
        'TRILIUM_EXPORT_DEPTH': '10',
        'TRILIUM_EXPORT_LIMIT': '5000',
        'SEARCH_K': '10'
    })
    def test_valid_config(self):
        """测试有效配置."""
        config = Config()
        assert config.trilium_base_url == 'http://localhost:8080'
        assert config.trilium_token == 'test_token_123'
        assert config.depth == 10
        assert config.limit == 5000
        assert config.search_k == 10
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': '',  # 空token
    })
    def test_empty_token_raises_error(self):
        """测试空token时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "TRILIUM_TOKEN 不能为空" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': '',  # 空URL
        'TRILIUM_TOKEN': 'test_token',
    })
    def test_empty_base_url_raises_error(self):
        """测试空base_url时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "TRILIUM_BASE_URL 不能为空" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'TRILIUM_EXPORT_DEPTH': '0',  # 无效深度
    })
    def test_invalid_depth_raises_error(self):
        """测试无效深度时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "TRILIUM_EXPORT_DEPTH 必须大于 0" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'TRILIUM_EXPORT_LIMIT': '-100',  # 无效限制
    })
    def test_invalid_limit_raises_error(self):
        """测试无效限制时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "TRILIUM_EXPORT_LIMIT 必须大于 0" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'SEARCH_K': '-5',  # 无效search_k
    })
    def test_invalid_search_k_raises_error(self):
        """测试无效search_k时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "SEARCH_K 必须大于 0" in str(exc_info.value)
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'CHUNK_SIZE': '100',
        'CHUNK_OVERLAP': '200',  # overlap >= size
    })
    def test_invalid_chunk_overlap_raises_error(self):
        """测试chunk_overlap>=chunk_size时抛出ConfigError."""
        with pytest.raises(ConfigError) as exc_info:
            Config()
        assert "CHUNK_OVERLAP" in str(exc_info.value)
        assert "必须小于 CHUNK_SIZE" in str(exc_info.value)


class TestConfigTypeConversion:
    """测试Config类的类型转换功能."""
    
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'TRILIUM_EXPORT_DEPTH': 'invalid',  # 非数字
    })
    def test_invalid_depth_type_uses_default(self):
        """测试非数字depth时使用默认值."""
        config = Config()
        assert config.depth == 10  # 默认值
        
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
        'CHUNK_SIZE': 'not_a_number',  # 非数字
    })
    def test_invalid_chunk_size_type_uses_default(self):
        """测试非数字chunk_size时使用默认值."""
        config = Config()
        assert config.chunk_size == ConfigConstants.DEFAULT_CHUNK_SIZE


class TestConfigRepr:
    """测试Config类的字符串表示."""
    
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'secret_token',
        'LLM_MODEL_TYPE': 'qwen',
    })
    def test_repr_hides_sensitive_info(self):
        """测试__repr__不泄露敏感信息."""
        config = Config()
        repr_str = repr(config)
        
        # 应该包含的信息
        assert 'http://localhost:8080' in repr_str
        assert 'qwen' in repr_str
        
        # 不应该包含的敏感信息
        assert 'secret_token' not in repr_str


class TestConfigDefaults:
    """测试Config类的默认值."""
    
    @patch.dict(os.environ, {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token',
    }, clear=True)
    def test_default_values(self):
        """测试所有默认值是否正确."""
        config = Config()
        
        # Trilium配置默认值
        assert config.depth == 10
        assert config.limit == 5000
        assert config.note_ids == ['root']
        
        # 文本分割默认值
        assert config.chunk_size == ConfigConstants.DEFAULT_CHUNK_SIZE
        assert config.chunk_overlap == ConfigConstants.DEFAULT_CHUNK_OVERLAP
        
        # 检索默认值
        assert config.search_k == ConfigConstants.DEFAULT_SEARCH_K
        
        # 模型类型默认值
        assert config.llm_model_type == 'gpt4all'
        
        # 镜像源默认值
        assert config.hf_endpoint == 'https://hf-mirror.com'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
