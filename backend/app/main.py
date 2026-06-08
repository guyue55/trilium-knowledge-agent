# -*- coding: utf-8 -*-
"""Trilium 知识库智能体主应用入口 (零 LangChain, 高内聚, 智能退化版)."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response
from loguru import logger

from app.api.endpoints import router as api_router
from app.core.config import get_config
from app.core.container import container
from app.core.security import mask_sensitive_data
from app.llm.factory import LLMFactory
from app.qa.cache import CacheManager
from app.qa.memory import SessionManager, MemoryManager
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.reranker import Reranker
from app.retrieval.vector_store import VectorStoreAdapter

# 配置日志脱敏 (重塑 Loguru patcher 拦截网)
logger.configure(patcher=mask_sensitive_data)

# 获取全局配置单例
config = get_config()

# 设置 Hugging Face 国内高速镜像源
if config.hf_endpoint:
    os.environ["HF_ENDPOINT"] = config.hf_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理器：在启动时优雅挂载组件，关闭时清理资源."""
    logger.info("🚀 正在初始化 Trilium 知识库智能体全局单例组件并注入 Container...")
    try:
        # 1. 实例化缓存与原生内存管理 (100% 摆脱 LangChain 影子)
        container.cache_manager = CacheManager(config)
        container.session_manager = SessionManager()
        container.memory_manager = MemoryManager(config)

        # 2. 异步初始化耗时大模型组件 (自适应极速探测)
        try:
            container.llm_adapter = await asyncio.to_thread(LLMFactory.create_llm, config)
        except Exception as e:
            container.set_error(f"LLM 适配器驱动初始化发生致命异常: {e}")
        
        # 3. 异步初始化 FastEmbed 词向量适配器
        embedding_adapter = EmbeddingAdapter(config)
        try:
            await asyncio.to_thread(embedding_adapter.initialize)
            if embedding_adapter.is_mocked:
                container.set_error("FastEmbed 词向量模块加载失败，已自动开启 Native 模拟词向量保护，系统保持正常运转。")
        except Exception as e:
            container.set_error(f"Embedding 初始化异常: {e}")
        
        # 4. 挂载 LanceDB 混合搜索引擎
        container.vector_store = VectorStoreAdapter(config, embedding_adapter)
        await asyncio.to_thread(container.vector_store.initialize)
        
        # 5. 挂载 FastEmbed BGE 重排模块
        container.reranker = Reranker(config)
        await asyncio.to_thread(container.reranker.initialize)

        logger.info("🎉 Trilium 智能体全局业务及算法组件装载就绪，正常开启问答管道！")
    except Exception as e:
        container.set_error(f"全局容器组件生命周期启动发生致命错误: {e}")
        logger.exception("详细错误回溯:")

    # ===============================
    # 让 FastAPI 服务在此处安全运行
    # ===============================
    yield
    
    # ===============================
    # 服务关闭后的资源清理逻辑
    # ===============================
    logger.info("🔌 应用正在关闭，释放 Container 资源...")
    container.cleanup()
    logger.info("💾 资源释放完成，应用已安全关闭")


