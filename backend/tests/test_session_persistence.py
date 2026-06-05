# -*- coding: utf-8 -*-
"""短期会话持久化、自适应 Token 压缩与检索缓存测试."""

import asyncio
import json
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from app.qa.memory import SessionManager, ChatMessage
from app.services.retrieval_service import RetrievalService
from app.retrieval.document import Document
from app.core.config import Config


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
def temp_session_manager(tmp_path):
    """创建临时 Session 存储，避免污染真实磁盘会话."""
    manager = SessionManager(max_history=3, max_session_chars=100)
    # 重定向 sessions_dir 路径到 tmp_path 临时目录
    manager.sessions_dir = tmp_path / "sessions"
    manager.sessions_dir.mkdir(parents=True, exist_ok=True)
    return manager


@pytest.mark.anyio
async def test_session_persistence_lifecycle(temp_session_manager):
    """测试会话消息的原子持久化、清空及物理载入还原 (Milestone 11)."""
    session_id = "test_session_1"
    
    # 1. 添加交互
    await temp_session_manager.add_interaction(session_id, "hello", "hi there")
    
    # 2. 检查内存
    history = await temp_session_manager.get_history(session_id)
    assert len(history) == 2
    assert history[0].content == "hello"
    assert history[1].content == "hi there"
    
    # 3. 验证物理 JSON 是否在磁盘生成
    file_path = temp_session_manager.sessions_dir / f"{session_id}.json"
    assert file_path.exists()
    
    disk_data = json.loads(file_path.read_text(encoding="utf-8"))
    assert disk_data["session_id"] == session_id
    assert len(disk_data["messages"]) == 2
    assert disk_data["messages"][0]["content"] == "hello"
    
    # 4. 强行抹去内存中的会话缓存，模拟服务重启/内存回收
    temp_session_manager.sessions.clear()
    temp_session_manager.summaries.clear()
    assert session_id not in temp_session_manager.sessions
    
    # 5. 重新获取，应该通过 _load_session_from_disk 自动在磁盘物理寻址自愈载入并完美还原
    loaded_history = await temp_session_manager.get_history(session_id)
    assert len(loaded_history) == 2
    assert loaded_history[0].role == "user"
    assert loaded_history[0].content == "hello"
    
    # 6. 测试会话清空，应该物理磁盘 JSON 同步被清除
    success = await temp_session_manager.clear_session(session_id)
    assert success is True
    assert not file_path.exists()
    assert session_id not in temp_session_manager.sessions


@pytest.mark.anyio
async def test_session_discovery_from_disk(temp_session_manager):
    """测试服务冷启动下，SessionManager 扫描磁盘 json 物理自愈并自动加载列表 (Milestone 11)."""
    # 1. 模拟物理磁盘上有 2 个存量会话（而在内存中尚未加载，模仿后端重启冷启动）
    session_id_1 = "legacy_session_A"
    session_id_2 = "legacy_session_B"
    
    # 分别写入数据
    data_a = {
        "session_id": session_id_1,
        "summary": "这是A的摘要",
        "messages": [{"role": "user", "content": "问题A"}, {"role": "assistant", "content": "回答A"}]
    }
    data_b = {
        "session_id": session_id_2,
        "summary": "这是B的摘要",
        "messages": [{"role": "user", "content": "问题B"}, {"role": "assistant", "content": "回答B"}]
    }
    
    file_path_a = temp_session_manager.sessions_dir / f"{session_id_1}.json"
    file_path_b = temp_session_manager.sessions_dir / f"{session_id_2}.json"
    
    file_path_a.write_text(json.dumps(data_a, ensure_ascii=False), encoding="utf-8")
    # 稍微延迟，以便 st_mtime 有明显时差排序
    await asyncio.sleep(0.01)
    file_path_b.write_text(json.dumps(data_b, ensure_ascii=False), encoding="utf-8")
    
    # 内存依然保持空
    assert not temp_session_manager.sessions
    
    # 2. 调用 get_all_sessions，应当启动冷启动文件寻址扫描
    all_sessions = await temp_session_manager.get_all_sessions()
    
    # 3. 验证扫描和自愈是否成功
    assert session_id_1 in all_sessions
    assert session_id_2 in all_sessions
    assert all_sessions[session_id_1] == "问题A"
    assert all_sessions[session_id_2] == "问题B"
    
    # 并且验证它已经自动反序列化到内存了
    assert session_id_1 in temp_session_manager.sessions
    assert temp_session_manager.summaries[session_id_1] == "这是A的摘要"


