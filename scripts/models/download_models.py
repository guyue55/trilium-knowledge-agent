# -*- coding: utf-8 -*-
"""模型下载脚本，用于自动下载嵌入模型和语言模型."""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import get_config


def download_embedding_model():
    """下载嵌入模型."""
    try:
        from huggingface_hub import snapshot_download

        config = get_config()

        # 设置镜像源
        if config.hf_endpoint:
            os.environ["HF_ENDPOINT"] = config.hf_endpoint
            print(f"使用镜像源: {config.hf_endpoint}")

        # 创建模型目录
        local_path = Path(config.embedding_model_local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"开始下载嵌入模型: {config.embedding_model}")
        print(f"保存到: {local_path}")

        # 下载模型
        snapshot_download(
            repo_id=config.embedding_model,
            local_dir=str(local_path),
            local_dir_use_symlinks=False,
        )
        print("嵌入模型下载完成!")

    except Exception as e:
        print(f"下载嵌入模型时出错: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


def main():
    """主函数."""
    print("开始下载所需模型...")

    # 下载嵌入模型
    print("\n=== 下载嵌入模型 ===")
    if not download_embedding_model():
        print("嵌入模型下载失败!")
        return False

    print("\n所有模型下载完成!")
    return True


if __name__ == "__main__":
    main()
