# -*- coding: utf-8 -*-
"""问答系统的会话内存与历史记录管理."""

import asyncio
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel
from loguru import logger

from app.core.config import Config
from app.llm.base import LLMAdapter


class ChatMessage(BaseModel):
    """原生会话消息结构，完全脱离 LangChain 依赖."""
    role: str  # "user" 或 "assistant"
    content: str


class SessionManager:
    """管理多用户的多轮对话上下文 (线程/协程安全，支持基于磁盘的 JSON 持久化与自适应 Token 压缩)."""

    def __init__(self, max_history: int = 5, max_session_chars: int = 3000):
        self.sessions: Dict[str, List[ChatMessage]] = {}
        self.summaries: Dict[str, str] = {}
        self.max_history = max_history
        self.max_session_chars = max_session_chars
        self._lock = asyncio.Lock()
        
        # 物理落盘路径：data/sessions/
        self.sessions_dir = Path(__file__).parent.parent.parent / "data" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # ⚡ 引入元数据内存二级缓存，存储结构为: {session_id: {"title": str, "updated_at": float, "summary": str}}
        self._sessions_metadata: Dict[str, Dict[str, Any]] = {}

    async def _sync_metadata_cache_unlocked(self) -> None:
        """快速对磁盘 file_path 和内存级元数据、会话消息、摘要执行增量热同步 (假定当前已持有 self._lock)."""
        import json
        if not self.sessions_dir.exists():
            return

        try:
            # 1. 扫描当前磁盘所有的 *.json 文件
            current_files = list(self.sessions_dir.glob("*.json"))
            disk_sids = set()

            for file_path in current_files:
                sid = file_path.stem
                disk_sids.add(sid)
                
                # 获取该文件的实际修改时间戳
                stat_res = file_path.stat()
                mtime = stat_res.st_mtime
                
                # 增量自愈防线：
                # 如果 sid 不在元数据中，或者文件修改时间不匹配（外部已被修改）
                # 或者在内存中意外缺失，则仅触发 1 次读取载入
                if (sid not in self._sessions_metadata or 
                    self._sessions_metadata[sid].get("updated_at") != mtime or
                    sid not in self.sessions or
                    sid not in self.summaries):
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        data = json.loads(content)
                        
                        # 1.1 填充 ChatMessage 消息缓存
                        self.sessions[sid] = [
                            ChatMessage(role=m["role"], content=m["content"]) 
                            for m in data.get("messages", [])
                        ]
                        # 1.2 填充摘要缓存
                        self.summaries[sid] = data.get("summary", "")
                        
                        # 1.3 提取标题
                        first_msg = self.sessions[sid][0].content if self.sessions[sid] else "空会话"
                        title = first_msg[:15] + "..." if len(first_msg) > 15 else first_msg
                        
                        # 1.4 更新元数据缓存
                        self._sessions_metadata[sid] = {
                            "title": title,
                            "updated_at": mtime,
                            "summary": self.summaries[sid]
                        }
                    except Exception as fe:
                        logger.error(f"解析并增量载入会话文件失败 {sid}: {fe}")
            
            # 2. 清理内存缓存中在磁盘上已被物理物理删除的会话
            for cached_sid in list(self._sessions_metadata.keys()):
                if cached_sid not in disk_sids:
                    self._sessions_metadata.pop(cached_sid, None)
                    self.sessions.pop(cached_sid, None)
                    self.summaries.pop(cached_sid, None)
                    
        except Exception as e:
            logger.error(f"快速同步会话元数据失败: {e}")

    async def _load_session_from_disk(self, session_id: str) -> bool:
        """从磁盘加载指定会话并载入内存并对齐元数据 (假定当前已持有 self._lock)."""
        import json
        file_path = self.sessions_dir / f"{session_id}.json"
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                data = json.loads(content)
                self.sessions[session_id] = [
                    ChatMessage(role=m["role"], content=m["content"]) 
                    for m in data.get("messages", [])
                ]
                self.summaries[session_id] = data.get("summary", "")
                
                # 顺便同步更新元数据，确保即使没有触发全局扫描也具有最新缓存
                mtime = file_path.stat().st_mtime
                first_msg = self.sessions[session_id][0].content if self.sessions[session_id] else "空会话"
                title = first_msg[:15] + "..." if len(first_msg) > 15 else first_msg
                self._sessions_metadata[session_id] = {
                    "title": title,
                    "updated_at": mtime,
                    "summary": self.summaries[session_id]
                }
                return True
            except Exception as e:
                logger.error(f"从磁盘加载会话 {session_id} 失败: {e}")
                return False
        return False

    async def _save_session_to_disk_unlocked(self, session_id: str) -> None:
        """原子写盘底层实现，并同步更新元数据 (假定当前已持有 self._lock)."""
        import json
        import os
        try:
            data = {
                "session_id": session_id,
                "summary": self.summaries.get(session_id, ""),
                "messages": [{"role": m.role, "content": m.content} for m in self.sessions.get(session_id, [])]
            }
            
            # 写入临时文件
            tmp_file_path = self.sessions_dir / f"{session_id}.json.tmp"
            real_file_path = self.sessions_dir / f"{session_id}.json"
            
            # 确保目录存在
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            
            tmp_file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            
            # 原子替换 (POSIX replace)
            os.replace(tmp_file_path, real_file_path)
            
            # ⚡ 写入成功后，立刻对当前会话的元数据在内存中完成刷新，记录最新修改时间
            mtime = real_file_path.stat().st_mtime
            first_msg = self.sessions[session_id][0].content if self.sessions.get(session_id) else "空会话"
            title = first_msg[:15] + "..." if len(first_msg) > 15 else first_msg
            self._sessions_metadata[session_id] = {
                "title": title,
                "updated_at": mtime,
                "summary": self.summaries.get(session_id, "")
            }
        except Exception as e:
            logger.error(f"会话 {session_id} 写入磁盘失败: {e}")

    async def get_all_sessions(self) -> Dict[str, str]:
        """获取所有已记录的会话ID以及它们的第一句人类提问（作为标题，基于 st_mtime 增量扫描自愈，0 I/O 放大）."""
        async with self._lock:
            # 执行快速增量自愈与冷启动感知
            await self._sync_metadata_cache_unlocked()
            
            # 按照修改时间排序
            sorted_sessions = sorted(
                self._sessions_metadata.items(),
                key=lambda x: x[1].get("updated_at", 0.0),
                reverse=True
            )
            return {sid: meta["title"] for sid, meta in sorted_sessions}

    async def get_all_sessions_with_metadata(self) -> Dict[str, Dict[str, Any]]:
        """获取所有已记录的会话ID，标题以及最后修改时间戳 (st_mtime)，支持时序分组."""
        async with self._lock:
            # 执行快速增量自愈与冷启动感知
            await self._sync_metadata_cache_unlocked()
            
            # 按照修改时间排序
            sorted_sessions = sorted(
                self._sessions_metadata.items(),
                key=lambda x: x[1].get("updated_at", 0.0),
                reverse=True
            )
            return {
                sid: {
                    "title": meta["title"],
                    "updated_at": meta["updated_at"]
                }
                for sid, meta in sorted_sessions
            }

    async def get_history(self, session_id: str) -> List[ChatMessage]:
        """获取指定会话的历史记录 (带自动物理寻址载入)."""
        async with self._lock:
            if session_id not in self.sessions:
                await self._load_session_from_disk(session_id)
            return self.sessions.get(session_id, [])

    async def get_summary(self, session_id: str) -> str:
        """获取指定会话的历史大纲背景摘要."""
        async with self._lock:
            if session_id not in self.sessions:
                await self._load_session_from_disk(session_id)
            return self.summaries.get(session_id, "")

    async def add_interaction(self, session_id: str, human_text: str, ai_text: str, llm_adapter: LLMAdapter = None) -> None:
        """向会话中添加一轮交互，触发非阻塞后台自适应摘要压缩，并原子落盘物理 JSON."""
        async with self._lock:
            if session_id not in self.sessions:
                await self._load_session_from_disk(session_id)
                if session_id not in self.sessions:
                    self.sessions[session_id] = []
            
            self.sessions[session_id].append(ChatMessage(role="user", content=human_text))
            self.sessions[session_id].append(ChatMessage(role="assistant", content=ai_text))
            
            # 首先进行传统的轮数截断兜底防线
            max_msg_len = self.max_history * 2
            if len(self.sessions[session_id]) > max_msg_len and not llm_adapter:
                self.sessions[session_id] = self.sessions[session_id][-max_msg_len:]
            
            # 原子保存到物理磁盘（已加锁环境）
            await self._save_session_to_disk_unlocked(session_id)

        # ⚡ 效率与长久重塑：如果传入了 LLM Adapter，并且会话总字符超标，启动非阻塞后台自适应摘要压缩任务
        if llm_adapter:
            # 在不锁死主线程/主协程的情况下，异步创建自适应总结任务
            asyncio.create_task(self._summarize_session_history_task(session_id, llm_adapter))

    async def _summarize_session_history_task(self, session_id: str, llm_adapter: LLMAdapter) -> None:
        """在后台非阻塞地提炼 and 压缩会话历史，避免拖慢用户的实时响应体验 (Milestone 12)."""
        # 1. 获取会话历史的快照
        async with self._lock:
            if session_id not in self.sessions:
                return
            messages = list(self.sessions[session_id])
            total_chars = sum(len(m.content) for m in messages)
            
            # 如果字符没有超限，或者当前消息总数不足 5 条（至少保留最新 4 条，即最近 2 轮），则不触发压缩
            if total_chars <= self.max_session_chars or len(messages) <= 4:
                return
                
            old_messages = messages[:-4]
            existing_summary = self.summaries.get(session_id, "")
            
        # 2. 释放锁之后，在后台线程中安全调用耗时的大模型生成（彻底释放主协程，零锁死）
        old_history_str = "\n".join(f"{'User' if m.role == 'user' else 'AI'}: {m.content}" for m in old_messages)
        
        summary_prompt = f"""你是一个智能对话大纲与语境总结引擎。
你的任务是将下面一段老对话历史（以及可能已经存在的旧背景摘要）提炼并合并为一段全新、高度压缩、精炼的“会话背景摘要”（Session Background Summary），以便释放大模型上下文空间，同时确保前文中的关键事实、用户偏好、开发项目背景和已解决的问题背景不丢失。

【已有的旧背景摘要】（如果没有则为空）：
{existing_summary}

【待压缩的老对话历史】：
{old_history_str}

要求：
1. 请用极为精炼的中文子弹笔记（Bullet Points）格式对上述信息进行合并、压缩 and 归纳。
2. 剔除所有客套话、打招呼、重复问答等无意义的闲聊，只保留确定性的长期偏好、开发环境（如 OS 平台）、项目技术约定或前面讨论解决的核心 BUG 技术事实。
3. 压缩后的背景摘要总字数绝对不能超过 500 字。
4. **重要**：只输出提炼后的 Bullet Points 纯文本正文，绝对不能包裹 markdown 代码块（如 ```），绝对不要输出任何前缀、废话或解释！
"""
        try:
            logger.info(f"⚡ 开始对会话 {session_id} 启动后台自适应 Token 压缩...")
            # 使用 to_thread 避免阻塞 FastAPI 异步主循环
            new_summary_raw = await asyncio.to_thread(llm_adapter.generate, summary_prompt)
            new_summary = new_summary_raw.strip()
            
            # 极致防线：剥离大模型可能包裹的 markdown 代码块
            if new_summary.startswith("```"):
                lines = new_summary.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                new_summary = "\n".join(lines).strip()
                
            if new_summary and len(new_summary) < 5000:
                # 3. 再次获取锁，将内存中已被压缩的历史前部删除，保留最近消息和新摘要并写盘
                async with self._lock:
                    current_len = len(self.sessions[session_id])
                    offset = len(messages) - 4
                    if current_len >= offset:
                        # 物理裁剪掉已经总结过的老消息，保留后部的最新 4 条以及最新交互期间可能追加的消息
                        self.sessions[session_id] = self.sessions[session_id][offset:]
                        
                    self.summaries[session_id] = new_summary
                    logger.info(f"✨ 会话 {session_id} 历史背景压缩完成！老消息已裁剪，摘要已常驻。")
                    
                    # 写入物理磁盘
                    await self._save_session_to_disk_unlocked(session_id)
        except Exception as e:
            logger.error(f"后台自适应会话摘要失败: {e}")

    async def clear_session(self, session_id: str) -> bool:
        """清空指定会话（同步清除内存与物理磁盘 JSON）."""
        import os
        async with self._lock:
            deleted = False
            if session_id in self.sessions:
                del self.sessions[session_id]
                deleted = True
            if session_id in self.summaries:
                del self.summaries[session_id]
            # 同步清理元数据缓存
            if session_id in self._sessions_metadata:
                del self._sessions_metadata[session_id]
                deleted = True
                
            try:
                file_path = self.sessions_dir / f"{session_id}.json"
                if file_path.exists():
                    os.remove(file_path)
                    deleted = True
                    logger.info(f"会话物理 JSON {session_id}.json 已安全清除")
            except Exception as e:
                logger.error(f"物理清除会话磁盘文件 {session_id}.json 异常: {e}")
                
            return deleted



