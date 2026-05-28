# -*- coding: utf-8 -*-
"""用于设置Trilium集成的脚本."""

import os
import sys

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_config
from app.core.trilium_integration import TriliumService
from scripts.update_knowledge_base import update_knowledge_base


def setup_trilium():
    """设置Trilium集成."""
    print("正在设置Trilium集成...")

    # 更新知识库
    update_knowledge_base()

    print("Trilium设置完成。")


if __name__ == "__main__":
    setup_trilium()
