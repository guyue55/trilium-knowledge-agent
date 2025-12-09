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
import jieba

# 添加专业术语到jieba词典
jieba.add_word("docker")
jieba.add_word("容器")
jieba.add_word("镜像")
jieba.add_word("volume")
jieba.add_word("network")
jieba.add_word("ddns")
jieba.add_word("部署")
jieba.add_word("命令")


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
                # 定义自定义提示词模板，针对检索场景优化
                prompt_template = """基于以下已知信息，简洁和专业的来回答用户的问题。如果无法从中得到答案，请说 "根据已知信息无法回答该问题"，不允许在答案中添加编造成分，答案请使用中文。

已知内容:
{context}

问题:
{question}

答案:"""
                prompt = PromptTemplate(
                    template=prompt_template, 
                    input_variables=["context", "question"]
                )
                
                # 创建一个更严格的QA链
                self.qa_chain = RetrievalQA.from_chain_type(
                    llm=self.llm,
                    chain_type="stuff",
                    retriever=self.knowledge_base.vector_store.as_retriever(search_kwargs={"k": self.config.search_k}),
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
            # 获取扩展查询
            expanded_questions = self._expand_query(question)
            print(f"扩展查询: {expanded_questions}")
            
            all_docs = []
            
            # 对每个扩展查询进行搜索
            for query in expanded_questions:
                if query != question:
                    print(f"使用扩展查询: {query}")
                
                # 1. 基础相似度搜索
                docs_similarity = self.knowledge_base.vector_store.similarity_search(query, k=4)
                all_docs.extend(docs_similarity)
                if query == question:
                    print(f"相似度搜索返回 {len(docs_similarity)} 个结果")
                
                # 2. 使用MMR搜索获取更多样化的结果
                docs_mmr = self.knowledge_base.vector_store.max_marginal_relevance_search(
                    query, 
                    k=4, 
                    fetch_k=20,
                    lambda_mult=0.3  # 更偏向相关性
                )
                all_docs.extend(docs_mmr)
                if query == question:
                    print(f"MMR搜索返回 {len(docs_mmr)} 个结果")
            
            # 3. 去重并按相关性排序
            docs = []
            seen_note_ids = set()
            doc_scores = {}  # 存储文档得分
            
            # 计算每个文档的得分（出现次数）
            for doc in all_docs:
                note_id = doc.metadata.get('note_id', '')
                if note_id in doc_scores:
                    doc_scores[note_id] += 1
                else:
                    doc_scores[note_id] = 1
            
            # 按得分排序文档
            sorted_docs = []
            for doc in all_docs:
                note_id = doc.metadata.get('note_id', '')
                if note_id not in seen_note_ids:
                    sorted_docs.append((doc, doc_scores[note_id]))
                    seen_note_ids.add(note_id)
            
            # 按得分降序排序
            sorted_docs.sort(key=lambda x: x[1], reverse=True)
            
            # 提取排序后的文档
            docs = [doc for doc, score in sorted_docs][:self.config.search_k]
            print(f"总共合并去重并排序后得到 {len(docs)} 个文档")
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
                # 使用 combine_documents_chain 并传入已检索的 docs (包含MMR和重排序优化的结果)
                # 这样可以确保使用的文档数量符合预期(10个)，且使用了更优的检索策略
                # 之前使用 self.qa_chain.invoke({"query": question}) 会导致 RetrievalQA 重新检索(默认k=5)，忽略了上面的优化
                
                print(f"[{model_timestamp}] 调用文档组合链 (输入文档数: {len(docs)})")
                chain_result = self.qa_chain.combine_documents_chain.invoke({
                    "input_documents": docs,
                    "question": question
                })
                
                # 统一结果格式
                answer_text = chain_result
                if isinstance(chain_result, dict):
                     # StuffDocumentsChain 默认输出 key 通常是 output_text
                     answer_text = chain_result.get("output_text", chain_result.get("text", str(chain_result)))
                
                result = {
                    "result": answer_text,
                    "source_documents": docs
                }
                
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
            
            # 获取路径信息
            note_path = doc.metadata.get('path', '')
            
            # 构建Trilium笔记的URL
            # 构建Trilium笔记的URL
            trilium_url = None
            if note_id and hasattr(self.config, 'trilium_base_url') and self.config.trilium_base_url:
                # 使用完整的路径信息构建URL
                if note_path:
                    # 如果有路径信息，则构建完整路径URL
                    # 如果有路径信息，则构建完整路径URL
                    trilium_url = f"{self.config.trilium_base_url.rstrip('/')}/#root/{note_path}?ntxId={note_id}"
                else:
                    # 如果没有路径信息，则使用自动跳转URL
                    trilium_url = f"{self.config.trilium_base_url.rstrip('/')}/#?noteId={note_id}"
            
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
    
    def _expand_query(self, question: str) -> list:
        """扩展查询以提高检索效果.
        
        Args:
            question: 原始查询
            
        Returns:
            扩展后的查询列表
        """
        expanded_queries = [question]
        
        # 使用jieba进行中文分词
        words = list(jieba.cut(question))
        print(f"查询分词结果: {words}")
        
        # 通用的操作词映射
        operation_mappings = {
            "停止": ["停止", "关闭", "终止", "停用"],
            "启动": ["启动", "运行", "开启", "激活"],
            "删除": ["删除", "移除", "清理", "销毁"],
            "查看": ["查看", "浏览", "列出", "显示", "查询"],
            "部署": ["部署", "安装", "配置", "搭建", "设置"],
            "命令": ["命令", "指令", "方法", "方式", "操作"],
        }
        
        # 通用的技术词映射
        tech_mappings = {
            "容器": ["容器", "docker容器", "实例", "服务", "pod"],
            "镜像": ["镜像", "image", "images"],
            "网络": ["网络", "network", "networks"],
            "数据卷": ["数据卷", "volume", "volumes", "存储"],
            "服务": ["服务", "service", "services"],
        }
        
        # 基于分词结果生成变体查询
        variant_queries = set()
        
        # 处理操作词
        for word in words:
            if word in operation_mappings:
                for variant in operation_mappings[word]:
                    new_query = question.replace(word, variant)
                    if new_query != question:
                        variant_queries.add(new_query)
        
        # 处理技术词
        for word in words:
            if word in tech_mappings:
                for variant in tech_mappings[word]:
                    new_query = question.replace(word, variant)
                    if new_query != question:
                        variant_queries.add(new_query)
        
        expanded_queries.extend(list(variant_queries))
        
        # 添加通用前缀和后缀
        prefixes = ["docker", "如何", "怎样", "怎么"]
        suffixes = ["命令", "方法", "方式", "操作", "步骤", "指南"]
        
        for prefix in prefixes:
            if not question.startswith(prefix):
                expanded_queries.append(f"{prefix}{question}")
        
        for suffix in suffixes:
            if not question.endswith(suffix):
                expanded_queries.append(f"{question}{suffix}")
        
        # 去重并保持原始查询在第一位
        unique_queries = []
        seen = set()
        for query in expanded_queries:
            if query not in seen:
                unique_queries.append(query)
                seen.add(query)
        
        return unique_queries
