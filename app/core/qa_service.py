import time
import datetime
from app.core.config import Config
from app.core.llm_service import LLMService
from app.core.knowledge_base import KnowledgeBase

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
LANGCHAIN_CHAINS_IMPORTED = True
from langchain.memory import ConversationBufferMemory
LANGCHAIN_MEMORY_IMPORTED = True

LANGCHAIN_IMPORTED = LANGCHAIN_CHAINS_IMPORTED and LANGCHAIN_MEMORY_IMPORTED


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
        if LANGCHAIN_MEMORY_IMPORTED and ConversationBufferMemory:
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
        if (LANGCHAIN_CHAINS_IMPORTED and RetrievalQA and self.llm and 
            self.knowledge_base.vector_store):
            try:
                # 定义自定义提示词模板
                prompt_template = """使用以下上下文来回答最后的问题。如果你不知道答案，就说你不知道，不要试图编造答案。

{context}

问题: {question}

有帮助的回答:"""
                prompt = PromptTemplate(
                    template=prompt_template, 
                    input_variables=["context", "question"]
                )
                
                # 创建一个更严格的QA链
                self.qa_chain = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=self.knowledge_base.vector_store.as_retriever(),
                    # 暂时禁用内存以排除问题
                    # memory=self.memory,
                    return_source_documents=True,
                    output_key="result",
                    chain_type_kwargs={"prompt": prompt}
                )
            except Exception as e:
                error_msg = f"初始化问答链失败: {e}"
                print(error_msg)
                self.init_errors.append(error_msg)
                self.qa_chain = None
        else:
            self.qa_chain = None
            if not LANGCHAIN_CHAINS_IMPORTED:
                self.init_errors.append("Langchain Chains未导入")
            if not RetrievalQA:
                self.init_errors.append("RetrievalQA不可用")
            if not self.llm:
                self.init_errors.append("LLM不可用")
            # 注意：向量存储不可用和问答链创建失败是两个不同的问题
            # 即使问答链创建失败，向量存储本身仍可能可用
            
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
        # 记录查询开始时间
        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 开始处理问题: {question}")
        
        # 检查必要组件是否可用
        print(f"调试: knowledge_base={self.knowledge_base}")
        print(f"调试: knowledge_base.vector_store={self.knowledge_base.vector_store}")
        print(f"调试: knowledge_base.vector_store is None={self.knowledge_base.vector_store is None}")
        if self.knowledge_base.vector_store is None:
            error_details = ""
            if hasattr(self, 'init_errors') and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors)
            else:
                error_details = "知识库未正确初始化，请检查配置。"
            return {
                "answer": error_details,
                "sources": []
            }
        
        # 向量数据库查询开始时间
        db_start_time = time.time()
        db_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{db_timestamp}] 开始向量数据库查询")
        
        # 即使问答链不可用，也可以直接使用向量存储进行搜索
        # 这样可以在部分组件不可用时提供降级功能
        
        # 尝试在知识库中搜索相关信息
        try:
            docs = self.knowledge_base.vector_store.similarity_search(question, k=2)  # 从3减少到2
        except Exception as e:
            error_details = ""
            if hasattr(self, 'init_errors') and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            return {
                "answer": f"{error_details}搜索知识库时出错: {str(e)}",
                "sources": []
            }
        
        # 向量数据库查询结束时间
        db_end_time = time.time()
        db_duration = db_end_time - db_start_time
        db_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{db_end_timestamp}] 向量数据库查询完成，耗时: {db_duration:.2f}秒")
        
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
            # 构造Prompt开始时间
            prompt_start_time = time.time()
            prompt_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{prompt_timestamp}] 开始构造Prompt")
            
            # 显示构造的Prompt内容（仅显示上下文部分）
            context = "\n\n".join([doc.page_content for doc in docs])
            print(f"[{prompt_timestamp}] 构造的上下文预览: {context[:200]}...")
            
            # 构造Prompt结束时间
            prompt_end_time = time.time()
            prompt_duration = prompt_end_time - prompt_start_time
            prompt_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{prompt_end_timestamp}] Prompt构造完成，耗时: {prompt_duration:.2f}秒")
            
            # 调用模型开始时间
            model_start_time = time.time()
            model_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{model_timestamp}] 开始调用语言模型")
            
            try:
                # 使用invoke方法替代已弃用的__call__方法
                result = self.qa_chain.invoke({"query": question})
                
                # 调用模型结束时间
                model_end_time = time.time()
                model_duration = model_end_time - model_start_time
                model_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{model_end_timestamp}] 语言模型调用完成，耗时: {model_duration:.2f}秒")
                
                # 记录总处理时间
                end_time = time.time()
                total_duration = end_time - start_time
                end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{end_timestamp}] 问题处理完成，总耗时: {total_duration:.2f}秒")
                
                # 处理结果，确保不包含提示词内容
                answer = result["result"]
                # 移除可能包含的提示词开头部分，只保留真正的回答内容
                trigger_phrases = ["请根据以下上下文回答问题", "基于以下已知信息", "请直接回答问题", "使用以下上下文来回答最后的问题"]
                answer_indicators = ["回答：", "答案:", "回答:", "答案：", "有帮助的回答:"]
                
                # 检查是否包含触发短语
                if any(phrase in answer for phrase in trigger_phrases):
                    # 查找最后一个答案标识符的位置
                    answer_start_index = -1
                    for indicator in answer_indicators:
                        index = answer.rfind(indicator)
                        if index != -1 and index > answer_start_index:
                            answer_start_index = index + len(indicator)
                    
                    # 如果找到了答案标识符，则提取之后的内容
                    if answer_start_index != -1:
                        answer = answer[answer_start_index:].strip()
                
                return {
                    "answer": answer,
                    "sources": self._format_sources(result.get("source_documents", []))
                }
            except Exception as e:
                print(f"使用问答链时出错: {e}")
                
                # 调用模型结束时间（出错情况）
                model_end_time = time.time()
                model_duration = model_end_time - model_start_time
                model_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{model_end_timestamp}] 语言模型调用出错，耗时: {model_duration:.2f}秒")
        
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
        
        # 记录总处理时间
        end_time = time.time()
        total_duration = end_time - start_time
        end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{end_timestamp}] 问题处理完成（无语言模型），总耗时: {total_duration:.2f}秒")
        
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