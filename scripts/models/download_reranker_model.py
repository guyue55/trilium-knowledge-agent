# -*- coding: utf-8 -*-
"""下载重排模型的工具脚本."""

import os
from pathlib import Path

from huggingface_hub import snapshot_download
from loguru import logger


def download_reranker_model():
    """下载 BAAI/bge-reranker-base 模型."""
    model_name = "BAAI/bge-reranker-base"

    # 获取项目根目录 (scripts/models 的上一级的上一级)
    project_root = Path(__file__).parent.parent.parent.absolute()
    save_path = project_root / "data" / "models" / model_name

    logger.info(f"开始下载重排模型 {model_name}...")
    logger.info(f"保存路径: {save_path}")

    try:
        # 设置镜像加速
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        # 使用 huggingface-hub 下载
        snapshot_download(
            repo_id=model_name,
            local_dir=str(save_path),
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "rust_model.ot"],
        )

        logger.info("重排模型下载完成！")

    except Exception as e:
        logger.error(f"下载失败: {e}")
        logger.warning("您可以稍后重试，或手动下载。系统会在未下载成功时回退为基础算法过滤。")


if __name__ == "__main__":
    download_reranker_model()
