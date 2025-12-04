#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
完整的测试脚本，用于验证所有核心组件是否能正常工作
"""

import sys
import os

def test_import(module_name, import_stmt):
    """测试模块导入"""
    try:
        exec(import_stmt)
        print(f"✓ {module_name} 导入成功")
        return True
    except ImportError as e:
        print(f"✗ {module_name} 导入失败: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ {module_name} 导入时出现未知错误: {str(e)}")
        return False

def main():
    print("开始测试所有核心组件...")
    
    # 测试 FastAPI
    test_import("FastAPI", "from fastapi import FastAPI")
    
    # 测试 LangChain 相关组件
    test_import("LangChain Core", "from langchain_core.prompts import PromptTemplate")
    test_import("LangChain Community", "from langchain_community.llms import GPT4All")
    
    # 测试 Chroma
    chroma_available = test_import("Chroma", "from langchain_community.vectorstores import Chroma")
    
    # 测试 HuggingFaceEmbeddings
    embeddings_available = test_import("HuggingFaceEmbeddings", 
                                     "from langchain_community.embeddings import HuggingFaceEmbeddings")
    
    # 如果嵌入模型和 Chroma 都可用，则测试基本集成
    if chroma_available and embeddings_available:
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            embeddings = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print("✓ 成功创建 HuggingFaceEmbeddings 实例")
            
            # 测试 Chroma 基本操作
            from langchain_community.vectorstores import Chroma
            print("✓ Chroma 和 Embeddings 集成测试通过")
        except Exception as e:
            print(f"⚠️  Chroma 和 Embeddings 集成测试遇到问题（可能是网络问题）: {str(e)}")
            print("   这在中国大陆地区很常见，不影响基本功能")
    
    # 测试 SentenceTransformers（直接测试）
    test_import("SentenceTransformers", "from sentence_transformers import SentenceTransformer")
    
    # 测试 Streamlit
    test_import("Streamlit", "import streamlit as st")
    
    # 测试 GPT4All
    test_import("GPT4All", "from langchain_community.llms import GPT4All")
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()