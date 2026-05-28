from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import time
from typing import Any

from loguru import logger

from app.core.config import Config, ConfigConstants
from app.core.knowledge_base import KnowledgeBase
from app.core.llm_service import LLMService

try:
    from langchain.chains.question_answering import load_qa_chain
    from langchain.memory import ConversationBufferWindowMemory
    from langchain.prompts import PromptTemplate

    LANGCHAIN_CHAINS_IMPORTED = True
    LANGCHAIN_MEMORY_IMPORTED = True
except ImportError:
    LANGCHAIN_CHAINS_IMPORTED = False
    LANGCHAIN_MEMORY_IMPORTED = False
    ConversationBufferWindowMemory = None

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

        # 存储不同会话的对话记忆
        self.sessions: dict[str, Any] = {}
        self._llm_lock = None
        self._session_lock = None

        # 问答缓存: (question, session_id) -> {result, timestamp}
        self.cache: dict[str, dict[str, Any]] = {}

        # 获取LLM实例

        self.llm = llm_service.get_llm()
        if not self.llm:
            self.init_errors.append("LLM不可用")

        # 创建检索问答链
        if LANGCHAIN_CHAINS_IMPORTED and self.llm and self.knowledge_base.vector_store:
            try:
                # 定义自定义提示词模板，针对检索场景优化
                prompt_template = """你是一个专业的问答助手。请基于以下已知信息和对话历史，简洁专业地回答用户问题。

重要指令：
1. 只返回纯净的答案内容，不要重复任何提示词部分
2. 必须将最终的答案内容包裹在 <answer> 和 </answer> 标签中，例如：<answer>这里是答案</answer>
3. 如果无法从已知信息中得到答案，只回答："<answer>根据检索结果无法回答该问题</answer>"
4. 不允许添加编造成分，全部用中文回答
5. 请在给出答案前进行内部校验，确保回答逻辑严密、事实准确，避免出现常识性或基础性错误，但必须忠实于已知信息，不得随意改动。

已知信息：
{context}

{chat_history}

问题：{question}

答案："""
                prompt = PromptTemplate(
                    template=prompt_template,
                    input_variables=["context", "chat_history", "question"],
                )

                # 创建一个更严格的QA链 (使用 load_qa_chain 以便手动控制检索结果)
                # self.qa_chain = RetrievalQA.from_chain_type(
                #     llm=self.llm,
                #     chain_type="stuff",
                #     retriever=self.knowledge_base.vector_store.as_retriever(search_kwargs={"k": self.config.search_k}),
                #     return_source_documents=True,
                #     output_key="result",
                #     chain_type_kwargs={"prompt": prompt}
                # )

                # 使用 load_qa_chain，它接受 input_documents 参数
                self.qa_chain = load_qa_chain(
                    llm=self.llm,
                    chain_type="stuff",
                    prompt=prompt,
                    verbose=False,  # 关闭详细日志以避免输出完整的Prompt
                )
            except Exception as e:
                error_msg = f"初始化问答链失败: {e}"
                logger.error(error_msg)
                self.init_errors.append(error_msg)
                self.qa_chain = None
        else:
            self.qa_chain = None
            if not LANGCHAIN_CHAINS_IMPORTED:
                self.init_errors.append("Langchain Chains未导入")
            if not self.llm:
                self.init_errors.append("LLM不可用")
            # 注意：向量存储不可用和问答链创建失败是两个不同的问题
            # 即使问答链创建失败，向量存储本身仍可能可用

            # 记录错误信息
            for error in self.init_errors:
                logger.error(error)

    def _get_session_memory(self, session_id: str) -> Any:
        """获取或创建会话记忆.

        Args:
            session_id: 会话ID.

        Returns:
            Any: 对话记忆对象.
        """
        if session_id not in self.sessions:
            if LANGCHAIN_MEMORY_IMPORTED and ConversationBufferWindowMemory:
                try:
                    # 使用窗口记忆，限制存储最近的 10 轮对话，防止内存无限增长
                    self.sessions[session_id] = ConversationBufferWindowMemory(
                        memory_key="chat_history", return_messages=True, k=10
                    )
                    logger.info(f"为会话 {session_id} 创建了新的对话记忆 (窗口大小: 10)")

                except Exception as e:
                    logger.error(f"为会话 {session_id} 创建对话记忆失败: {e}")
                    return None
            else:
                return None
        return self.sessions[session_id]

    def _get_cache_key(self, question: str, session_id: str) -> str:
        """生成缓存键."""
        return f"{session_id}:{question}"

    def _check_cache(self, question: str, session_id: str) -> dict[str, Any] | None:
        """检查缓存是否存在且未过期."""
        cache_key = self._get_cache_key(question, session_id)
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() - entry["timestamp"] < ConfigConstants.QA_CACHE_TTL:
                logger.info(f"命中缓存: {question}")
                return entry["result"]
            else:
                # 过期删除
                del self.cache[cache_key]
        return None

    def _save_cache(self, question: str, session_id: str, result: dict[str, Any]) -> None:
        """保存结果到缓存."""
        # 简单的缓存容量限制
        if len(self.cache) >= ConfigConstants.QA_CACHE_SIZE:
            # 随机删除一个（简单处理）
            self.cache.pop(next(iter(self.cache)))

        cache_key = self._get_cache_key(question, session_id)
        self.cache[cache_key] = {"result": result, "timestamp": time.time()}

    async def ask_question_async(self, question: str, session_id: str = "default") -> dict[str, Any]:
        """异步版本的提问方法，提供更好的并发性能."""
        # 延迟初始化锁，确保在正确的事件循环中
        if self._llm_lock is None:
            self._llm_lock = asyncio.Lock()
        if self._session_lock is None:
            self._session_lock = asyncio.Lock()

        # 1. 检查缓存
        cached_result = self._check_cache(question, session_id)
        if cached_result:
            return cached_result

        # 记录查询开始时间
        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] [Session: {session_id}] 开始异步处理问题: {str(question)[:200]}")

        # 2. 获取会话记忆
        async with self._session_lock:
            memory = self._get_session_memory(session_id)

        try:
            # 3. 执行语义搜索 (异步)
            search_start_time = time.time()
            docs = await self.knowledge_base.semantic_search_async(question, k=self.config.search_k)
            search_duration = time.time() - search_start_time
            logger.info(f"语义搜索完成，耗时: {search_duration:.2f}秒，找到 {len(docs)} 个相关文档")

            if not docs:
                return {
                    "answer": "抱歉，在知识库中没有找到与您的问题相关的上下文信息。",
                    "sources": [],
                }

            # 4. 调用模型 (异步包装)
            model_start_time = time.time()
            logger.info(f"开始调用语言模型 (超时设置: {ConfigConstants.LLM_GENERATION_TIMEOUT}秒)")

            # 获取对话历史
            chat_history = ""
            if memory:
                # load_memory_variables 通常是同步的，如果是简单的 memory
                history_vars = memory.load_memory_variables({})
                chat_history = history_vars.get("chat_history", "")

            try:
                # 使用 to_thread 运行 LLM 调用
                # 排队执行推理，避免多并发打爆本地大模型
                async with self._llm_lock:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.qa_chain.invoke,
                            {
                                "input_documents": docs,
                                "question": question,
                                "chat_history": chat_history,
                            },
                            return_only_outputs=True,
                        ),
                        timeout=ConfigConstants.LLM_GENERATION_TIMEOUT,
                    )

                # 更新对话记忆
                if memory:
                    memory.save_context({"input": question}, {"output": result.get("output_text", "")})

                model_duration = time.time() - model_start_time
                total_duration = time.time() - start_time
                logger.info(f"问答处理完成，总耗时: {total_duration:.2f}秒 (模型耗时: {model_duration:.2f}秒)")

                # 处理结果，确保不包含提示词内容，只保留纯答案
                raw_answer = result.get("output_text", "未能生成答案。")
                clean_answer = self._clean_answer(raw_answer)

                final_result = {
                    "answer": clean_answer,
                    "sources": self._format_sources(documents=docs),
                }

                # 5. 保存结果到缓存
                self._save_cache(question, session_id, final_result)

                return final_result

            except asyncio.TimeoutError:
                logger.error(f"语言模型调用超时 ({ConfigConstants.LLM_GENERATION_TIMEOUT}秒)")
                return {
                    "answer": f"抱歉，AI 生成回答超时（限制为 {ConfigConstants.LLM_GENERATION_TIMEOUT} 秒）。请尝试简化问题或减小检索范围。",
                    "sources": self._format_sources(docs),
                }

        except Exception as e:
            logger.error(f"提问时出错: {e}")
            # 内部错误脱敏处理，不向用户泄露底层异常堆栈
            return {
                "answer": "抱歉，系统处理您的问题时出现了内部错误。请稍后再试或联系管理员。",
                "sources": [],
            }

    def ask_question(self, question: str, session_id: str = "default") -> dict[str, Any]:
        """提出问题并获得答案.

        Args:
            question: 要提出的问题字符串.
            session_id: 会话ID，用于区分不同用户的对话历史.

        Returns:
            dict[str, Any]: 包含答案和来源的字典，格式为:
                {
                    "answer": str,  # 答案文本
                    "sources": list[dict]  # 来源列表
                }
        """

        # 记录查询开始时间
        start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{timestamp}] [Session: {session_id}] 开始处理问题: {question}")

        # 获取会话记忆
        memory = self._get_session_memory(session_id)

        # 检查必要组件是否可用
        if self.knowledge_base.vector_store is None:
            error_details = ""
            if hasattr(self, "init_errors") and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors)
            else:
                error_details = "知识库未正确初始化，请检查配置。"
            return {"answer": error_details, "sources": []}

        # 向量数据库查询开始时间
        db_start_time = time.time()
        db_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{db_timestamp}] 开始向量数据库查询")

        # 即使问答链不可用，也可以直接使用向量存储进行搜索
        # 这样可以在部分组件不可用时提供降级功能

        # 尝试在知识库中搜索相关信息
        try:
            # 1. 获取绝对阈值
            score_threshold = getattr(self.config, "search_score_threshold", 0.5)

            # 基础相似度搜索 (带得分)
            # 我们取较多的初始结果（k*3），以便后续进行质量筛选
            docs_with_scores = self.knowledge_base.vector_store.similarity_search_with_relevance_scores(
                question, k=self.config.search_k * 3, score_threshold=score_threshold
            )

            if not docs_with_scores:
                logger.warning(f"检索结果相关性过低，无文档达到绝对阈值 {score_threshold}")
                return {
                    "answer": "抱歉，在知识库中没有找到足够相关的参考信息，无法给出准确回答。",
                    "sources": [],
                }

            # 2. 质量重排与筛选 (标题加权)
            processed_results = []
            question_keywords = [k.lower() for k in question.split() if len(k) > 1]

            for doc, score in docs_with_scores:
                final_score = score
                title = doc.metadata.get("title", "").lower()

                # # 标题匹配加成 (Boost)
                # for kw in question_keywords:
                #     if kw in title:
                #         final_score += 0.15 # 命中标题给予显著加分
                #         break
                processed_results.append((doc, final_score))

            # 按最终得分从高到低排序
            processed_results.sort(key=lambda x: x[1], reverse=True)

            # 3. 动态筛选：宁缺毋滥逻辑
            # 我们不仅看绝对分数，还要看“质量梯队”。
            # 如果后面的文档比第一名差太多，即便它过了绝对阈值，也不要它。
            top_score = processed_results[0][1]
            # 相对过滤比例：只保留得分不低于最高分 80% 的结果
            relative_ratio = 0.8

            quality_docs = []
            for doc, score in processed_results:
                # 必须满足：1. 不超过设定的最大数量 k；2. 得分足够接近最高分
                if len(quality_docs) < self.config.search_k:
                    if score >= (top_score * relative_ratio):
                        quality_docs.append(doc)
                    else:
                        # 一旦出现断层，后续文档全部放弃
                        break

            docs = quality_docs
            logger.info(f"质量筛选完成：原始召回 {len(docs_with_scores)}，最终保留优质文档 {len(docs)}")

        except Exception as e:
            error_details = ""
            if hasattr(self, "init_errors") and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            return {
                "answer": f"{error_details}搜索知识库时出错: {str(e)}",
                "sources": [],
            }

        # 向量数据库查询结束时间
        db_end_time = time.time()
        db_duration = db_end_time - db_start_time
        db_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[{db_end_timestamp}] 向量数据库查询完成，耗时: {db_duration:.2f}秒")

        if not docs:
            error_details = ""
            if hasattr(self, "init_errors") and self.init_errors:
                error_details = "问答服务初始化失败详情: " + "; ".join(self.init_errors) + "\n\n"
            return {
                "answer": f"{error_details}在知识库中未找到相关信息。",
                "sources": [],
            }

        # 如果LLM可用，使用它生成答案
        if self.qa_chain:
            # 构造Prompt开始时间
            prompt_start_time = time.time()
            prompt_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{prompt_timestamp}] 开始构造Prompt")

            # 显示构造的Prompt内容（仅显示上下文部分）
            context = "\n\n".join([doc.page_content for doc in docs])
            logger.debug(f"[{prompt_timestamp}] 构造的上下文预览: {context[:200]}...")

            # 构造Prompt结束时间
            prompt_end_time = time.time()
            prompt_duration = prompt_end_time - prompt_start_time
            prompt_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{prompt_end_timestamp}] Prompt构造完成，耗时: {prompt_duration:.2f}秒")

            # 调用模型开始时间
            model_start_time = time.time()
            model_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{model_timestamp}] 开始调用语言模型 (超时设置: {ConfigConstants.LLM_GENERATION_TIMEOUT}秒)")

            try:
                # 获取对话历史
                chat_history = ""
                if memory:
                    history_vars = memory.load_memory_variables({})
                    chat_history = history_vars.get("chat_history", "")

                # 使用线程池运行同步的 invoke 调用，以实现超时控制
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        self.qa_chain.invoke,
                        {
                            "input_documents": docs,
                            "question": question,
                            "chat_history": chat_history,
                        },
                        return_only_outputs=True,
                    )
                    try:
                        result = future.result(timeout=ConfigConstants.LLM_GENERATION_TIMEOUT)
                    except concurrent.futures.TimeoutError:
                        logger.error(f"语言模型调用超时 ({ConfigConstants.LLM_GENERATION_TIMEOUT}秒)")
                        return {
                            "answer": f"抱歉，AI 生成回答超时（限制为 {ConfigConstants.LLM_GENERATION_TIMEOUT} 秒）。请尝试简化问题或减小检索范围。",
                            "sources": self._format_sources(docs),
                        }

                # 更新对话记忆
                if memory:
                    memory.save_context({"input": question}, {"output": result.get("output_text", "")})

                # 调用模型结束时间
                model_end_time = time.time()
                model_duration = model_end_time - model_start_time
                model_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[{model_end_timestamp}] 语言模型调用完成，耗时: {model_duration:.2f}秒")

                # 记录总处理时间
                end_time = time.time()
                total_duration = end_time - start_time
                end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"[{end_timestamp}] 问题处理完成，总耗时: {total_duration:.2f}秒")

                # 处理结果，确保不包含提示词内容，只保留纯答案
                raw_answer = result.get("output_text", "")
                answer = self._clean_answer(raw_answer)

                return {"answer": answer, "sources": self._format_sources(docs)}
            except Exception as e:
                logger.error(f"使用问答链时出错: {e}")

                # 调用模型结束时间（出错情况）
                model_end_time = time.time()
                model_duration = model_end_time - model_start_time
                model_end_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.error(f"[{model_end_timestamp}] 语言模型调用出错，耗时: {model_duration:.2f}秒")

        # 如果LLM不可用，提供基于检索的简单回答
        error_details = ""
        if hasattr(self, "init_errors") and self.init_errors:
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
        logger.info(f"[{end_timestamp}] 问题处理完成（无语言模型），总耗时: {total_duration:.2f}秒")

        return {
            "answer": f"{error_details}{answer_content}",
            "sources": self._format_sources(docs),
        }

    def _clean_answer(self, answer: str) -> str:
        """清理LLM返回的答案，提取 <answer> 标签内的内容.

        Args:
            answer: 原始答案字符串

        Returns:
            str: 清理后的纯答案
        """
        if not answer:
            return answer

        import re
        
        # 优先匹配 <answer> 标签内的内容
        match = re.search(r"<answer>(.*?)</answer>", answer, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        # 如果模型没有输出闭合标签，尝试提取 <answer> 之后的内容
        match = re.search(r"<answer>(.*)", answer, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 回退策略：移除可能包含的提示词开头部分，只保留真正的回答内容
        # 1. 定义可能的答案引导词（按优先级排，越准确的越前）
        indicators = [
            "答案：",
            "你的回答：",
            "回答：",
            "答案:",
            "回答:",
            "有帮助的回答:",
        ]

        # 检查是否包含触发短语
        if not any(phrase in answer for phrase in indicators):
            return answer.strip()

        # 2. 从后往前找最后一个标识符
        last_idx = -1
        for indicator in indicators:
            idx = answer.rfind(indicator)
            if idx > last_idx:
                last_idx = idx + len(indicator)

        # 3. 如果找到了，截取后面内容；没找到则处理开头残留
        if last_idx != -1:
            answer = answer[last_idx:]
        else:
            answer = re.sub(r"^(已知内容|对话历史|问题|答案|回答|你的回答)[:：\s]*", "", answer)

        return answer.strip()

    def _format_sources(self, documents: list[Any]) -> list[dict[str, Any]]:
        """格式化源文档.

        Args:
            documents: 源文档列表.

        Returns:
            list[dict[str, Any]]: 格式化后的源列表，每个源包含title、url、source、content字段.
        """

        sources = []
        for doc in documents:
            source = doc.metadata.get("source", "未知")
            title = doc.metadata.get("title", "未知标题")

            # 解析source以获取note_id
            note_id = None
            if source.startswith("trilium:"):
                note_id = source[8:]  # 移除"trilium:"前缀
            elif "note_id" in doc.metadata:
                note_id = doc.metadata.get("note_id")

            # 获取路径信息
            note_path = doc.metadata.get("path", "")

            # 构建Trilium笔记的URL
            # 构建Trilium笔记的URL
            trilium_url = None
            if note_id and hasattr(self.config, "trilium_base_url") and self.config.trilium_base_url:
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

            sources.append(
                {
                    "title": title,
                    "url": trilium_url,
                    "source": source,
                    "content": (doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content),
                }
            )
        return sources
