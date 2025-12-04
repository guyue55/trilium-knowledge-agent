# coding: utf-8
"""用于下载向量模型."""

'''方式1：

# from langchain.embeddings import HuggingFaceEmbeddings

# # 首次使用时会自动下载
# embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
'''


import os

# pip install huggingface_hub
from huggingface_hub import snapshot_download

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # download from mirror

snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2', local_dir='data/models/sentence-transformers/all-MiniLM-L6-v2')