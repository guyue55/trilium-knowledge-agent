# -*- coding: utf-8 -*-
"""测试前端显示逻辑."""

import streamlit as st

# 模拟从后端获取的响应
response = {
    "answer": "测试回答",
    "sources": [
        {
            "title": "测试文档1",
            "url": "http://192.168.1.202:3004/#root?noteId=test1",
            "content": "这是测试内容1..."
        },
        {
            "title": "测试文档2", 
            "url": "http://192.168.1.202:3004/#root?noteId=test2",
            "content": "这是测试内容2..."
        }
    ]
}

# 模拟前端显示
def display_sources(sources):
    """显示来源信息."""
    if sources:
        with st.expander("查看来源"):
            for source in sources:
                # 显示更友好的来源信息
                if isinstance(source, dict):
                    title = source.get("title", "未知标题")
                    url = source.get("url")
                    content = source.get("content", "")
                    if url:
                        st.markdown(f"**[{title}]({url})**")
                    else:
                        st.markdown(f"**{title}**")
                    
                    if content:
                        st.markdown(f"> {content}")
                else:
                    st.markdown(f"- {source}")

# 主界面
st.title("测试前端显示")

# 显示回答
st.markdown(response["answer"])

# 显示来源
display_sources(response["sources"])

# 模拟保存到会话状态并在后续显示
st.session_state.conversation = [{
    "role": "assistant",
    "content": response["answer"], 
    "sources": response["sources"]
}]

st.markdown("---")
st.markdown("## 从会话状态显示")

# 从会话状态显示来源
message = st.session_state.conversation[0]
if "sources" in message and message["sources"]:
    with st.expander("查看来源（从会话状态）"):
        for source in message["sources"]:
            # 显示更友好的来源信息
            if isinstance(source, dict):
                title = source.get("title", "未知标题")
                url = source.get("url")
                content = source.get("content", "")
                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")
                
                if content:
                    st.markdown(f"> {content}")
            else:
                st.markdown(f"- {source}")