# -*- coding: utf-8 -*-
"""用于设置Trilium集成的脚本."""

import sys
import os

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_config
from app.core.trilium_integration import TriliumService


def setup_trilium():
    """设置Trilium集成."""
    print("正在设置Trilium集成...")
    
    # 获取配置
    config = get_config()
    
    # 初始化Trilium服务
    trilium_service = TriliumService(config)
    
    # 加载文档
    print("正在从Trilium加载文档...")
    documents = trilium_service.load_documents()
    
    print(f"已从Trilium加载 {len(documents)} 个文档。")
    
    # 保存文档或按需处理
    # 这只是一个占位符 - 您需要在这里实现实际的逻辑
    
    print("Trilium设置完成。")


if __name__ == "__main__":
    setup_trilium()