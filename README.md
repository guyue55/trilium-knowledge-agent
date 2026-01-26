# Trilium知识库智能体

基于 FastAPI + LangChain + Trilium Notes 集成的知识问答系统。

## 简介

这是一个集成了 Trilium Notes 本地知识库的智能问答系统，利用检索增强生成 (RAG) 技术，能够基于您的个人知识库提供精准的回答。

## 功能特性

- 与 Trilium Notes 无缝集成
- 本地运行，保护您的隐私数据
- 支持自然语言问答
- 自动监控知识库更新
- 对话历史记忆功能

## 技术栈

- **Web框架**: FastAPI
- **AI框架**: LangChain
- **知识库**: Trilium Notes
- **向量数据库**: Chroma (本地)
- **嵌入模型**: sentence-transformers
- **语言模型**: GPT4All/Llama.cpp (本地运行)
- **前端界面**: Streamlit

## 目录结构

```
📂 trilium-knowledge-agent/
├── 📂 app/                  # 核心应用代码
│   ├── 📂 api/              # API 路由和控制器
│   ├── 📂 core/             # 核心业务逻辑
│   ├── 📂 models/           # 数据模型
│   └── 📂 utils/            # 工具函数
├── 📂 data/                 # 数据存储目录
│   ├── 📂 trilium/          # Trilium 相关数据
│   ├── 📂 vector_db/        # 向量数据库存储
│   └── 📂 models/           # 本地模型文件
├── 📂 frontend/             # 前端界面
│   └── 📄 app.py            # Streamlit 应用
├── 📂 scripts/              # 实用脚本
│   ├── 📄 setup_trilium.py  # Trilium 初始化脚本
│   └── 📄 update_knowledge_base.py  # 知识库更新脚本
├── 📂 tests/                # 测试目录
├── 📄 requirements.txt      # Python 依赖
├── 📄 .env.example          # 环境变量示例
└── 📄 README.md             # 项目文档
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件设置 Trilium 凭据等
```

### 初始化知识库

```bash
python scripts/setup_trilium.py
```

### 启动后端服务

```bash
uvicorn app.main:app --reload --port 8000
```

### 启动前端界面

```bash
streamlit run frontend/app.py
```

## 使用说明

1. 确保 Trilium Notes 正在运行并且可以通过 API 访问
2. 配置好 `.env` 文件中的相关参数
3. 初始化知识库
4. 启动后端服务和前端界面
5. 在前端界面中进行问答交互

## 前端界面功能

- 聊天式交互界面
- 对话历史记录
- 答案来源展示
- 可配置的后端 API 地址
- 清除对话历史功能

## 高级功能

### 知识库自动更新

系统会自动监控 Trilium 数据目录的变化，当检测到更新时会自动重新索引相关笔记。

### 对话历史记忆

系统保留对话历史，能够在多轮对话中保持上下文连贯性。

## 部署

### 本地部署

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化知识库
python scripts/setup_trilium.py

# 启动后端服务
uvicorn app.main:app --reload --port 8000

# 启动前端界面（在另一个终端）
streamlit run frontend/app.py
```

### Docker 部署

(待完善)

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

[MIT](LICENSE)