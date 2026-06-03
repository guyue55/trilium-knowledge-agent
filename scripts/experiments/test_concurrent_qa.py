# -*- coding: utf-8 -*-
"""测试：并发执行阻塞的大模型问答与非阻塞的健康检查"""

import asyncio
import time
import httpx
from loguru import logger

API_URL = "http://localhost:8000/api/v1"

async def ask_question():
    """发送一个耗时的问答请求"""
    logger.info("-> 发起 QA 请求 (预期耗时较长)...")
    start = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/ask",
                json={"question": "请介绍一下苹果公司和它的产品"}
            )
            data = response.json()
            logger.info(f"<- QA 请求完成！耗时: {time.time() - start:.2f}秒. 答案: {data.get('answer')[:30]}...")
        except Exception as e:
            logger.error(f"<- QA 请求失败: {e}")

async def ping_health(interval=1.0, count=5):
    """循环 Ping 健康检查接口"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        for i in range(count):
            logger.info(f"-> 发起 Health Check 请求 {i+1}...")
            start = time.time()
            try:
                response = await client.get(f"{API_URL}/health")
                data = response.json()
                logger.info(f"<- Health Check {i+1} 返回！耗时: {time.time() - start:.3f}秒, 状态: {data.get('status')}")
            except Exception as e:
                logger.error(f"<- Health Check {i+1} 失败: {e}")
            await asyncio.sleep(interval)

async def main():
    logger.info("开始并发非阻塞测试...")
    
    # 并发执行 QA 请求与不断的健康检查探测
    await asyncio.gather(
        ask_question(),
        ping_health(interval=0.5, count=10)
    )
    
    logger.info("测试结束！")

if __name__ == "__main__":
    asyncio.run(main())
