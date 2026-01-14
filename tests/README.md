# 测试文档

## 概述

本目录包含Trilium Knowledge Agent项目的测试套件，使用pytest框架编写。

## 测试结构

```
tests/
├── conftest.py          # Pytest配置和fixtures
├── test_config.py       # 配置管理模块测试
├── test_schemas.py      # API Schema验证测试
└── README.md           # 本文档
```

## 运行测试

### 安装测试依赖

```bash
pip install pytest pytest-cov
```

### 运行所有测试

```bash
# 基本运行
pytest tests/

# 详细输出
pytest tests/ -v

# 显示测试覆盖率
pytest tests/ --cov=app --cov-report=html

# 运行特定测试文件
pytest tests/test_config.py -v

# 运行特定测试类
pytest tests/test_config.py::TestConfigValidation -v

# 运行特定测试方法
pytest tests/test_config.py::TestConfigValidation::test_valid_config -v
```

## 测试模块说明

### test_config.py

测试配置管理模块（`app/core/config.py`），包括：

- **TestConfigConstants**: 测试配置常量的定义
- **TestConfigValidation**: 测试配置验证逻辑
  - 有效配置
  - 空token/URL检测
  - 无效数值配置检测
  - chunk_size和chunk_overlap验证
- **TestConfigTypeConversion**: 测试类型转换和默认值
- **TestConfigRepr**: 测试字符串表示（确保不泄露敏感信息）
- **TestConfigDefaults**: 测试所有默认值

### test_schemas.py

测试API Schema模块（`app/api/schemas.py`），包括：

- **TestQuestionRequest**: 测试问题请求验证
  - 有效问题
  - 空问题检测
  - 长度限制
  - 恶意内容检测（XSS防护）
- **TestSourceDocument**: 测试源文档模型
  - 字段验证
  - 长度限制
- **TestErrorDetail**: 测试错误详情模型
- **TestAnswerResponse**: 测试答案响应模型

### conftest.py

提供测试fixtures和配置：

- **test_env**: 测试环境变量fixture
- **mock_config**: 模拟Config对象fixture

## 测试覆盖目标

- **目标覆盖率**: 60%+（P2阶段）
- **当前状态**: 基础测试已实现
- **待补充**: 
  - 知识库模块测试（test_knowledge_base.py）
  - QA服务模块测试（test_qa_service.py）
  - Trilium集成测试（test_trilium_integration.py）
  - 集成测试（test_integration.py）

## 测试最佳实践

1. **命名规范**:
   - 测试文件: `test_<module_name>.py`
   - 测试类: `Test<FeatureName>`
   - 测试方法: `test_<what_it_tests>`

2. **测试结构**:
   - 使用AAA模式（Arrange-Act-Assert）
   - 每个测试方法测试一个具体场景
   - 使用descriptive测试名称

3. **Fixtures使用**:
   - 共享的测试数据放在`conftest.py`
   - 使用适当的scope（function/class/module/session）
   - 避免fixture之间的依赖

4. **Mock使用**:
   - 只mock外部依赖（数据库、API等）
   - 不要过度mock，保持测试的真实性
   - 使用`@patch.dict(os.environ, ...)`模拟环境变量

## CI/CD集成

待实现 - 将在P3阶段添加GitHub Actions配置

## 贡献指南

添加新功能时，请同时添加相应的测试用例：

1. 在`tests/`目录创建对应的测试文件
2. 确保测试覆盖主要功能路径
3. 运行测试确保通过
4. 提交PR时包含测试用例

## 常见问题

### Q: 测试失败提示找不到模块？
A: 确保在项目根目录运行pytest，或者设置PYTHONPATH：
```bash
export PYTHONPATH=$PWD:$PYTHONPATH  # Linux/Mac
set PYTHONPATH=%CD%;%PYTHONPATH%     # Windows
```

### Q: 如何跳过某些测试？
A: 使用pytest的mark功能：
```python
@pytest.mark.skip(reason="暂时跳过")
def test_something():
    pass
```

### Q: 如何测试异步代码？
A: 使用pytest-asyncio：
```bash
pip install pytest-asyncio
```

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

## 更新日志

- **2025-01-13**: 创建初始测试套件（test_config.py, test_schemas.py）
- **待补充**: 更多核心模块的测试用例
