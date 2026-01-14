# -*- coding: utf-8 -*-
"""统一异常处理模块."""

from typing import Optional
from fastapi import HTTPException, status
from loguru import logger


class BaseAppException(Exception):
    """应用程序基础异常类."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        
    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"


class ConfigException(BaseAppException):
    """配置相关异常."""
    pass


class KnowledgeBaseException(BaseAppException):
    """知识库相关异常."""
    pass


class LLMException(BaseAppException):
    """语言模型相关异常."""
    pass


class TriliumException(BaseAppException):
    """Trilium相关异常."""
    pass


class QAException(BaseAppException):
    """问答服务相关异常."""
    pass


def handle_app_exception(exc: BaseAppException, exc_type: str = "internal_error"):
    """处理应用程序异常并记录日志."""
    logger.error(f"{exc_type.upper()} - {exc.__class__.__name__}: {exc.message}")
    
    # 根据异常类型返回适当的HTTP状态码
    if isinstance(exc, (ConfigException, QAException)):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, (TriliumException, LLMException)):
        status_code = status.HTTP_502_BAD_GATEWAY
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    return HTTPException(
        status_code=status_code,
        detail={
            "error": exc_type,
            "message": exc.message,
            "error_code": exc.error_code
        }
    )


# 异常处理装饰器
def exception_handler(func):
    """装饰器：统一异常处理."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseAppException as e:
            logger.exception(f"应用程序异常: {e}")
            raise handle_app_exception(e)
        except Exception as e:
            logger.exception(f"未处理的异常: {e}")
            raise handle_app_exception(
                BaseAppException(str(e)), 
                "unexpected_error"
            )
    return wrapper