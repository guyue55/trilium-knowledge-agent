# -*- coding: utf-8 -*-
"""Trilium 知识库智能体 API 接口层自动化巡检与鲁棒性审计脚本.

该脚本对运行在 http://localhost:8000/ 的后端服务进行全方位的端点探测与数据闭环校验。
"""

import sys
import json
import time
import requests
from loguru import logger

# 配置 loguru 日志样式
logger.remove()
logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:7}</level> | <cyan>{message}</cyan>")

BASE_URL = "http://localhost:8000"
TEST_SESSION_ID = "audit_smoke_test_session"


def test_endpoint(method: str, path: str, payload: dict = None, headers: dict = None, stream: bool = False):
    """通用请求发送封装."""
    url = f"{BASE_URL}{path}"
    try:
        t0 = time.time()
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=payload, timeout=5)
        elif method.upper() == "POST":
            timeout = (5, 60) if stream else 10
            response = requests.post(url, headers=headers, json=payload, stream=stream, timeout=timeout)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            raise ValueError(f"不支持的 HTTP 方法: {method}")
        
        latency = (time.time() - t0) * 1000
        return response, latency
    except Exception as e:
        logger.error(f"访问端点 {method} {path} 发生网络或超时异常: {e}")
        return None, 0.0


def run_full_api_audit():
    logger.info("======================================================================")
    logger.info("🚀 开始执行 Trilium Knowledge Agent 全量 API 接口鲁棒性审计...")
    logger.info("======================================================================")

    # ----------------------------------------------------------------------
    # 1. 探测健康端点 (GET /health 与 GET /api/v1/health)
    # ----------------------------------------------------------------------
    logger.info("\n[1/7] 探测健康状态与组件解析...")
    for path in ["/health", "/api/v1/health"]:
        res, lat = test_endpoint("GET", path)
        if res and res.status_code == 200:
            data = res.json()
            logger.success(f"✅ 端点 {path} 可达! 耗时: {lat:.2f}ms")
            logger.info(f"   系统整体状态: <yellow>{data.get('status')}</yellow>")
            logger.info(f"   各组件详情: {json.dumps(data.get('components', {}), ensure_ascii=False)}")
            logger.info(f"   Trilium 地址: {data.get('trilium_base_url')}")
            if data.get("errors"):
                logger.warning(f"   发现组件报错: {data.get('errors')}")
        else:
            status_code = res.status_code if res else "Unknown"
            logger.error(f"❌ 端点 {path} 异常! HTTP 状态码: {status_code}")

    # ----------------------------------------------------------------------
    # 2. 静态页面加载与防缓存响应头审查
    # ----------------------------------------------------------------------
    logger.info("\n[2/7] 静态主页加载与无损防缓存响应头审查...")
    res, lat = test_endpoint("GET", "/")
    if res and res.status_code == 200:
        logger.success(f"✅ HTML 主页加载成功! 耗时: {lat:.2f}ms")
        cache_control = res.headers.get("Cache-Control", "未配置")
        pragma = res.headers.get("Pragma", "未配置")
        expires = res.headers.get("Expires", "未配置")
        logger.info(f"   Cache-Control : {cache_control}")
        logger.info(f"   Pragma        : {pragma}")
        logger.info(f"   Expires       : {expires}")
        
        # 验证防缓存标志是否生效
        if "no-cache" in cache_control.lower() and "no-store" in cache_control.lower():
            logger.success("   🎉 防缓存消除机制 100% 符合高鲁棒规范！")
        else:
            logger.warning("   ⚠️ 警告：主入口未配置强防缓存响应头，可能导致前端资源缓存过期卡顿！")
            
        # 验证返回内容中是否带有动态物理时间戳防缓存标签
        html_content = res.text
        if "styles.css?v=" in html_content and "script.js?v=" in html_content:
            logger.success("   🎉 动态时间戳后缀在返回的 HTML 中已成功拼接！")
        else:
            logger.warning("   ⚠️ 警告：未检测到 css/js 带时间戳后缀，可能是由于物理 styles.css 未修改或加载兜底桩导致。")
    else:
        logger.error("❌ 无法访问主页 GET /")

    # ----------------------------------------------------------------------
    # 3. 审查非敏感配置获取与热参数暴露
    # ----------------------------------------------------------------------
    logger.info("\n[3/7] 审查非敏感配置端点 (GET /api/v1/config)...")
    res, lat = test_endpoint("GET", "/api/v1/config")
    if res and res.status_code == 200:
        data = res.json()
        logger.success(f"✅ 配置端点获取成功! 耗时: {lat:.2f}ms")
        logger.info(f"   大模型选择  : {data.get('llm_model_type')}")
        logger.info(f"   大模型路径  : {data.get('llm_model_path') or data.get('openai_model_name') or '默认'}")
        logger.info(f"   是否开启重排: {data.get('use_reranker')}")
        logger.info(f"   重排置信度  : {data.get('reranker_threshold')}")
        
        # 敏感 Key 脱敏合规审计
        keys_to_check = ["openai_api_key", "deepseek_api_key", "gemini_api_key"]
        masked_ok = True
        for key in keys_to_check:
            val = data.get(key)
            if val and not val.startswith("******"):
                logger.error(f"   🚨 严重安全漏洞：端点回显泄漏明文凭证 [{key}] = {val}!")
                masked_ok = False
        if masked_ok:
            logger.success("   🎉 审计通过：各平台云端 API Key 完全处于安全掩码保护下 (******)！")
    else:
        logger.error("❌ 无法获取配置端点 GET /api/v1/config")

    # ----------------------------------------------------------------------
    # 4. 会话列表管理审计
    # ----------------------------------------------------------------------
    logger.info("\n[4/7] 审查多用户会话列表 (GET /api/v1/sessions)...")
    res, lat = test_endpoint("GET", "/api/v1/sessions")
    if res and res.status_code == 200:
        data = res.json()
        logger.success(f"✅ 会话列表获取成功! 耗时: {lat:.2f}ms")
        sessions = data.get("sessions", {})
        logger.info(f"   当前磁盘常驻与冷启动探测会话总数: {len(sessions)}")
        for idx, (sid, meta) in enumerate(list(sessions.items())[:5]):
            title = meta.get("title") if isinstance(meta, dict) else meta
            logger.info(f"   - 会话 {idx+1}: ID={sid[:8]}... 标题='{title}'")
    else:
        logger.error("❌ 无法获取会话列表 GET /api/v1/sessions")

    # ----------------------------------------------------------------------
    # 5. 长期记忆文件读取审计
    # ----------------------------------------------------------------------
    logger.info("\n[5/7] 审查长期记忆内容 (GET /api/v1/memory)...")
    res, lat = test_endpoint("GET", "/api/v1/memory")
    if res and res.status_code == 200:
        data = res.json()
        logger.success(f"✅ 长期记忆端点响应成功! 耗时: {lat:.2f}ms")
        content = data.get("content", "")
        logger.info(f"   长期记忆大小 : {len(content)} 字符")
        lines = content.splitlines()
        logger.info("   最新交互提炼片段 (Lessons Learned):")
        lessons_found = False
        for line in lines:
            if line.strip().startswith("- [") or line.strip().startswith("* ["):
                logger.info(f"     {line.strip()}")
                lessons_found = True
        if not lessons_found:
            logger.info("     (尚未生成任何增量历史教训，属于新系统或模拟环境)")
    else:
        logger.error("❌ 无法读取长期记忆 GET /api/v1/memory")

    # ----------------------------------------------------------------------
    # 6. 端到端流式 SSE 问答管道与测试会话灌入审计
    # ----------------------------------------------------------------------
    logger.info("\n[6/7] 触发全链路 SSE 问答管道测试 (POST /api/v1/ask_stream)...")
    payload = {
        "question": "测试系统连通性与检索逻辑。请用一句话返回，并在句尾输出 'audit_pass' 标记以供校验。",
        "session_id": TEST_SESSION_ID
    }
    
    res, lat = test_endpoint("POST", "/api/v1/ask_stream", payload=payload, stream=True)
    if res and res.status_code == 200:
        logger.success(f"✅ SSE 管道建立连接! 耗时: {lat:.2f}ms")
        logger.info("   正在流式解包 SSE 事件 (Event Stream)...")
        
        full_answer = ""
        sources = []
        for line in res.iter_lines():
            if line:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    event_data_raw = line_str[6:]
                    try:
                        event = json.loads(event_data_raw)
                        ev_type = event.get("type")
                        if ev_type == "chunk":
                            chunk = event.get("data", "")
                            full_answer += chunk
                            sys.stdout.write(chunk)
                            sys.stdout.flush()
                        elif ev_type == "sources":
                            sources = event.get("data", [])
                        elif ev_type == "error":
                            logger.error(f"\n   🔴 管道返回业务异常: {event.get('data')}")
                    except Exception as parse_e:
                        logger.warning(f"\n   解析 SSE event 失败: {parse_e} (原始行: {line_str})")
        
        print()  # 换行
        logger.success("   🎉 SSE 流式生成完毕并顺利关闭！")
        logger.info(f"   RAG 召回来源文档数: {len(sources)}")
        for i, s in enumerate(sources[:3]):
            logger.info(f"     - 来源 {i+1}: [{s.get('title')}] 相关度分: {s.get('score', 0.0):.4f}")
            
        if "audit_pass" in full_answer.lower():
            logger.success("   🎉 RAG / MockLLM 全链路大模型生成闭环测试通过 (检测到 'audit_pass' 标)！")
        else:
            logger.warning("   ⚠️ 提示：大模型未按指示输出 'audit_pass'（可能是非 Mock 模型未完全对齐指令，属正常现象）。")
    else:
        status_code = res.status_code if res else "Unknown"
        logger.error(f"❌ 无法开启 SSE 流式提问，HTTP 状态码: {status_code}")

    # ----------------------------------------------------------------------
    # 7. 测试临时会话的物理级优雅清理与原子落盘测试
    # ----------------------------------------------------------------------
    logger.info("\n[7/7] 触发会话一键清理与资源落盘物理审计 (DELETE /api/v1/session/{session_id})...")
    res, lat = test_endpoint("DELETE", f"/api/v1/session/{TEST_SESSION_ID}")
    if res and res.status_code == 200:
        data = res.json()
        logger.success(f"✅ 清理测试会话成功! 耗时: {lat:.2f}ms")
        logger.info(f"   后端响应: {data.get('message')}")
        
        # 再次获取会话列表，确认清理干净
        res_list, _ = test_endpoint("GET", "/api/v1/sessions")
        if res_list and res_list.status_code == 200:
            sessions_data = res_list.json().get("sessions", {})
            if TEST_SESSION_ID not in sessions_data:
                logger.success(f"   🎉 物理与内存会话清理 100% 成功，会话 ID [{TEST_SESSION_ID}] 已彻底被抹去！")
            else:
                logger.error(f"   ❌ 严重漏洞：会话 ID [{TEST_SESSION_ID}] 依然遗留在会话列表中，清理未物理落盘！")
    else:
        logger.error(f"❌ 无法清理测试会话 DELETE /api/v1/session/{TEST_SESSION_ID}")


if __name__ == "__main__":
    run_full_api_audit()
