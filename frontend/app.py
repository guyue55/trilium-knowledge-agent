# -*- coding: utf-8 -*-
"""
Trilium知识库智能体的Streamlit前端.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

# 从环境变量获取API URL或使用默认值
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")


def send_question(question: str) -> dict[str, Any] | None:
    """向后端API发送问题.

    Args:
        question: 要发送的问题.

    Returns:
        API的响应或None（如果请求失败）.
    """
    try:
        response = requests.post(
            f"{API_URL}/ask",
            json={"question": question},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"连接后端时出错: {e}")
        if e.response is not None:
            st.error(f"详细错误信息: {e.response.text}")
        return None


def display_sources(sources: list[Any]) -> None:
    """显示来源信息."""
    if not sources:
        return

    with st.expander("查看来源"):
        for source in sources:
            # 显示更友好的来源信息
            if isinstance(source, dict):
                title = source.get("title", "未知标题")
                url = source.get("url")
                # 不再显示内容详情，只显示标题和链接
                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")
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

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        # 显示当前使用的 API 地址，但不允许直接修改全局变量
        st.text_input("API 地址:", value=API_URL, disabled=True)

        st.header("🗑️ 操作")
        if st.button("清除对话历史"):
            st.session_state.conversation = []
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
                response = send_question(prompt)

            if response:
                answer = response.get("answer", "抱歉，我没有找到答案。")
                st.markdown(answer)

                # 添加来源（如果有）
                sources = response.get("sources", [])
                if sources:
                    display_sources(sources)

                # 将助手响应添加到对话中
                st.session_state.conversation.append({"role": "assistant", "content": answer, "sources": sources})
            else:
                st.error("无法获取回答，请检查后端服务是否正常运行。")


if __name__ == "__main__":
    main()
