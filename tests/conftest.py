# -*- coding: utf-8 -*-
"""Pytest配置文件.

提供测试fixtures和配置。
"""

import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试环境变量
os.environ['TESTING'] = '1'


@pytest.fixture(scope="session")
def test_env():
    """测试环境配置fixture.
    
    Returns:
        dict: 测试环境变量字典.
    """
    return {
        'TRILIUM_BASE_URL': 'http://localhost:8080',
        'TRILIUM_TOKEN': 'test_token_for_testing',
        'TRILIUM_EXPORT_DEPTH': '5',
        'TRILIUM_EXPORT_LIMIT': '100',
        'SEARCH_K': '5',
    }


@pytest.fixture
def mock_config():
    """模拟配置对象fixture.
    
    Returns:
        object: 模拟的Config对象.
    """
    from unittest.mock import Mock
    from app.core.config import ConfigConstants
    
    config = Mock()
    config.trilium_base_url = 'http://localhost:8080'
    config.trilium_token = 'test_token'
    config.trilium_data_dir = './test_data/trilium'
    config.note_ids = ['root']
    config.depth = 5
    config.limit = 100
    config.vector_db_dir = './test_data/vector_db'
    config.embedding_model = 'sentence-transformers/all-MiniLM-L6-v2'
    config.embedding_model_local_path = './test_data/models/embedding'
    config.llm_model_path = './test_data/models/llm'
    config.llm_model_type = 'gpt4all'
    config.qwen_api_key = ''
    config.search_k = ConfigConstants.DEFAULT_SEARCH_K
    config.chunk_size = ConfigConstants.DEFAULT_CHUNK_SIZE
    config.chunk_overlap = ConfigConstants.DEFAULT_CHUNK_OVERLAP
    config.hf_endpoint = 'https://hf-mirror.com'
    
    return config
