# -*- coding: utf-8 -*-
"""长期记忆管理器单元测试."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock

from app.qa.memory import MemoryManager


 
@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def temp_memory_manager(tmp_path, mock_config):
    """创建临时记忆管理器，避免污染物理真实数据."""
    # 先初始化
    manager = MemoryManager(mock_config)
    # 物理路径篡改重定向到 tmp_path 临时目录
    manager.memory_file_path = tmp_path / "agent_memory.md"
    manager._init_memory_file()
    return manager


@pytest.mark.anyio
async def test_memory_init(temp_memory_manager):
    """测试长期记忆文件的初始化与默认模板."""
    assert temp_memory_manager.memory_file_path.exists()
    content = await temp_memory_manager.get_memory()
    assert "owner: guyue" in content
    assert "Agent Long-Term Memory" in content


@pytest.mark.anyio
async def test_memory_save_and_get(temp_memory_manager):
    """测试常规记忆的保存与读取."""
    new_content = "test memory content"
    success = await temp_memory_manager.save_memory(new_content)
    assert success is True
    
    content = await temp_memory_manager.get_memory()
    assert content == new_content


@pytest.mark.anyio
async def test_memory_truncation_protection(temp_memory_manager):
    """测试超长内容的写入与截断保护防线."""
    # 1. 尝试直接 save 超过 15000 字符的内容，应当被硬防护阻断
    overlong_content = "A" * 16000
    success = await temp_memory_manager.save_memory(overlong_content)
    assert success is False
    
    # 2. 模拟物理文件由于意外原因已经被填满超长内容
    temp_memory_manager.memory_file_path.write_text("B" * 13000, encoding="utf-8")
    content = await temp_memory_manager.get_memory()
    # 应该执行安全切断保护
    assert len(content) <= 12200
    assert "部分长期记忆由于过长已执行专家级截断保护" in content


@pytest.mark.anyio
async def test_memory_autonomous_update_and_debounce(temp_memory_manager):
    """测试异步大模型自主更新记忆及高并发防抖节流."""
    mock_llm = Mock()
    
    # 模拟大模型生成：模拟带延迟的缓慢调用，以便我们能抓住并发窗口
    def slow_generate(prompt):
        import time
        time.sleep(0.1)
        return "NO_CHANGE"
        
    mock_llm.generate = Mock(side_effect=slow_generate)
    
    # 1. 异步拉起第一次更新
    task1 = asyncio.create_task(
        temp_memory_manager.update_memory_autonomously(mock_llm, "你好", "您好！我是您的智能助理。")
    )
    
    # 2. 此时 _is_updating 状态必须立刻被设为 True
    await asyncio.sleep(0.01)  # 稍微让出 CPU 让 task1 执行到 lock 读取
    assert temp_memory_manager._is_updating is True
    
    # 3. 立即高并发拉起第二次更新，此时应当直接触发防抖，优雅跳过
    task2 = asyncio.create_task(
        temp_memory_manager.update_memory_autonomously(mock_llm, "操作系统是？", "是 macOS。")
    )
    
    await asyncio.gather(task1, task2)
    
    assert temp_memory_manager._is_updating is False
    # 证明：第二次高频连续调用没有被静默丢弃，而是压入 Pending Buffer 缓冲区，
    # 在第一轮结束后通过循环自动消费（不丢弃任何关键偏好），因此总计触发 2 次 generate。
    assert mock_llm.generate.call_count == 2


@pytest.mark.anyio
async def test_memory_exception_finally_safety(temp_memory_manager):
    """测试在大模型分析发生异常时，防死锁 finally 状态锁释放."""
    mock_llm = Mock()
    
    # 模拟大模型抛出连接超时等致命异常
    mock_llm.generate = Mock(side_effect=RuntimeError("LLM Timeout Connection Failed"))
    
    # 触发自主更新
    await temp_memory_manager.update_memory_autonomously(mock_llm, "测试异常", "测试")
    
    # 哪怕发生崩溃，finally 必须成功释放 _is_updating
    assert temp_memory_manager._is_updating is False
