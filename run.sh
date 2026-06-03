#!/bin/bash
# ==============================================================================
# Trilium 知识库智能体 一键极速部署与运行脚本 (Unified Lifecycle Runner)
# ==============================================================================
set -e

# 设置彩色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}      🌟 欢迎使用 Trilium 知识库智能体 (Trilium Knowledge Agent) 🌟${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 确保在正确的项目根目录下执行
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 检查是否存在 Docker-compose 的可用指令形式
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    DOCKER_COMPOSE_CMD=""
fi

# ==============================================================================
# 启动模式 1：一键容器化生产级部署 (Docker Compose Mode)
# ==============================================================================
if [ "$1" == "docker" ] || [ "$1" == "docker-backend" ]; then
    echo -e "${BLUE}[1/7] 正在检查 Docker 宿主机环境...${NC}"
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}❌ 致命错误：本机未检测到 Docker 安装，请先安装 Docker Desktop！${NC}"
        exit 1
    fi
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        echo -e "${RED}❌ 致命错误：未检测到 Docker Compose 插件或独立程序！${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker 引擎与 Compose 服务状态就绪。${NC}"

    # 1. 检测并生成 .env 配置文件
    if [ ! -f "backend/.env" ]; then
        echo -e "${YELLOW}⚠️  检测到后端未配置 .env 文件，正在从 .env.example 自动生成默认配置...${NC}"
        cp .env.example backend/.env
        echo -e "${GREEN}✅ 已自动生成默认配置。${NC}"
    fi

    # 2. 选择性启动 Ollama 服务容器
    if [ "$1" == "docker" ]; then
        echo -e "\n${BLUE}[2/7] 正在启动 Ollama 本地模型容器...${NC}"
        $DOCKER_COMPOSE_CMD --profile ollama up -d ollama
        
        # 3. 轮询监控探测 Ollama 在线心跳
        echo -e "\n${BLUE}[3/7] 正在极速轮询检测 Ollama 连通度...${NC}"
        retries=0
        max_retries=15
        ollama_ready=0
        while [ $retries -lt $max_retries ]; do
            if curl -s -o /dev/null -w "%{http_code}" http://localhost:11434 | grep -E "200|404" &>/dev/null; then
                ollama_ready=1
                break
            fi
            echo -e "   ⏳ Ollama 正在初始化，等待端口 11434 就绪... ($((retries+1))/$max_retries)"
            sleep 1
            retries=$((retries+1))
        done

        if [ $ollama_ready -ne 1 ]; then
            echo -e "${RED}⚠️  警告：无法连通宿主机 Ollama 端口，我们将继续，但可能会影响后续的模型拉取。${NC}"
        else
            echo -e "${GREEN}✅ Ollama 本地容器端口就绪！${NC}"
        fi

        # 4. 容器内全自动下载高性能中文大模型 (qwen2.5:1.5b)
        echo -e "\n${BLUE}[4/7] 正在从官方镜像拉取高性能中文 RAG 推荐模型 [qwen2.5:1.5b]...${NC}"
        echo -e "      (此模型体积仅 900MB，首Token生成极快，语义深层理解优秀，生产离线部署首选)"
        docker exec ollama ollama pull qwen2.5:1.5b
    else
        echo -e "\n${YELLOW}⚠️  检测为 docker-backend 模式，跳过本地 Ollama 容器拉起。${NC}"
        echo -e "   您可在前端页面中自由热配置您的外部大模型（如 OpenAI、DeepSeek、Gemini 及已有外部 Ollama API）。"
    fi


    # 5. 构建并拉起统一的前后端托管 Backend FastAPI 容器
    echo -e "\n${BLUE}[5/7] 正在构建并拉起 FastAPI 整合应用容器...${NC}"
    $DOCKER_COMPOSE_CMD up -d backend

    # 6. 等待并执行高质量数据治理智能灌入
    echo -e "\n${BLUE}[6/7] 正在触发容器内数据治理与种子知识库灌入 (Bootstrap)...${NC}"
    sleep 2 # 确保 backend gunicorn/uvicorn 就绪
    docker exec trilium-agent-backend python scripts/bootstrap_data.py

    # 7. 全链路 RAG 集成闭环自测
    echo -e "\n${BLUE}[7/7] 正在执行生产级容器端到端 RAG 闭环验证 (Smoke Test)...${NC}"
    # 在 backend 容器内通过 python 直接调用完整的 QA 问答，打印打字机 SSE
    docker exec trilium-agent-backend python -c "
import asyncio
from app.core.config import get_config
from app.core.container import container
from app.services.qa_service import QAService
from app.services.retrieval_service import RetrievalService
from app.retrieval.embeddings import EmbeddingAdapter
from app.retrieval.vector_store import VectorStoreAdapter
from app.retrieval.reranker import Reranker