@pytest.mark.anyio
async def test_session_token_adaptive_summary(temp_session_manager):
    """测试自适应会话滑动与后台大纲总结压缩机制 (Milestone 12)."""
    session_id = "test_summary_session"
    
    # 1. 模拟大模型总结生成器
    mock_llm = Mock()
    mock_llm.generate = Mock(return_value="这是提炼压缩后的会话背景：用户是一个 macOS 平台开发者。")
    
    # 2. 我们将字符触发阈值改为 50，以极其轻松地触发总结
    temp_session_manager.max_session_chars = 50
    
    # 先添加几条交互，累积字数很长
    await temp_session_manager.add_interaction(session_id, "我使用的是 macOS 操作系统", "收到，已记录您的系统。")
    await temp_session_manager.add_interaction(session_id, "我最喜欢 Glassmorphism 毛玻璃的前端美学", "毛玻璃磨砂质感确实非常高智感。")
    await temp_session_manager.add_interaction(session_id, "今天天气真好", "是的，非常晴朗。", mock_llm)
    
    # 等待异步 create_task 任务稍微执行
    await asyncio.sleep(0.1)
    
    # 3. 验证老消息是否已被自适应裁剪并总结
    # 我们只保留最近的 4 条消息（即 2 轮），前面的第 1 轮应该已经被压缩
    history = await temp_session_manager.get_history(session_id)
    assert len(history) == 4
    
    # 第 1 轮消息应当已被截断消失
    assert history[0].content != "我使用的是 macOS 操作系统"
    
    # 4. 验证摘要内容是否正确被写入 summaries 并原子存入磁盘 JSON
    summary = await temp_session_manager.get_summary(session_id)
    assert "macOS" in summary
    
    file_path = temp_session_manager.sessions_dir / f"{session_id}.json"
    disk_data = json.loads(file_path.read_text(encoding="utf-8"))
    assert disk_data["summary"] == "这是提炼压缩后的会话背景：用户是一个 macOS 平台开发者。"


@pytest.mark.anyio
async def test_reranker_hot_cache_barrier(mock_config):
    """测试 Reranker 检索热缓存屏障，避免高频追问/相似提问打盘和重复推理 (Milestone 13)."""
    # 1. 模拟 VectorStore 和 Reranker
    mock_vector_store = Mock()
    mock_reranker = Mock()
    
    # 模拟第一次混合检索有数据返回
    doc_a = Document(page_content="MySQL 缓冲池参数", metadata={"title": "MySQL"})
    doc_b = Document(page_content="InnoDB 核心机制", metadata={"title": "InnoDB"})
    mock_vector_store.similarity_search_with_scores = Mock(return_value=[(doc_a, 0.9), (doc_b, 0.8)])
    mock_reranker.rerank_and_filter = Mock(return_value=[doc_a, doc_b])
    
    service = RetrievalService(mock_config, mock_vector_store, mock_reranker)
    
    # 2. 第一次发起混合检索
    query = "MySQL核心缓冲池"
    filtered_1, raw_1 = await service.retrieve_and_rerank(query)
    
    assert len(filtered_1) == 2
    assert mock_vector_store.similarity_search_with_scores.call_count == 1
    assert mock_reranker.rerank_and_filter.call_count == 1
    
    # 3. 连续第二次发起完全相同的混合检索（模拟追问）
    filtered_2, raw_2 = await service.retrieve_and_rerank(query)
    
    # call_count 应当依然是 1，证明第二次混合检索直接命中热缓存屏障，
    # 0 次重复调用 LanceDB 与 Cross-Encoder，极速返回，高可用提吞吐！
    assert len(filtered_2) == 2
    assert mock_vector_store.similarity_search_with_scores.call_count == 1
    assert mock_reranker.rerank_and_filter.call_count == 1
