# -*- coding: utf-8 -*-
"""智能问答编排服务.

作为领域服务层(Service Layer)，负责协调大模型、历史记录、缓存和检索服务。
"""

import asyncio
import re
from typing import Any, Dict, List

from loguru import logger

from app.llm.base import LLMAdapter
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager, MemoryManager
from app.services.retrieval_service import RetrievalService
from app.services.intent_router import IntentRouter


class QAService:
    """专职于问答编排的业务层服务."""

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        retrieval_service: RetrievalService,
        cache_manager: CacheManager,
        session_manager: SessionManager,
        memory_manager: MemoryManager,
    ):
        self.llm_adapter = llm_adapter
        self.retrieval_service = retrieval_service
        self.cache_manager = cache_manager
        self.session_manager = session_manager
        self.memory_manager = memory_manager
        self.intent_router = IntentRouter()
        # Session-level 锁机制，杜绝对全局多租户/多会话并发的任何排队阻塞
        # 引入 WeakValueDictionary，弱引用自动垃圾回收防止局部锁仅增不减的缓慢内存泄漏
        import weakref
        self._session_locks = weakref.WeakValueDictionary()
        self._session_locks_lock = asyncio.Lock()

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """注册并获取指定会话的局部 Lock，保障单 Session 时序一致性的同时，实现全局多会话完全并行 (弱引用防泄漏自愈)."""
        async with self._session_locks_lock:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._session_locks[session_id] = lock
            return lock

    def _get_chitchat_prompt_template(self) -> str:
        return """你是一个友好、优雅、聪明的 AI 助手。

【长期记忆与用户偏好】：
{agent_memory}

请以亲切自然、充满科技感和温暖的语气回复用户的日常闲聊、问候或简单互动。如果你认识这个用户（长期记忆中有记录），请展现出亲切的主动问候与背景融入！
要求：
1. 必须使用中文回答。
2. 保持回答得体、简洁、幽默且专业，展现出 Google 风格的高级质感。
3. 必须将你的最终答案包裹在 <answer> 和 </answer> 标签之间！！！

对话历史：
{chat_history}

用户问题：{question}
"""

    def _get_general_prompt_template(self) -> str:
        return """你是一个友好、优雅、聪明的 AI 助手。

【长期记忆与用户偏好】：
{agent_memory}

由于用户的提问超出了你当前专属知识库的覆盖范围，请基于你的通用知识为用户提供高水平的解答。如果你认识这个用户（长期记忆中有记录），请结合他的偏好、OS 或项目背景来定制你的回答！
要求：
1. 必须使用中文回答。
2. 展现出你渊博的知识，保持得体、专业且充满 Google 风格的高级质感。
3. 必须将你的最终答案包裹在 <answer> 和 </answer> 标签之间！！！

对话历史：
{chat_history}

用户问题：{question}
"""

    def _get_prompt_template(self) -> str:
        return """你是一个专门解答基于知识库内容问题的智能助手。

【长期记忆与用户偏好】：
{agent_memory}

【参考信息（RAG 知识片段）】：
{context}

要求：
1. 必须使用中文回答。
2. 你的回答必须完全基于上述【参考信息】，不要编造参考信息中没有的内容。如果参考信息中无法得出答案，请直接回复"根据提供的知识库信息，我无法回答这个问题"。
3. 必须确保你回答中的每一个核心技术事实句尾，使用 `[i]` 标号注明其来源（其中 i 是参考信息中的“参考 i”的数字标号，例如：`这是事实[1]。这是另外一个事实[2]`）。
4. 绝对禁止对没有事实来源的句子打上引用角标。禁止编造不存在的角标，引用的角标必须 100% 存在于上述参考信息列表中！
5. 必须将你的最终答案包裹在 <answer> 和 </answer> 标签之间！！！

对话历史：
{chat_history}

用户问题：{question}
"""

    def _clean_answer(self, raw_answer: str) -> str:
        if not raw_answer:
            return ""

        match = re.search(r"<answer>(.*?)</answer>", raw_answer, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted

        cleaned = raw_answer.replace("<answer>", "").replace("</answer>", "").strip()
        prefixes_to_remove = ["AI助手:", "助手:", "AI:", "根据提供的参考信息，", "根据知识库内容，", "答案：", "回答："]
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned

    def _format_history(self, history: List[Any]) -> str:
        if not history:
            return "无"
        formatted = []
        for msg in history:
            role = "User" if msg.role == "user" else "AI"
            formatted.append(f"{role}: {msg.content}")
        return "\n".join(formatted)


    def _format_context(self, docs: List[Any]) -> str:
        if not docs:
            return "没有找到相关参考信息。"
        contexts = []
        for i, doc in enumerate(docs):
            title = doc.metadata.get("title", "未知来源")
            contexts.append(f"[参考 {i+1}] 来源：{title}\n内容：{doc.page_content}\n")
        return "\n".join(contexts)

    async def ask(self, question: str, session_id: str = "default") -> Dict[str, Any]:
        """处理用户提问，执行完整 QA 编排."""
        logger.info(f"QAService: 收到提问 '{question}' (Session: {session_id})")

        if self.cache_manager:
            cached_result = self.cache_manager.get(question, session_id)
            if cached_result:
                logger.info("QAService: 命中问答缓存，直接返回")
                return cached_result

        try:
            # 1. 前置意图分类与 RAG 检索并行化 (Milestone 18: Speculative Concurrency)
            # 利用 asyncio.gather 并发化 CPU 密集正则拦截与 I/O 密集型数据库检索
            intent_task = asyncio.create_task(asyncio.to_thread(self.intent_router.classify, question))
            retrieval_task = asyncio.create_task(self.retrieval_service.retrieve_and_rerank(question))
            
            intent, (filtered_docs, raw_docs) = await asyncio.gather(intent_task, retrieval_task)
            
            if intent == "CHITCHAT":
                filtered_docs = []
                raw_docs = []
                context_str = "无"
                prompt_template = self._get_chitchat_prompt_template()
            else:
                if not filtered_docs:
                    logger.info(f"QAService: 检索重排后没有满足阈值的核心切片，自动切换至 [GENERAL_CHAT] 通用自由对话模式。")
                    intent = "GENERAL_CHAT"
                    context_str = "无"
                    prompt_template = self._get_general_prompt_template()
                else:
                    context_str = self._format_context(filtered_docs)
                    prompt_template = self._get_prompt_template()

            # 2. 构建上下文与历史以及长期记忆
            if self.session_manager:
                history = await self.session_manager.get_history(session_id)
                history_str = self._format_history(history)
            else:
                history_str = "无"

            agent_memory = await self.memory_manager.get_memory()
            if self.session_manager:
                session_summary = await self.session_manager.get_summary(session_id)
                if session_summary:
                    agent_memory = f"{agent_memory}\n\n【当前会话历史演进背景摘要（Session Background Summary）】:\n{session_summary}"

            # 3. 生成 Prompt
            if intent in ("CHITCHAT", "GENERAL_CHAT"):
                prompt_value = prompt_template.format(
                    agent_memory=agent_memory,
                    chat_history=history_str,
                    question=question
                )
            else:
                prompt_value = prompt_template.format(
                    agent_memory=agent_memory,
                    context=context_str,
                    chat_history=history_str,
                    question=question
                )

            # 4. LLM 推理 (使用 Session 局部锁，杜绝全局阻塞)
            session_lock = await self._get_session_lock(session_id)
            async with session_lock:
                raw_answer = await asyncio.to_thread(
                    self.llm_adapter.generate,
                    prompt_value
                )

            # 5. 清理答案并记录历史
            final_answer = self._clean_answer(raw_answer)
            if self.session_manager:
                await self.session_manager.add_interaction(session_id, question, final_answer, self.llm_adapter)

            # 5.1 异步自主突变更新长期记忆 Markdown（不阻塞实时响应）
            asyncio.create_task(
                self.memory_manager.update_memory_autonomously(
                    self.llm_adapter, question, final_answer
                )
            )

            # 6. 构造返回结果
            response = {
                "answer": final_answer,
                "sources": [
                    {
                        "title": doc.metadata.get("title", "未知"),
                        "note_id": doc.metadata.get("note_id", ""),
                        "content": doc.page_content,
                        "score": doc.metadata.get("score", 0.0),
                        "path": doc.metadata.get("path", "")
                    }
                    for doc in filtered_docs
                ]
            }

            if self.cache_manager:
                self.cache_manager.set(question, session_id, response)
            return response

        except Exception as e:
            logger.error(f"QAService 处理失败: {e}")
            return {
                "answer": "抱歉，系统处理您的请求时出现错误。",
                "sources": [],
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "系统处理请求时出现错误",
                    "details": str(e)
                }
            }

    async def ask_stream(self, question: str, session_id: str = "default"):
        """流式处理用户提问."""
        logger.info(f"QAService: 流式收到提问 '{question}' (Session: {session_id})")

        if self.cache_manager:
            cached_result = self.cache_manager.get(question, session_id)
            if cached_result:
                logger.info("QAService: 流式命中问答缓存，直接返回")
                yield {"type": "sources", "data": cached_result.get("sources", [])}
                yield {"type": "chunk", "data": cached_result["answer"]}
                return

        try:
            # 1. 前置意图分类与 RAG 检索并行化 (Milestone 18: Speculative Concurrency)
            # 利用 asyncio.gather 并发化 CPU 密集正则拦截与 I/O 密集型数据库检索
            intent_task = asyncio.create_task(asyncio.to_thread(self.intent_router.classify, question))
            retrieval_task = asyncio.create_task(self.retrieval_service.retrieve_and_rerank(question))
            
            intent, (filtered_docs, raw_docs) = await asyncio.gather(intent_task, retrieval_task)
            
            if intent == "CHITCHAT":
                filtered_docs = []
                raw_docs = []
                sources = []
                context_str = "无"
                prompt_template = self._get_chitchat_prompt_template()
            else:
                if not filtered_docs:
                    logger.info(f"QAService: 流式检索重排后没有满足阈值的核心切片，自动切换至 [GENERAL_CHAT] 通用自由对话模式。")
                    intent = "GENERAL_CHAT"
                    sources = []
                    context_str = "无"
                    prompt_template = self._get_general_prompt_template()
                else:
                    sources = [
                        {
                            "title": doc.metadata.get("title", "未知"),
                            "note_id": doc.metadata.get("note_id", ""),
                            "content": doc.page_content,
                            "score": doc.metadata.get("score", 0.0),
                            "path": doc.metadata.get("path", "")
                        }
                        for doc in filtered_docs
                    ]
                    context_str = self._format_context(filtered_docs)
                    prompt_template = self._get_prompt_template()
            
            yield {"type": "sources", "data": sources}

            # 2. 构建上下文与历史以及长期记忆
            if self.session_manager:
                history = await self.session_manager.get_history(session_id)
                history_str = self._format_history(history)
            else:
                history_str = "无"

            agent_memory = await self.memory_manager.get_memory()
            if self.session_manager:
                session_summary = await self.session_manager.get_summary(session_id)
                if session_summary:
                    agent_memory = f"{agent_memory}\n\n【当前会话历史演进背景摘要（Session Background Summary）】:\n{session_summary}"

            # 3. 生成 Prompt
            if intent in ("CHITCHAT", "GENERAL_CHAT"):
                prompt_value = prompt_template.format(
                    agent_memory=agent_memory,
                    chat_history=history_str,
                    question=question
                )
            else:
                prompt_value = prompt_template.format(
                    agent_memory=agent_memory,
                    context=context_str,
                    chat_history=history_str,
                    question=question
                )

            # 4. LLM 推理 (流式) (使用 Session 局部锁，杜绝全局阻塞)
            full_answer = ""
            session_lock = await self._get_session_lock(session_id)
            async with session_lock:
                async for chunk in self.llm_adapter.agenerate_stream(prompt_value):
                    full_answer += chunk
                    clean_chunk = chunk.replace("<answer>", "").replace("</answer>", "").replace("<ANSWER>", "").replace("</ANSWER>", "")
                    if clean_chunk:
                        yield {"type": "chunk", "data": clean_chunk}

            # 5. 清理答案并记录历史
            final_answer = self._clean_answer(full_answer)
            if self.session_manager:
                await self.session_manager.add_interaction(session_id, question, final_answer, self.llm_adapter)

            # 5.1 异步自主突变更新长期记忆 Markdown（不阻塞实时响应）
            asyncio.create_task(
                self.memory_manager.update_memory_autonomously(
                    self.llm_adapter, question, final_answer
                )
            )

            # 6. 保存缓存
            if self.cache_manager:
                self.cache_manager.set(question, session_id, {
                    "answer": final_answer,
                    "sources": sources
                })

        except Exception as e:
            logger.error(f"QAService 流式处理失败: {e}")
            yield {"type": "error", "data": {
                "code": "INTERNAL_ERROR",
                "message": "系统处理请求时出现错误",
                "details": str(e)
            }}
