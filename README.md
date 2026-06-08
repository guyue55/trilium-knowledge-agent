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

项目支持一键式的 Docker Compose 容器部署，并默认启用了**零信任网络安全自启防护机制**。

#### 1. 一键启动服务
在项目根目录下，直接通过 Docker Compose 启动：
```bash
docker-compose up -d --build
```
系统将自动为您拉起 `trilium-agent-backend` 后端服务。

#### 2. 安全防线：API_AUTH_KEY 机制
在对外暴露端口或云服务器部署时，保障 API 的安全性极其重要。
- **自定义 Token 部署**：
  您可以在 `docker-compose.yml` 的 `environment:` 中配置 `API_AUTH_KEY`，或者在容器启动时指定此环境变量：
  ```yaml
  environment:
    - API_AUTH_KEY=your_secret_api_key_here
  ```
- **默认安全自启生成（推荐）**：
  如果您在部署时**没有指定或留空了 `API_AUTH_KEY`**，系统为了防止服务对外直接裸奔导致泄露大模型 API Key 额度，**会自动启动防护并在日志中随机生成一个 16 位强安全凭证**。
  
  **如何获取并使用生成的 Token：**
  1. 运行以下命令查看后端启动日志：
     ```bash
     docker logs trilium-agent-backend
     ```
  2. 您将会在日志中看到醒目的金钥匙警告框：
     ```text
     🔑 [DOCKER 安全自启防护] 检测到处于容器部署环境，且未配置 API_AUTH_KEY 环境变量！
     👉 为了防止服务公开暴露导致的安全隐患，系统已为您自动生成随机安全 Auth Token:

        trilium_agent_123456abcdef...

     👉 请复制此 Token，并填入前端界面左侧边栏底部的 [Auth Token] 输入框中，方可连通后端。
     ```
  3. 复制该 Token 值，刷新网页后直接填入前端主界面左下角侧边栏底部的 **[Auth Token]** 密码框中，系统将自愈重连，双端即可无缝打通安全交互通道。

- **本地免密对比**：
  在非 Docker 容器环境（即直接通过 `uvicorn` 本地命令行启动）中运行时，如果您不填 `API_AUTH_KEY`，则依然默认不开启密码鉴权，不影响本地开箱即用的免登录、极简本地体验。这实现了“本地零摩擦”与“容器高安全”的完美统一。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目。

## 许可证

[MIT](LICENSE)