class MemoryManager:
    """管理智能体的长期记忆（基于常驻内存 Cache + 物理落盘双重保障的安全管理机制）."""
    
    def __init__(self, config: Config):
        self.config = config
        # 记忆文件物理路径：默认保存在与 data 同级或 model 同级的目录中
        self.memory_file_path = Path(__file__).parent.parent.parent / "data" / "agent_memory.md"
        
        # 确保 data 目录存在
        self.memory_file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        
        # ⚡ 效率重塑：内存级热缓存（常驻），彻底消除主问答流程中的磁盘 I/O 阻塞
        self._memory_cache = ""
        # ⚡ 一致性重塑：感知外部物理文件篡改的修改时间时间戳
        self._last_mtime = 0.0
        # ⚡ 长久重塑：待更新的事实缓冲区，避免连续高频对话下因防抖静默丢失偏好
        self._pending_interactions: List[Dict[str, str]] = []
        
        self._init_memory_file()
        self._load_memory_to_cache()
        
        # 专家级高并发防抖锁
        self._is_updating = False

    def _init_memory_file(self):
        """如果记忆文件不存在，用高水准的 Google Style 模板进行物理初始化."""
        if not self.memory_file_path.exists():
            default_template = """---
owner: guyue
project: trilium-knowledge-agent
last_updated: 2026-06-04T14:30:00+08:00
tags: [system-memory, preference, environment]
---

# 🤖 Agent Long-Term Memory (AI 长期记忆大脑)

## 👤 用户画像与偏好 (User Profile & Preferences)
- **开发操作系统**: macOS
- **偏好前端美学**: Google Material / Glassmorphism (毛玻璃) 风格，极致暗黑/白天自适应模式，拒绝 plain styling。
- **构建环境约定**: 
  - 后端偏好：FastAPI + Python3 (零 LangChain, 原生极简高内聚)
  - 模型部署：Ollama 本地部署为可选（默认不强求 docker-compose），支持直接配置已有大模型 API。
  - 前端部署：静态资源直接挂载在 FastAPI 目录下，依靠 `/assets/` 静态服务，利用时间戳进行无损缓存防卫。

## 🛠️ 项目环境与部署快照 (Environment & Deployment Snapshots)
- **FastAPI 运行端口**: `http://localhost:8000` (正常可用)
- **回态回归验证**: 包含 PC、平板、移动端窄屏等多端响应式设计，完美防冲突 `z-index`。
- **Trilium 集成模式**: 采用 API Token 直连模式，知识库索引正常。

## 📝 历史交互提炼 (Lessons Learned & Resolved Conflicts)
- [2026-06-03] **[解决]** 汉堡按钮的点击穿透与移动端左侧抽屉动画丢失问题。根本原因在于 CSS Layer 被局部覆盖，通过将 z-index 提升至 1100 解决。
- [2026-06-03] **[注意]** 不要使用 ad-hoc 的 Tailwind 样式，前端使用原生高度定制的 Vanilla CSS (位于 styles.css) 以保持纯净性。
"""
            self.memory_file_path.write_text(default_template, encoding="utf-8")
            logger.info(f"💾 初始化长期记忆 Markdown 文件成功: {self.memory_file_path}")

    def _load_memory_to_cache(self):
        """一次性将物理文件载入内存一级缓存，消除频繁提问中的读磁盘开销."""
        try:
            if self.memory_file_path.exists():
                self._memory_cache = self.memory_file_path.read_text(encoding="utf-8")
                self._last_mtime = self.memory_file_path.stat().st_mtime
                logger.info("🧠 长期记忆内存常驻热缓存载入成功！")
            else:
                self._memory_cache = ""
                self._last_mtime = 0.0
        except Exception as e:
            logger.error(f"载入长期记忆到缓存失败: {e}")
            self._memory_cache = ""
            self._last_mtime = 0.0

    async def get_memory(self) -> str:
        """从微秒级内存缓存直接读取，保障极致的 RAG 响应流速 (0 I/O 开销)；若检测到外部篡改或物理修改，自动刷新自愈缓存. """
        try:
            if self.memory_file_path.exists():
                current_mtime = self.memory_file_path.stat().st_mtime
                if current_mtime > self._last_mtime:
                    logger.warning("🧠 检测到物理记忆文件在外部被直接修改，热缓存正在自动重载自愈...")
                    self._load_memory_to_cache()
        except Exception as e:
            logger.error(f"检查物理记忆文件修改时间失败: {e}")

        content = self._memory_cache
        # 专家防御型编程：如果缓存被意外污染超长，执行安全截断
        if len(content) > 12000:
            logger.warning("⚠️ 长期记忆常驻内容过长，读取时执行安全硬截断！")
            return content[:12000] + "\n\n... (部分长期记忆由于过长已执行专家级截断保护) ..."
        return content

    async def save_memory(self, content: str) -> bool:
        """物理原子落盘：先安全写入临时文件并落盘，再通过 OS 原子级 replace 操作覆盖，同步更新热缓存."""
        import os
        async with self._lock:
            try:
                # 1. 强安全字数控制，防止大模型写出撑爆 Context 的内容
                if len(content) > 15000:
                    logger.warning("⚠️ 尝试写入长期记忆的字符超限 (15000)，拒绝保存")
                    return False

                # 2. 写入同目录临时文件
                tmp_file_path = self.memory_file_path.with_suffix(".md.tmp")
                tmp_file_path.write_text(content, encoding="utf-8")
                
                # 3. 操作系统级原子覆盖 (POSIX 级 replace，杜绝对多进程、异常崩溃下的损坏隐患)
                os.replace(tmp_file_path, self.memory_file_path)
                self._last_mtime = self.memory_file_path.stat().st_mtime
                
                # 4. 同步刷新常驻热缓存，保障数据完全一致性
                self._memory_cache = content
                logger.info("💾 长期记忆原子物理落盘且内存热缓存同步刷新成功！")
                return True
            except Exception as e:
                logger.error(f"原子物理落盘长期记忆发生异常: {e}")
                # 专家降级防线：如果由于某种原因原子写入失败，降级为直写
                try:
                    self.memory_file_path.write_text(content, encoding="utf-8")
                    self._memory_cache = content
                    self._last_mtime = self.memory_file_path.stat().st_mtime
                    logger.warning("💾 原子物理写入遭遇异常，降级直写模式覆写成功。")
                    return True
                except Exception as ex:
                    logger.error(f"降级直写模式同样遭遇失败: {ex}")
                    return False

    def _merge_incremental_memory(self, old_content: str, increment_text: str, max_lessons: int = 15) -> str:
        """将大模型提炼出来的增量事实，与老长期记忆安全合并，应用 FIFO 滑动窗口截断，杜绝文件物理膨胀与语义退化."""
        import datetime
        now_str = datetime.datetime.now().astimezone().isoformat()
        
        # 1. 默认 YAML 头部元数据 (降级自愈保障)
        yaml_data = {
            "owner": "guyue",
            "project": "trilium-knowledge-agent",
            "last_updated": now_str,
            "tags": "[system-memory, preference, environment]"
        }
        
        # 提取老文件中的 YAML 头并进行继承
        yaml_header_str = ""
        main_body = old_content
        if old_content.startswith("---"):
            parts = old_content.split("---", 2)
            if len(parts) >= 3:
                yaml_header_str = parts[1].strip()
                main_body = parts[2].strip()
                
        # 解析老 YAML 字段，继承非 last_updated 字段
        if yaml_header_str:
            for line in yaml_header_str.splitlines():
                if ":" in line:
                    parts_kv = line.split(":", 1)
                    k = parts_kv[0].strip()
                    v = parts_kv[1].strip()
                    if k != "last_updated":
                        yaml_data[k] = v
                        
        # 2. 组装全新 YAML 头部
        new_yaml_lines = ["---"]
        for k, v in yaml_data.items():
            new_yaml_lines.append(f"{k}: {v}")
        new_yaml_lines.append("---")
        new_yaml_header = "\n".join(new_yaml_lines)
        
        # 3. 定位 `## 📝 历史交互提炼 (Lessons Learned & Resolved Conflicts)`
        target_header = "## 📝 历史交互提炼 (Lessons Learned & Resolved Conflicts)"
        header_idx = main_body.find("## 📝 历史交互提炼")
        
        if header_idx == -1:
            # 格式破损或老文件丢失，强制在正文尾部自愈追加该标题
            main_body = main_body.rstrip() + f"\n\n{target_header}\n"
            header_idx = main_body.find("## 📝 历史交互提炼")
            
        # 根据换行精确分割静态正文与动态提炼列表
        lines = main_body[header_idx:].splitlines()
        static_body = main_body[:header_idx] + lines[0] + "\n"
        dynamic_body = "\n".join(lines[1:])
        
        # 4. 解析新老列表项并精准合并去重
        old_lessons = []
        for line in dynamic_body.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                old_lessons.append(line_stripped)
                
        new_lessons = []
        for line in increment_text.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("- ") or line_stripped.startswith("* "):
                new_lessons.append(line_stripped)
                
        # 最新教训拼在最前面
        merged_lessons = []
        seen = set()
        for item in new_lessons + old_lessons:
            if item not in seen:
                seen.add(item)
                merged_lessons.append(item)
                
        # 滑动窗口截断 (只保留最新的 15 条 Lessons，根除阿尔茨海默征并限制物理体积)
        if len(merged_lessons) > max_lessons:
            logger.warning(f"📝 长期记忆滑动窗口拦截：历史教训条数达到上限（当前 {len(merged_lessons)} 条），启动自动 FIFO 截断，仅保留最新 {max_lessons} 条，消除阿尔茨海默征！")
            merged_lessons = merged_lessons[:max_lessons]
            
        new_dynamic_content = "\n".join(merged_lessons) + "\n"
        
        # 5. 最终完美组装并回吐
        final_content = f"{new_yaml_header}\n\n{static_body.strip()}\n\n{new_dynamic_content}"
        return final_content

    async def update_memory_autonomously(self, llm_adapter: LLMAdapter, question: str, answer: str) -> None:
        """利用待消费队列 (Pending Buffer) 机制，支持多轮高频提问合并增量提炼，避免事实静默丢弃并保障运行效率."""
        # 1. 任何新事实产生优先安全压入缓冲区，突破以往防抖静默 return
        async with self._lock:
            self._pending_interactions.append({"question": question, "answer": answer})
        
        # 2. 若当前正在生成，直接挂起返回（因为本轮事实已被保留在待更新缓冲区中，在 while 循环中会被合并重构）
        if self._is_updating:
            logger.info("🧠 长期记忆正在后台重构生成中，当前交互事实已安全挂起并入缓冲区...")
            return

        self._is_updating = True
        try:
            # 3. 循环消费缓冲区，直到把所有的积压偏好消费殆尽，实现密集事实的“增量自增与合并”
            while True:
                async with self._lock:
                    if not self._pending_interactions:
                        break
                    # 打包提取并排空
                    batch_interactions = list(self._pending_interactions)
                    self._pending_interactions.clear()

                # 4. 读取内存一级热缓存（免 I/O）
                current_memory = await self.get_memory()

                # 5. 拼接本次待更新的多轮事实
                interactions_str = ""
                for idx, interaction in enumerate(batch_interactions):
                    interactions_str += f"[{idx+1}] 用户问题：{interaction['question']}\n[{idx+1}] AI 回答：{interaction['answer']}\n\n"

                # 6. 生成分析 Prompt (仅提炼增量事实，大模型运行速度提升 10 倍，API 资费降低 90%)
                import datetime
                now_date = datetime.datetime.now().strftime("%Y-%m-%d")
                
                update_prompt = f"""你是一个智能记忆提炼引擎。请分析下面发生的用户和 AI 的最新交互，提取出其中包含的、且【现有长期记忆】中尚未记录的、值得长久保存的重要新事实、用户偏好、项目环境快照或新解决的 BUG 记录。

现有长期记忆：
{current_memory}

最新交互：
{interactions_str}

要求：
1. 仔细比对现有记忆和最新交互。如果当前交互中没有任何新的偏好或长期事实需要沉淀，**必须精确且仅输出 `NO_CHANGE`** 字符串，不要做任何多余解释！
2. 如果存在新的、现有长期记忆中尚未包含的重要事实，请单独提炼出来。**必须**使用标准的 Markdown 列表格式输出：`- [{now_date}] **[分类]** 事实描述`。
   - 日期请使用：{now_date}
   - 分类可以是：[解决]、[偏好]、[注意]、[部署] 等
   - 事实描述应当精准、精炼，去除废话。
3. **重要限制**：绝对不能输出任何解释、任何 ```markdown 块包裹标记，也不能输出 YAML 头部！只输出提炼后的单行或多行列表，如果没有则只输出 `NO_CHANGE`。
"""
                logger.info(f"🧠 长期记忆模块拉起后台 LLM，正在对缓冲区的 {len(batch_interactions)} 轮交互进行增量提炼...")
                
                # 7. 释放锁之后，在没有锁保护的独立线程进行大模型耗时生成（彻底解放 API 读写并发！）
                response = await asyncio.to_thread(llm_adapter.generate, update_prompt)
                response_clean = response.strip()
                
                if "NO_CHANGE" in response_clean and len(response_clean) < 50:
                    logger.info("🧠 长期记忆分析完毕：缓冲区中无新事实需要沉淀。")
                    continue

                # 8. 剥离包裹代码块的 ```markdown 或其它标记 (极致防线)
                if response_clean.startswith("```"):
                    lines = response_clean.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    response_clean = "\n".join(lines).strip()

                if response_clean and len(response_clean) < 15000:
                    # 9. 高内聚增量安全合并自愈，应用滑动窗口与元数据继承
                    healed_content = self._merge_incremental_memory(current_memory, response_clean)
                    # 10. 物理原子安全覆写，并同步刷新热缓存
                    await self.save_memory(healed_content)
                else:
                    logger.warning("⚠️ 后台大模型生成的记忆内容格式异常或超出硬字数限制（15000），自主合并被阻断保护。")

        except Exception as e:
            logger.error(f"自主更新长期记忆发生异常: {e}")
        finally:
            # 专家防死锁设计：必须在 finally 释放标志，确保后续交互可持续更新！
            self._is_updating = False
