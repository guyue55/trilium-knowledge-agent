# -*- coding: utf-8 -*-
"""智能问答编排服务.

作为领域服务层(Service Layer)，负责协调大模型、历史记录、缓存和检索服务。
"""

import asyncio
import re
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from app.llm.base import LLMAdapter
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager
from app.services.retrieval_service import RetrievalService


class QAService:
    """专职于问答编排的业务层服务."""

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        retrieval_service: RetrievalService,
        cache_manager: CacheManager,
        session_manager: SessionManager,
    ):
        self.llm_adapter = llm_adapter
        self.retrieval_service = retrieval_service
        self.cache_manager = cache_manager
        self.session_manager = session_manager

        self._llm_lock = asyncio.Lock()

    def _get_prompt_template(self) -> ChatPromptTemplate:
        template = """你是一个专门解答基于知识库内容问题的智能助手。
请根据以下检索到的参考信息和对话历史来回答用户的问题。
要求：
1. 必须使用中文回答。
2. 你的回答必须完全基于参考信息，不要编造参考信息中没有的内容。如果参考信息中无法得出答案，请直接回复"根据提供的知识库信息，我无法回答这个问题"。
3. 请尽可能给出详细、准确的回答，可以引用原文。
4. 必须将你的最终答案包裹在 <answer> 和 </answer> 标签之间！！！

参考信息：
{context}

对话历史：
{chat_history}

用户问题：{question}
"""
        return ChatPromptTemplate.from_template(template)

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
            role = "User" if msg.type == "human" else "AI"
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

        cached_result = self.cache_manager.get(question, session_id)
        if cached_result:
            logger.info("QAService: 命中问答缓存，直接返回")
            return cached_result

        try:
            # 1. 委托检索服务
            filtered_docs, raw_docs = await self.retrieval_service.retrieve_and_rerank(question)

            # 2. 构建上下文与历史
            context_str = self._format_context(filtered_docs)
            history = await self.session_manager.get_history(session_id)
            history_str = self._format_history(history)

            # 3. 生成 Prompt
            prompt_template = self._get_prompt_template()
            prompt_value = prompt_template.format(
                context=context_str,
                chat_history=history_str,
                question=question
            )

            # 4. LLM 推理
            async with self._llm_lock:
                raw_answer = await asyncio.to_thread(
                    self.llm_adapter.generate,
                    prompt_value
                )

            # 5. 清理答案并记录历史
            final_answer = self._clean_answer(raw_answer)
            await self.session_manager.add_interaction(session_id, question, final_answer)

            # 6. 构造返回结果
            response = {
                "answer": final_answer,
                "sources": [
                    {
                        "title": doc.metadata.get("title", "未知"),
                        "note_id": doc.metadata.get("note_id", ""),
                        "content": doc.page_content,
                        "score": score
                    }
                    for doc in filtered_docs
                    for raw_doc, score in raw_docs if raw_doc == doc
                ]
            }

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

        cached_result = self.cache_manager.get(question, session_id)
        if cached_result:
            logger.info("QAService: 流式命中问答缓存，直接返回")
            yield {"type": "sources", "data": cached_result.get("sources", [])}
            yield {"type": "chunk", "data": cached_result["answer"]}
            return

        try:
            # 1. 委托检索服务
            filtered_docs, raw_docs = await self.retrieval_service.retrieve_and_rerank(question)
            
            sources = []
            for doc in filtered_docs:
                for raw_doc, score in raw_docs:
                    if raw_doc == doc:
                        sources.append({
                            "title": doc.metadata.get("title", "未知"),
                            "note_id": doc.metadata.get("note_id", ""),
                            "content": doc.page_content,
                            "score": score
                        })
                        break
            
            yield {"type": "sources", "data": sources}

            # 2. 构建上下文与历史
            context_str = self._format_context(filtered_docs)
            history = await self.session_manager.get_history(session_id)
            history_str = self._format_history(history)

            # 3. 生成 Prompt
            prompt_template = self._get_prompt_template()
            prompt_value = prompt_template.format(
                context=context_str,
                chat_history=history_str,
                question=question
            )

            # 4. LLM 推理 (流式)
            full_answer = ""
            async with self._llm_lock:
                async for chunk in self.llm_adapter.agenerate_stream(prompt_value):
                    full_answer += chunk
                    yield {"type": "chunk", "data": chunk}

            # 5. 清理答案并记录历史
            final_answer = self._clean_answer(full_answer)
            await self.session_manager.add_interaction(session_id, question, final_answer)

            # 6. 保存缓存
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
