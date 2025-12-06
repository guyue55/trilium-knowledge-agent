# -*- coding: utf-8 -*-
"""用于更新知识库的脚本."""

import sys
import os

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_config
from app.core.trilium_integration import TriliumService
from app.core.knowledge_base import KnowledgeBase
from langchain.docstore.document import Document


def update_knowledge_base():
    """使用来自Trilium的最新文档更新知识库."""
    print("正在更新知识库...")
    
    # 获取配置
    config = get_config()
    
    # 临时增加限制以获取更多文档（全量更新）
    # 默认可能只有500，增加到10000以确保覆盖大部分知识库
    config.limit = 10000
    print(f"已设置文档获取限制为: {config.limit}")
    
    # 初始化服务
    trilium_service = TriliumService(config)
    knowledge_base = KnowledgeBase(config)
    
    # 从Trilium加载文档
    print("正在从Trilium加载文档...")
    raw_documents = trilium_service.load_documents()
    
    # 转换为Document对象
    documents = []
    for doc in raw_documents:
        # 确保标题不为空
        title = doc.get('title', '未知标题')
        if not title or title.strip() == "":
            title = "未知标题"
            
        # 创建Document对象
        document = Document(
            page_content=doc.get('content', ''),
            metadata={
                'title': title,
                'note_id': doc.get('note_id', ''),
                'source': f"trilium:{doc.get('note_id', '')}"
            }
        )
        documents.append(document)
    
    print(f"已从Trilium加载 {len(documents)} 个文档。")
    
    if len(documents) > 0:
        # 为了保证知识库的准确性，执行全量更新
        # 先清空现有的向量存储
        print("正在清空旧的向量数据...")
        knowledge_base.clear_vector_store()
        
        # 更新向量存储
        print("正在更新向量存储...")
        knowledge_base.update_vector_store(documents)
        
        print("知识库更新成功。")
    else:
        print("未加载到任何文档，跳过更新。")


if __name__ == "__main__":
    update_knowledge_base()