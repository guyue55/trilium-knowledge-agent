# 安装指南

## 依赖安装问题解决

在安装依赖时可能会遇到一些问题，以下是常见问题及解决方案：

## 问题1：依赖冲突

如果遇到如下错误：
```
ERROR: Cannot install -r requirements.txt (line X) because these package versions have conflicting dependencies.
```

### 解决方案：

1. **分步安装依赖**：
   ```bash
   # 安装核心Web框架
   pip install fastapi==0.95.0 uvicorn==0.21.1 pydantic==1.10.7
   
   # 安装AI相关库
   pip install langchain==0.0.350 langchain-community==0.0.20 langchain-core==0.1.23
   
   # 安装数据库和工具
   pip install chromadb==0.4.22
   
   # 安装前端和工具
   pip install streamlit==1.28.0 requests==2.31.0 watchdog==3.0.0 python-dotenv==1.0.0
   
   # 安装语言模型
   pip install gpt4all==2.0.0
   ```

2. **使用特定版本安装**：
   ```bash
   pip install -r requirements-simple.txt
   ```

## 问题2：网络问题

如果下载依赖时出现网络问题，可以使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
# 或者
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
# 或者
pip install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/
```

## 问题3：权限问题

如果遇到权限问题，可以使用用户安装模式：

```bash
pip install --user -r requirements.txt
```

## 问题4：Python版本兼容性问题

您当前使用的是 Python 3.12.4，某些库可能尚未完全支持此版本。如果遇到兼容性问题，建议：

1. **使用兼容的库版本**（已在requirements-simple.txt中更新）
2. **降级Python版本**到3.10或3.11（推荐）：
   ```bash
   # 使用conda创建Python 3.10环境
   conda create -n trilium-agent python=3.10
   conda activate trilium-agent
   ```

## 问题5：ONNX Runtime DLL加载失败

如果遇到以下错误：
```
ImportError: DLL load failed while importing onnxruntime_pybind11_state: 动态链接库(DLL)初始化例程失败。
```

请尝试重新安装onnxruntime：
```bash
pip uninstall onnxruntime -y
pip install onnxruntime==1.17.0
```

## 问题6：Pydantic版本兼容性问题

如果遇到以下错误：
```
TypeError: ForwardRef._evaluate() missing 1 required keyword-only argument: 'recursive_guard'
```

这是由于Pydantic版本不兼容导致的，请安装兼容的版本：
```bash
pip install pydantic==1.10.7
```

## 问题7：Langchain导入错误

如果遇到导入错误，特别是与HuggingFaceEmbeddings或Chroma相关的错误，请确保安装了正确的langchain组件：
```bash
pip install langchain==0.0.350 langchain-community==0.0.20
```

## 推荐安装流程

1. **创建虚拟环境**（推荐）：
   ```bash
   # 使用venv
   python -m venv trilium-agent-env
   # Windows激活
   trilium-agent-env\Scripts\activate
   # Linux/Mac激活
   source trilium-agent-env/bin/activate
   ```

   或者使用conda：
   ```bash
   conda create -n trilium-agent python=3.10
   conda activate trilium-agent
   ```

2. **分步安装依赖**：
   ```bash
   # 安装核心Web框架（注意使用兼容的pydantic版本）
   pip install fastapi==0.95.0 uvicorn==0.21.1 pydantic==1.10.7
   
   # 安装数据库
   pip install chromadb==0.4.22 onnxruntime==1.17.0 pulsar-client==3.8.0
   
   # 安装AI库
   pip install langchain==0.0.350 langchain-community==0.0.20 langchain-core==0.1.23
   
   # 安装前端和工具
   pip install streamlit==1.28.0 requests==2.31.0 watchdog==3.0.0 python-dotenv==1.0.0
   
   # 安装语言模型和嵌入模型
   pip install gpt4all==2.0.0 sentence-transformers==2.2.2 huggingface-hub==0.19.4
   ```

3. **验证安装**：
   ```bash
   python -c "import fastapi, langchain, chromadb; print('核心依赖安装成功')"
   ```

## 手动下载模型

某些模型可能需要手动下载：

1. **嵌入模型**：
   ```bash
   python scripts/download_embedding_model.py
   ```

2. **语言模型**：
   ```bash
   # 下载GPT4All模型
   wget https://gpt4all.io/models/ggml-gpt4all-j-v1.3-groovy.bin -P ./data/models/gpt4all/
   ```

## 常见问题

### Q: 安装过程中出现"Microsoft Visual C++ 14.0 is required"错误
A: 这通常发生在Windows系统上安装某些需要编译的包时。解决方案：
1. 安装Microsoft C++ Build Tools
2. 或者使用conda安装预编译版本：
   ```bash
   conda install -c conda-forge package_name
   ```

### Q: 安装chromadb时出现onnxruntime或pulsar-client问题
A: 可以先单独安装这些依赖：
```bash
pip install onnxruntime==1.17.0
pip install pulsar-client==3.8.0
pip install chromadb==0.4.22
```

### Q: 安装gpt4all时出现问题
A: 可以尝试：
```bash
pip install gpt4all --no-cache-dir
```

## 验证安装

安装完成后，可以通过以下方式验证：

```bash
# 检查FastAPI
python -c "import fastapi; print(f'FastAPI版本: {fastapi.__version__}')"

# 检查LangChain
python -c "import langchain; print(f'LangChain版本: {langchain.__version__}')"

# 检查ChromaDB
python -c "import chromadb; print('ChromaDB安装成功')"

# 检查Streamlit
python -c "import streamlit; print('Streamlit安装成功')"

# 检查核心组件
python -c "from app.core.knowledge_base import KnowledgeBase; print('KnowledgeBase导入成功')"
```

如果所有检查都通过，您就可以开始使用Trilium知识库智能体了。