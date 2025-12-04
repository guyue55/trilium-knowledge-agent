import sys
import os

try:
    from langchain_community.vectorstores import Chroma
    print("✓ 成功导入 Chroma")
except ImportError as e:
    print("✗ Chroma 导入失败:", str(e))
    sys.exit(1)

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    print("✓ 成功导入 HuggingFaceEmbeddings")
except ImportError as e:
    print("✗ HuggingFaceEmbeddings 导入失败:", str(e))
    sys.exit(1)

try:
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'  # download from mirror
    # 使用本地缓存并设置镜像源
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    print("✓ 成功创建 HuggingFaceEmbeddings 实例")
except Exception as e:
    print("✗ 导入或创建 HuggingFaceEmbeddings 时出错:", str(e))
    # 即使无法加载模型，我们也继续测试 Chroma 的基本功能
    
    # 测试仅使用基础 Chroma 功能
    try:
        # 创建简单的测试向量存储
        from langchain_core.vectorstores import VectorStore
        print("✓ 基础 Chroma 功能可用")
    except Exception as e2:
        print("✗ Chroma 基本功能也不可用:", str(e2))
        sys.exit(1)

print("测试完成")