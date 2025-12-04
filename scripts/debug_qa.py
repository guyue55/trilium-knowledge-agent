# -*- coding: utf-8 -*-
"""调试脚本，用于检查问答服务的sources格式化."""

import sys
import os

# 将项目根目录添加到路径中
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_config
from app.core.qa_service import QAService
from app.core.llm_service import LLMService
from app.core.knowledge_base import KnowledgeBase

def debug_qa():
    """检查问答服务返回的sources."""
    print("正在检查问答服务...")
    
    # 获取配置
    config = get_config()
    
    # 初始化服务
    llm_service = LLMService(config)
    knowledge_base = KnowledgeBase(config)
    qa_service = QAService(config, llm_service, knowledge_base)
    
    # 提出一个问题
    question = "你好"
    print(f"问题: {question}")
    
    # 获取回答
    result = qa_service.ask_question(question)
    
    print("\n回答:")
    print(result["answer"])
    
    print("\n来源:")
    sources = result.get("sources", [])
    for i, source in enumerate(sources, 1):
        print(f"来源 {i}:")
        if isinstance(source, dict):
            print(f"  标题: {source.get('title', '未知标题')}")
            print(f"  URL: {source.get('url', '无')}")
            print(f"  内容: {source.get('content', '无内容')[:100]}...")
        else:
            print(f"  {source}")

if __name__ == "__main__":
    debug_qa()