# 创建 FastAPI 实例
app = FastAPI(
    title="Trilium Knowledge Agent",
    description="一个基于 FastAPI 的超轻量级应用，用于与 Trilium Notes 进行语义级混合搜索与 RAG 流式交互问答。",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 跨域请求中间件
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含 API V1 路由
app.include_router(api_router, prefix="/api/v1")

# 挂载前端静态页面资源 (防卫式自适应双端感知设计，宿主机与容器全兼容)
container_frontend_dir = Path("/frontend/public")
local_frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "public"

if container_frontend_dir.exists():
    frontend_dir = container_frontend_dir
    logger.info(f"🚀 成功在容器内检测并挂载外部前端静态资源: {frontend_dir}")
else:
    frontend_dir = local_frontend_dir

if not frontend_dir.exists():
    logger.warning(f"⚠️ 前端静态目录未检测到: {frontend_dir}，正在动态建立引导兜底桩...")
    # 为了防止 uvicorn 挂载 StaticFiles 时发生 RuntimeError 崩溃，我们优雅在物理上生成临时兜底桩
    temp_frontend_dir = Path(__file__).parent.parent / "temp_frontend_public"
    temp_frontend_dir.mkdir(parents=True, exist_ok=True)
    temp_assets_dir = temp_frontend_dir / "assets"
    temp_assets_dir.mkdir(parents=True, exist_ok=True)
    
    # 写入美观的系统级引导提示 HTML
    index_html = temp_frontend_dir / "index.html"
    index_html.write_text("""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Trilium Agent 引导页</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }
        .card { max-width: 600px; margin: 0 auto; background: #1e293b; padding: 40px 30px; border-radius: 16px; box-shadow: 0 10px 25px -3px rgba(0,0,0,0.5); border: 1px solid #334155; }
        h1 { color: #38bdf8; font-size: 28px; margin-bottom: 20px; }
        p { line-height: 1.6; color: #cbd5e1; font-size: 16px; }
        .tip { background: #0f172a; padding: 12px; border-radius: 8px; color: #f43f5e; font-family: monospace; font-size: 14px; border: 1px solid #1e293b; text-align: left; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Trilium Agent Backend 成功运行</h1>
        <p>后端服务启动极其顺利！当前前端托管处于 <b>自适应沙盒守护模式</b>。</p>
        <p class="tip">温馨提示：如果您是在 Docker 容器内运行，请在 docker-compose.yml 的 volumes 挂载项下追加前端路径映射（例如：- ./frontend:/frontend），让前后端整合容器完美融合。</p>
        <p>后端的 API 路由 <code>/api/v1</code> 和 <code>/health</code> 均处于 100% 可用状态！</p>
    </div>
</body>
</html>""", encoding="utf-8")
    frontend_dir = temp_frontend_dir

app.mount("/assets", StaticFiles(directory=str(frontend_dir)), name="assets")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """软性接管浏览器对 /favicon.ico 的默认底层高频请求，完美消除 404 报警."""
    favicon_path = frontend_dir / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    return Response(status_code=204)


@app.get("/")
async def root():
    """主入口直接返回单页面前端 APP，防缓存、秒级热生效版本控制."""
    import time
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        css_path = frontend_dir / "styles.css"
        js_path = frontend_dir / "script.js"
        
        # 提取文件最后修改时间戳作为无损防缓存 version 标签
        css_v = int(css_path.stat().st_mtime) if css_path.exists() else int(time.time())
        js_v = int(js_path.stat().st_mtime) if js_path.exists() else int(time.time())
        
        html_content = index_path.read_text(encoding="utf-8")
        # 动态追加防缓存版本号
        html_content = html_content.replace("/assets/styles.css", f"/assets/styles.css?v={css_v}")
        html_content = html_content.replace("/assets/script.js", f"/assets/script.js?v={js_v}")
        
        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "Trilium Agent Backend is running. Frontend index.html not found."}


@app.get("/health")
@app.get("/api/v1/health")  # 同时支持直连与子路由健康度探测
async def health_check():
    """超高鲁棒性的系统健康监测端点，绝对不崩溃."""
    health_status = {
        "status": "healthy",
        "components": {"llm": "unknown", "vector_db": "unknown", "reranker": "unknown"},
        "trilium_base_url": container.config.trilium_base_url,
        "errors": container.init_errors
    }

    # 1. 监测 LLM 连通度
    if container.llm_adapter:
        # 如果是 Mock 退化，标记为 degraded
        if container.llm_adapter.__class__.__name__ == "MockLLMAdapter":
            health_status["components"]["llm"] = "degraded (mocked)"
            health_status["status"] = "degraded"
        else:
            health_status["components"]["llm"] = "available"
    else:
        health_status["components"]["llm"] = "unavailable"
        health_status["status"] = "degraded"

    # 2. 监测 LanceDB 数据库加载度
    logger.debug(f"[健康检测] container.vector_store: {container.vector_store}")
    if container.vector_store:
        logger.debug(f"[健康检测] container.vector_store.table: {container.vector_store.table}")
        
    if container.vector_store and container.vector_store.table is not None:
        health_status["components"]["vector_db"] = "available"
    else:
        health_status["components"]["vector_db"] = "unavailable"
        health_status["status"] = "degraded"

    # 3. 监测 BGE 重排模型初始化状态
    if container.reranker:
        if not container.reranker._initialized:
            health_status["components"]["reranker"] = "pending_initialization"
        elif getattr(container.reranker, "_model", None) is not None:
            health_status["components"]["reranker"] = "advanced_cross_encoder"
        else:
            health_status["components"]["reranker"] = "basic_fallback"
            
    if health_status["components"]["llm"] == "unavailable" and health_status["components"]["vector_db"] == "unavailable":
        health_status["status"] = "unhealthy"

    return health_status


def check_and_download_models():
    """模型配置预检（已废除过时的 GPT4All 本地 bin 检测，本地离线推荐使用 Ollama）."""
    return True


if __name__ == "__main__":
    logger.info("⚙️ 正在检查必需的本地模型配置...")
    check_and_download_models()
    
    # 启动后台 Uvicorn 高效 ASGI 服务
    uvicorn.run(app="app.main:app", host="0.0.0.0", port=8000, reload=True)
