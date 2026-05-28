# -*- coding: utf-8 -*-
"""问答工作流编排."""

import asyncio
import re
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from app.core.config import Config
from app.llm.base import LLMAdapter
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter


class QAPipeline:
    """核心问答工作流，解耦组装各个模块."""

    def __init__(
        self,
        config: Config,
        llm_adapter: LLMAdapter,
        vector_store: VectorStoreAdapter,
        reranker: Reranker,
        cache_manager: CacheManager,
        session_manager: SessionManager,
    ):
        self.config = config
        self.llm_adapter = llm_adapter
        self.vector_store = vector_store
        self.reranker = reranker
        self.cache_manager = cache_manager
        self.session_manager = session_manager

        self._llm_lock = asyncio.Lock()
        self.init_errors: List[str] = []

        if not self.llm_adapter or not self.vector_store:
            self.init_errors.append("LLM 或 VectorStore 适配器注入为空")

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
        """从模型输出中清洗并提取最终答案."""
        if not raw_answer:
            return ""

        # 优先使用正则表达式提取 <answer> 标签内部内容
        match = re.search(r"<answer>(.*?)</answer>", raw_answer, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted

        # Fallback 清理逻辑
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
        """处理用户提问，执行完整 QA Pipeline."""
        logger.info(f"收到提问: {question} (Session: {session_id})")

        # 1. 缓存拦截
        cached_result = self.cache_manager.get(question, session_id)
        if cached_result:
            logger.info("命中问答缓存")
            return cached_result

        try:
            # 2. 向量检索
            raw_docs = self.vector_store.similarity_search_with_scores(
                question, k=self.config.search_k * 2
            )

            # 3. 质量重排与过滤
            filtered_docs = self.reranker.rerank_and_filter(raw_docs, question)

            # 4. 构建上下文与历史
            context_str = self.format_context(filtered_docs)
            history = await self.session_manager.get_history(session_id)
            history_str = self.format_history(history)

            # 5. 生成 Prompt
            prompt_template = self._get_prompt_template()
            prompt_value = prompt_template.format(
                context=context_str,
                chat_history=history_str,
                question=question
            )

            # 6. LLM 推理 (加锁防爆)
            async with self._llm_lock:
                raw_answer = self.llm_adapter.generate(prompt_value)

            # 7. 清理并提取答案
            final_answer = self._clean_answer(raw_answer)

            # 8. 记录历史
            await self.session_manager.add_interaction(session_id, question, final_answer)

            # 9. 构造返回结果
            response = {
                "answer": final_answer,
                "sources": [
                    {
                        "title": doc.metadata.get("title", "未知"),
                        "note_id": doc.metadata.get("note_id", ""),
                        "score": score
                    }
                    for doc, score in raw_docs[:len(filtered_docs)]  # 保留分数信息
                ]
            }

            self.cache_manager.set(question, session_id, response)
            return response

        except Exception as e:
            logger.error(f"问答处理失败: {e}")
            return {"answer": f"抱歉，系统处理您的请求时出现错误: {str(e)}", "sources": []}

    def format_context(self, docs: List[Any]) -> str:
        return self._format_context(docs)

    def format_history(self, history: List[Any]) -> str:
        return self._format_history(history)
