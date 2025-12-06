# -*- coding: utf-8 -*-
"""应用程序配置管理."""

import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()


class Config:
    """应用程序配置."""
    
    def __init__(self) -> None:
        """初始化配置."""
        # Trilium配置
        self.trilium_base_url = os.getenv("TRILIUM_BASE_URL", "http://192.168.1.202:3004")
        self.trilium_token = os.getenv("TRILIUM_TOKEN", "")
        self.trilium_data_dir = os.getenv("TRILIUM_DATA_DIR", "./data/trilium")
        self.note_ids = os.getenv("NOTE_IDS", "root").split(",")
        self.depth = os.getenv("DEPTH", 5)
        self.limit = os.getenv("LIMIT", 500)
        
        # 向量数据库配置
        self.vector_db_dir = os.getenv("VECTOR_DB_DIR", "./data/vector_db/embeddings")
        
        # 嵌入模型配置
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.embedding_model_local_path = os.getenv("EMBEDDING_MODEL_LOCAL_PATH", "./data/models/sentence-transformers/all-MiniLM-L6-v2")
        
        # 语言模型配置
        self.llm_model_path = os.getenv("LLM_MODEL_PATH", "./data/models/gpt4all/ggml-gpt4all-j-v1.3-groovy.bin")
        self.llm_model_type = os.getenv("LLM_MODEL_TYPE", "gpt4all")  # gpt4all 或 qwen
        self.qwen_api_key = os.getenv("QWEN_API_KEY", "")  # 阿里云千问API密钥
        
        # 镜像源配置
        self.hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")


def get_config() -> Config:
    """获取应用程序配置实例.
    
    Returns:
        Config: 应用程序配置实例.
    """
    return Config()