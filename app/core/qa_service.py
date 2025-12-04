# -*- coding: utf-8 -*-
"""Trilium知识体代理的问答服务."""

from app.core.config import Config
from app.core.llm_service import LLMService
from app.core.knowledge_base import KnowledgeBase

# 尝试导入langchain组件
try:
    from langchain.chains import RetrievalQA
    from langchain.memory import ConversationBufferMemory
    LANGCHAIN_IMPORTED = True
except ImportError:
    LANGCHAIN_IMPORTED = False
    RetrievalQA = None
    ConversationBufferMemory = None


class QAService:
    """用于处理问答逻辑的服务."""
    
    def __init__(self, config: Config, llm_service: LLMService, knowledge_base: KnowledgeBase) -> None:
        """初始化问答服务.
        
        Args:
            config: 应用程序配置.
            llm_service: 语言模型服务.
            knowledge_base: 知识库服务.
        """
        self.config = config
        self.llm_service = llm_service
        self.knowledge_base = knowledge_base
        self.init_errors = []
        
        # 初始化对话记忆
        if LANGCHAIN_IMPORTED and ConversationBufferMemory:
            try:
                self.memory = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            except Exception as e:
                error_msg = f"初始化对话记忆失败: {e}"
                print(error_msg)
                self.init_errors.append(error_msg)
                self.memory = None
        else:
            error_msg = "ConversationBufferMemory不可用"
            self.init_errors.append(error_msg)
            self.memory = None
        
        # 获取LLM实例
        self.llm = llm_service.get_llm()
        if not self.llm:
            self.init_errors.append("LLM不可用")
        
        # 创建检索问答链
        if (LANGCHAIN_IMPORTED and RetrievalQA and self.llm and 
            self.knowledge_base.vector_store):
            try:
                self.qa_chain = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=self.knowledge_base.vector_store.as_retriever(),
                    memory=self.memory,
                    return_source_documents=True
                )
            except Exception as e:
                error_msg = f"初始化问答链失败: {e}"
                print(error_msg)
                self.init_errors.append(error_msg)
                self.qa_chain = None
        else:
            self.qa_chain = None
            if not LANGCHAIN_IMPORTED:
                self.init_errors.append("Langchain未导入")
            if not RetrievalQA:
                self.init_errors.append("RetrievalQA不可用")
            if not self.llm:
                self.init_errors.append("LLM不可用")
            if not self.knowledge_base.vector_store:
                self.init_errors.append("向量存储不可用")
            
            # 打印错误信息
            for error in self.init_errors:
                print(error)
    
    def ask_question(self, question: str) -> dict:
        """提出问题并获得答案.
        
        Args:
            question: 要提出的问题.
            
        Returns:
            包含答案和来源的字典.
        """
        # 检查必要组件是否可用
        if not self.knowledge_base.vector_store:
            error_details = ""
            if hasattr(self, 'init_errors') and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors)
            else:
                error_details = "知识库未正确初始化，请检查配置。"
            return {
                "answer": error_details,
                "sources": []
            }
        
        # 尝试在知识库中搜索相关信息
        try:
            docs = self.knowledge_base.vector_store.similarity_search(question, k=3)
        except Exception as e:
            error_details = ""
            if hasattr(self, 'init_errors') and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            return {
                "answer": f"{error_details}搜索知识库时出错: {str(e)}",
                "sources": []
            }
        
        if not docs:
            error_details = ""
            if hasattr(self, 'init_errors') and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            return {
                "answer": f"{error_details}在知识库中未找到相关信息。",
                "sources": []
            }
        
        # 如果LLM可用，使用它生成答案
        if self.qa_chain:
            try:
                result = self.qa_chain({"query": question})
                return {
                    "answer": result["result"],
                    "sources": self._format_sources(result.get("source_documents", []))
                }
            except Exception as e:
                print(f"使用问答链时出错: {e}")
        
        # 如果LLM不可用，提供基于检索的简单回答
        error_details = ""
        if hasattr(self, 'init_errors') and self.init_errors:
            error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            
        # 即使没有LLM，也要返回基于检索的信息
        # 整合多个文档的内容，提供更全面的回答
        answer_parts = []
        for i, doc in enumerate(docs, 1):
            content = doc.page_content[:800]  # 增加内容长度到800字符
            if len(doc.page_content) > 800:
                content += "..."
            answer_parts.append(f"文档 {i}:\n{content}")
        
        answer_content = "已找到相关文档，但语言模型不可用。以下是相关内容：\n\n" + "\n\n---\n\n".join(answer_parts)
        return {
            "answer": f"{error_details}{answer_content}",
            "sources": self._format_sources(docs)
        }
    
    def _format_sources(self, documents) -> list:
        """格式化源文档.
        
        Args:
            documents: 源文档.
            
        Returns:
            格式化的源.
        """
        sources = []
        for doc in documents:
            source = doc.metadata.get("source", "未知")
            title = doc.metadata.get("title", "未知标题")
            
            # 解析source以获取note_id
            note_id = None
            if source.startswith("trilium:"):
                note_id = source[8:]  # 移除"trilium:"前缀
            elif 'note_id' in doc.metadata:
                note_id = doc.metadata.get('note_id')
            
            # 构建Trilium笔记的URL
            trilium_url = None
            if note_id and hasattr(self.config, 'trilium_base_url') and self.config.trilium_base_url:
                # 构造Trilium笔记的URL
                trilium_url = f"{self.config.trilium_base_url.rstrip('/')}/#root?noteId={note_id}"
            
            # 确保标题不为空
            if not title or title.strip() == "":
                title = "未知标题"
            
            sources.append({
                "title": title,
                "url": trilium_url,
                "source": source,
                "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            })
        return sources