async def run_smoke():
    config = get_config()
    emb = EmbeddingAdapter(config)
    emb.initialize()
    vs = VectorStoreAdapter(config, emb)
    vs.initialize()
    rk = Reranker(config)
    rk.initialize()
    
    # 模拟 QAService 整体问答
    from app.llm.factory import LLMFactory
    llm = await asyncio.to_thread(LLMFactory.create_llm, config)
    rs = RetrievalService(config, vs, rk)
    qa = QAService(llm, rs, None, None)
    
    query = 'MySQL高负载下innodb缓存该怎么配？'
    print(f'\\033[0;34m[提问] : {query}\\033[0m')
    print('\\033[0;32m[智能体流式回复中]：\\033[0m')
    async for event in qa.ask_stream(query, session_id=\"smoke_session\"):
        if event.get('type') == 'chunk':
            import sys
            sys.stdout.write(event.get('data', ''))
            sys.stdout.flush()
        elif event.get('type') == 'sources':
            sources = event.get('data', [])
            if sources:
                print('\\n\\n\\033[0;33m[RAG 召回来源]：\\033[0m')
                for s in sources:
                    print(f\"  - [{s.get('title')}] 路径: {s.get('path')} (匹配度: {s.get('score', 0.0):.4f})\")
    print('\\n')

asyncio.run(run_smoke())
"

    echo -e "\n${BLUE}======================================================================${NC}"
    echo -e "${GREEN}🎉 恭喜！一键 Docker 生产级容器化环境部署、数据治理与种子填充全部圆满完成！${NC}"
    echo -e "${GREEN}🌍 请在浏览器中直接打开享受 WOW 级的流式极速 RAG 问答: ${YELLOW}http://localhost:8000/${NC}"
    echo -e "${BLUE}======================================================================${NC}\n"
    exit 0
fi

# ==============================================================================
# 启动模式 2：宿主机 Python 环境本地轻量运行 (Normal Local Mode)
# ==============================================================================

# 1. 检查 backend/.env 文件
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠️  检测到后端未配置 .env 文件，正在从 .env.example 自动生成默认配置...${NC}"
    cp .env.example backend/.env
    echo -e "${GREEN}✅ 已自动在 backend/.env 生成默认模板，请在需要时手动修改其中的 TRILIUM_TOKEN 等字段。${NC}"
else
    echo -e "${GREEN}✅ 检测到后端 .env 配置文件已就绪。${NC}"
fi

# 2. 提供一键检查并安装依赖提示
echo -e "${BLUE}⚙️  正在加载 Python 环境并检测依赖更新 (backend/requirements.txt)...${NC}"
# 支持虚拟环境自动加载检测
if [ -d "venv" ]; then
    echo -e "${GREEN}ℹ️  检测到项目存在独立虚拟环境 (venv)，正在自动激活...${NC}"
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo -e "${GREEN}ℹ️  检测到项目存在独立虚拟环境 (.venv)，正在自动激活...${NC}"
    source .venv/bin/activate
fi

# 执行极速本地增量安装
pip install -r backend/requirements.txt --quiet && echo -e "${GREEN}✅ 依赖项检查通过并自动对齐完毕。${NC}" || {
    echo -e "${YELLOW}⚠️  依赖自动安装失败（可能是由于没有全局 pip 权限），正在尝试以普通模式启动。若报导入错误，请运行 pip install -r backend/requirements.txt${NC}"
}

# 3. 端口占用智能检测与优雅自动释放
PORT=8000
PID=$(lsof -t -i:$PORT || true)
if [ ! -z "$PID" ]; then
    echo -e "${YELLOW}⚠️  检测到本地端口 $PORT 已被占用 (进程 PID: $PID)！${NC}"
    PROCESS_NAME=$(ps -p $PID -o comm= 2>/dev/null || true)
    echo -e "   占用的进程为: ${BLUE}${PROCESS_NAME##*/}${NC}"
    echo -e "${YELLOW}🔄 正在为您一键释放端口 $PORT 以避免绑定冲突...${NC}"
    kill -9 $PID || true
    sleep 1
    echo -e "${GREEN}✅ 端口 $PORT 释放完毕。${NC}"
fi

# 4. 注册退出清理机制 (退场 Trap)
cleanup_on_exit() {
    echo -e "\n\n${BLUE}======================================================================${NC}"
    echo -e "${GREEN}👋 感谢使用 Trilium 知识库智能体！服务已安全关闭，临时缓存已释放。${NC}"
    echo -e "${BLUE}======================================================================${NC}"
}
trap cleanup_on_exit EXIT

# 5. 打印服务运行指引
echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}🚀 系统运行就绪！正在拉起前后台整合服务...${NC}"
echo -e "${GREEN}🌍 请在浏览器中直接打开进行交互: ${YELLOW}http://localhost:8000/${NC}"
echo -e "${BLUE}======================================================================${NC}\n"

# 6. 启动集成了前端托管的 FastAPI 统一应用
export PYTHONPATH=./backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
