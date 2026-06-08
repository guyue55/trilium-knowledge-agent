# 使用官方 Python 3.10-slim 镜像
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_ENDPOINT=https://hf-mirror.com

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端、前端及系统工具脚本，实现高度内建与自给自足 (生产部署无需任何开发 volumes 挂载)
COPY backend/ /app/
COPY frontend/ /frontend/
COPY scripts/ /app/scripts/

# 创建必要的数据目录
RUN mkdir -p data/models data/vector_db data/trilium

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
