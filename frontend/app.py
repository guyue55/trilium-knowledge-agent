# -*- coding: utf-8 -*-
"""
Trilium知识库智能体的Streamlit前端.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests
import streamlit as st

# 从环境变量获取API URL或使用默认值
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")


def get_headers(api_key: str) -> dict[str, str]:
    """构造请求头."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def send_question(question: str, session_id: str, api_key: str) -> dict[str, Any] | None:
    """向后端API发送问题.

    Args:
        question: 要发送的问题.
        session_id: 独占会话ID.
        api_key: 安全密钥.

    Returns:
        API的响应或None（如果请求失败）.
    """
    try:
        response = requests.post(
            f"{API_URL}/ask",
            json={"question": question, "session_id": session_id},
            headers=get_headers(api_key),
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        if e.response is not None:
            try:
                error_data = e.response.json()
                st.error(f"❌ 错误 ({e.response.status_code}): {error_data.get('detail', e.response.text)}")
            except ValueError:
                st.error(f"❌ 错误 ({e.response.status_code}): {e.response.text}")
        else:
            st.error(f"❌ 连接后端时出错: {e}")
        return None

def clear_backend_session(session_id: str, api_key: str) -> None:
    """通知后端清理指定会话."""
    try:
        requests.delete(f"{API_URL}/session/{session_id}", headers=get_headers(api_key), timeout=2)
    except Exception as e:
        st.warning(f"清除后端缓存失败: {e}")

def get_backend_status(api_key: str) -> dict[str, Any] | None:
    """获取后端健康状态."""
    try:
        response = requests.get(f"{API_URL}/status", headers=get_headers(api_key), timeout=2)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def display_sources(sources: list[Any]) -> None:
    """显示来源信息."""
    if not sources:
        return

    with st.expander("查看参考原文"):
        for i, source in enumerate(sources):
            if isinstance(source, dict):
                title = source.get("title", "未知来源")
                content = source.get("content", "")
                score = source.get("score")
                
                # 构造展示标题
                header = f"**[{i+1}] {title}**"
                if score is not None:
                    header += f" (相关度: {score:.2f})"
                st.markdown(header)
                
                # 展示原文切片片段
                if content:
                    # 简单去除过多的连续换行并清理特殊的 Metadata 注入前缀显示
                    display_content = content.replace("---", "").strip()
                    st.info(display_content)
                st.divider()
            else:
                st.markdown(f"- {source}")


def main() -> None:
    """主Streamlit应用程序."""
    st.set_page_config(page_title="Trilium知识库智能体", page_icon="📚", layout="wide")

    st.title("🧠 Trilium 知识库智能助手")
    st.markdown("基于本地知识库的智能问答系统")

    # 初始化会话状态
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        # 显示当前使用的 API 地址，但不允许直接修改全局变量
        st.text_input("API 地址:", value=API_URL, disabled=True)
        api_key = st.text_input("API Key (如果启用):", type="password")

        st.header("📊 后端状态")
        status = get_backend_status(api_key)
        if status:
            st.success("连接正常 ✅")
            st.caption(f"Embedding: {status.get('embedding_model', '未知')}")
            errors = status.get('initialization_errors', {})
            if errors:
                for comp, err in errors.items():
                    st.error(f"{comp} 异常: {err}")
        else:
            st.error("连接失败 / 未授权 ❌")

        st.header("🗑️ 操作")
        if st.button("清除对话历史"):
            clear_backend_session(st.session_state.session_id, api_key)
            st.session_state.conversation = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

        st.markdown("---")
        st.markdown("### ℹ️ 关于")
        st.markdown(
            """
        这是一个基于 Trilium Notes 知识库的智能问答助手。
        
        **功能特点:**
        - 基于本地知识库回答问题
        - 保护您的隐私数据
        - 支持对话历史记录
        """
        )

    # 主聊天界面
    st.subheader("💬 对话")

    # 显示对话历史
    # 获取会话列表，明确类型以减少静态分析告警
    conversation_history: list[dict[str, Any]] = st.session_state.conversation

    for message in conversation_history:
        role = message.get("role")
        content = message.get("content", "")
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        elif role == "assistant":
            with st.chat_message("assistant"):
                st.markdown(content)
                # 如果有来源则显示
                sources = message.get("sources", [])
                if sources:
                    display_sources(sources)

    # 问题输入
    if prompt := st.chat_input("请输入您的问题..."):
        # 将用户消息添加到对话中
        st.session_state.conversation.append({"role": "user", "content": prompt})

        # 显示用户消息
        with st.chat_message("user"):
            st.markdown(prompt)

        # 从后端获取响应
        with st.chat_message("assistant"):
            with st.spinner("正在思考..."):
                response = send_question(prompt, st.session_state.session_id, api_key)

            if response:
                if response.get("error"):
                    err = response["error"]
                    st.error(f"⚠️ {err.get('message', '系统异常')} [{err.get('code')}]")
                    if err.get('details'):
                        st.caption(f"详细原因: {err['details']}")
                else:
                    answer = response.get("answer", "抱歉，我没有找到答案。")
                    st.markdown(answer)

                    # 添加来源（如果有）
                    sources = response.get("sources", [])
                    if sources:
                        display_sources(sources)

                    # 将助手响应添加到对话中
                    st.session_state.conversation.append({"role": "assistant", "content": answer, "sources": sources})


if __name__ == "__main__":
    main()
