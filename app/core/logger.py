"""日志配置模块."""

from loguru import logger
import os
from datetime import datetime


def setup_logger(name: str = "trilium_knowledge", level: str = "INFO"):
    """设置日志记录器.
    
    Args:
        name: 日志记录器名称
        level: 日志级别
    """
    # 移除默认的处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sink="stdout",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{line} | {message}",
        colorize=True
    )
    
    # 添加文件处理器
    logger.add(
        sink=os.path.join("./logs", "{time:YYYY-MM-DD}.log"),
        level="DEBUG",
        rotation="1 day",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {file}:{line} | {message}"
    )


# 确保日志目录存在
os.makedirs("./logs", exist_ok=True)

# 初始化日志记录器
setup_logger()