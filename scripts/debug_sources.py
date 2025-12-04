# -*- coding: utf-8 -*-
"""调试脚本，用于检查向量存储中的文档元数据."""

import sys
import os

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_config
from app.core.knowledge_base import KnowledgeBase

def debug_sources():
    """检查向量存储中的文档元数据."""
    print("正在检查向量存储中的文档元数据...")
    
    # 获取配置
    config = get_config()
    
    # 初始化知识库
    knowledge_base = KnowledgeBase(config)
    
    if not knowledge_base.vector_store:
        print("向量存储未正确初始化")
        return
    
    print("向量存储初始化成功")
    
    # 搜索所有文档
    try:
        documents = knowledge_base.semantic_search("测试", k=10)
        print(f"找到 {len(documents)} 个文档:")
        
        for i, doc in enumerate(documents, 1):
            print(f"\n文档 {i}:")
            print(f"  内容预览: {doc.page_content[:100]}...")
            print(f"  元数据: {doc.metadata}")
            
            # 检查关键字段
            title = doc.metadata.get('title', '未知标题')
            source = doc.metadata.get('source', '未知来源')
            note_id = doc.metadata.get('note_id', '未知ID')
            
            print(f"  标题: '{title}'")
            print(f"  来源: {source}")
            print(f"  笔记ID: {note_id}")
            
    except Exception as e:
        print(f"搜索文档时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_sources()
    input("按回车键退出...")  # 等待用户按键