#!/bin/bash
# 启动后端 FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 等待后端启动（可选）
sleep 5

# 启动前端 Streamlit
streamlit run frontend/app.py --server.port 8501 --server.address 0.0.0.0
