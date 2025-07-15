#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agents 多语言实时翻译广播系统 - 主入口
支持多语言同时运行，提供RPC控制接口
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession
from agent_config import build_agent_for

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("translation-agent")

# 房间与语言的映射关系
ROOM_LANGUAGE_MAP = {
    "Pryme-Japanese": "ja",
    "Pryme-Korean": "ko",
    "Pryme-Vietnamese": "vi",
    "Pryme-Malay": "ms"
}

# 保存所有运行中的代理实例
active_agents = {}

async def create_agent(room_name: str, language: str) -> Agent:
    """
    创建并配置翻译代理
    
    Args:
        room_name: LiveKit房间名
        language: 目标语言代码
    
    Returns:
        配置好的Agent实例
    """
    logger.info(f"正在为房间 '{room_name}' 构建 {language} 语言翻译代理...")
    
    # 构建代理会话
    try:
        agent_session = build_agent_for(language)
    except ValueError as e:
        logger.error(f"构建代理失败: {str(e)}")
        return None
    
    # 添加状态变化回调
    def on_state_changed(old_state: str, new_state: str):
        logger.info(f"代理状态变化 [{room_name}/{language}]: {old_state} -> {new_state}")
    
    agent_session.on_state_changed = on_state_changed
    
    # 创建Agent实例
    agent = Agent(
        identity=f"translator-{language}",
        name=f"{language}翻译员",
        session=agent_session,
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
        room_name=room_name
    )
    
    # 注册RPC方法
    @agent.register_rpc_method("start_translation")
    async def start_translation():
        """开始翻译"""
        logger.info(f"收到RPC请求: 开始翻译 ({room_name}/{language})")
        await agent_session.start_listening()
        return {"status": "started", "room": room_name, "language": language}
    
    @agent.register_rpc_method("stop_translation")
    async def stop_translation():
        """停止翻译"""
        logger.info(f"收到RPC请求: 停止翻译 ({room_name}/{language})")
        await agent_session.stop_listening()
        return {"status": "stopped", "room": room_name, "language": language}
    
    return agent

async def run_agent(agent: Agent, room_name: str, language: str):
    """
    运行翻译代理并保持连接
    
    Args:
        agent: 要运行的Agent实例
        room_name: LiveKit房间名
        language: 目标语言代码
    """
    try:
        # 启动代理
        logger.info(f"正在连接代理到房间 '{room_name}'...")
        await agent.start()
        logger.info(f"代理已成功连接到房间 '{room_name}' ({language})")
        
        # 保持代理运行
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            if agent.is_stopped():
                logger.warning(f"代理已停止 ({room_name}/{language})，正在尝试重新连接...")
                try:
                    await agent.start()
                    logger.info(f"代理已重新连接 ({room_name}/{language})")
                except Exception as e:
                    logger.error(f"代理重新连接失败 ({room_name}/{language}): {str(e)}")
    
    except Exception as e:
        logger.error(f"运行代理时出错 ({room_name}/{language}): {str(e)}")
    
    # 注意: 我们不在这里关闭代理，因为我们希望它一直运行
    # 关闭操作会在主函数的finally块中处理

async def run_all_agents():
    """启动所有语言的翻译代理"""
    # 检查必要的环境变量
    required_env_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", 
                         "DEEPGRAM_API_KEY", "GROQ_API_KEY", "CARTESIA_API_KEY"]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        logger.error("请确保在.env文件中设置了这些变量")
        return
    
    # 为每个房间创建并启动代理
    tasks = []
    for room_name, language in ROOM_LANGUAGE_MAP.items():
        try:
            # 创建代理
            agent = await create_agent(room_name, language)
            if agent:
                # 保存代理实例
                active_agents[room_name] = agent
                # 创建运行任务
                task = asyncio.create_task(run_agent(agent, room_name, language))
                tasks.append(task)
                logger.info(f"已创建 {room_name} 房间的 {language} 语言翻译代理")
            else:
                logger.error(f"无法为 {room_name} 房间创建 {language} 语言翻译代理")
        except Exception as e:
            logger.error(f"创建代理时出错 ({room_name}/{language}): {str(e)}")
    
    # 等待所有任务完成（实际上它们会一直运行）
    if tasks:
        await asyncio.gather(*tasks)

async def shutdown_agents():
    """关闭所有运行中的代理"""
    for room_name, agent in active_agents.items():
        if agent and not agent.is_stopped():
            logger.info(f"正在关闭 {room_name} 房间的代理...")
            try:
                await agent.stop()
                logger.info(f"已关闭 {room_name} 房间的代理")
            except Exception as e:
                logger.error(f"关闭代理时出错 ({room_name}): {str(e)}")

async def main_async():
    """异步主函数"""
    try:
        await run_all_agents()
    except asyncio.CancelledError:
        logger.info("收到取消信号")
    except Exception as e:
        logger.error(f"运行代理时出错: {str(e)}")
    finally:
        await shutdown_agents()

def main():
    """主函数"""
    # 加载环境变量
    load_dotenv()
    
    logger.info("正在启动多语言实时翻译广播系统...")
    
    # 运行所有代理
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 