# 使用 Python 3.10s 基础镜像（匹配开发环境）
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖（如 gcc 等，如果某些 python 包需要编译）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_ENDPOINT=https://hf-mirror.com

# 复制并安装后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 如果前端有额外的依赖，可以在这里安装
# COPY frontend/requirements.txt ./frontend/
# RUN pip install --no-cache-dir -r frontend/requirements.txt

# 复制项目所有代码
COPY . .

# 创建必要的数据目录
RUN mkdir -p data/models data/vector_db data/trilium

# 暴露端口：8000 (FastAPI), 8501 (Streamlit)
EXPOSE 8000 8501

# 给启动脚本添加执行权限
RUN chmod +x run.sh

# 启动服务
CMD ["/bin/bash", "run.sh"]
