# -*- coding: utf-8 -*-
"""文本向量化（Embedding）适配器."""

import os
from typing import Any

from loguru import logger

from app.core.config import Config


class EmbeddingAdapter:
    """文本向量化模型封装."""

    def __init__(self, config: Config):
        self.config = config
        self.embedding_model = None

    def initialize(self) -> bool:
        """初始化加载 HuggingFace 向量模型."""
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            # 设置镜像源
            if self.config.hf_endpoint:
                os.environ["HF_ENDPOINT"] = self.config.hf_endpoint

            model_name = self.config.embedding_model
            local_model_path = self.config.embedding_model_local_path

            if not os.path.exists(local_model_path):
                logger.info(f"本地模型不存在 ({local_model_path})，尝试网络下载...")
                try:
                    from huggingface_hub import snapshot_download

                    original_offline = os.environ.get("HF_HUB_OFFLINE")
                    if original_offline == "1":
                        os.environ["HF_HUB_OFFLINE"] = "0"

                    snapshot_download(
                        repo_id=model_name,
                        local_dir=local_model_path,
                        local_dir_use_symlinks=False,
                        resume_download=True,
                    )
                    logger.info("嵌入模型下载完成")

                    if original_offline is not None:
                        os.environ["HF_HUB_OFFLINE"] = original_offline

                    model_name = local_model_path
                except ImportError:
                    logger.error("未安装 huggingface_hub，无法自动下载")
                except Exception as e:
                    logger.error(f"模型下载失败: {e}")
            else:
                logger.info(f"使用本地嵌入模型: {local_model_path}")
                model_name = local_model_path

            # 初始化 HF Embeddings
            try:
                self.embedding_model = HuggingFaceEmbeddings(
                    model_name=model_name, cache_folder="./data/models"
                )
            except RuntimeError as re:
                if "split_torch_state_dict_into_shards" in str(re):
                    logger.warning("遇到 huggingface_hub 兼容问题，尝试 local_files_only=True")
                    self.embedding_model = HuggingFaceEmbeddings(
                        model_name=model_name,
                        cache_folder="./data/models",
                        model_kwargs={"local_files_only": True},
                    )
                else:
                    raise re

            logger.info("Embedding 适配器初始化成功")
            return True
        except Exception as e:
            logger.error(f"Embedding 初始化异常: {e}")
            self.embedding_model = None
            return False

    def get_model(self) -> Any:
        return self.embedding_model
