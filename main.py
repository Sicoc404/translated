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
# 修正导入路径 - 使用新的导入方式
from livekit.agents import Agent, JobContext, WorkerOptions, cli
from livekit.rtc import Room, RoomOptions
from agent_config import build_agent_for, LANGUAGE_CONFIG

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

# 保存所有运行中的会话实例
active_sessions = {}

async def create_room_connection(room_name: str) -> Room:
    """
    创建并连接到LiveKit房间
    
    Args:
        room_name: LiveKit房间名
    
    Returns:
        已连接的Room实例
    """
    from livekit.rtc import Room, RoomOptions
    from livekit.api import AccessToken, VideoGrants
    
    # 创建访问令牌
    token = (
        AccessToken(os.getenv("LIVEKIT_API_KEY"), os.getenv("LIVEKIT_API_SECRET"))
        .with_identity(f"translator-agent")
        .with_name("翻译助手")
        .with_grants(VideoGrants(room=room_name, room_join=True))
        .to_jwt()
    )
    
    # 创建房间实例
    room = Room()
    
    # 连接到房间
    await room.connect(os.getenv("LIVEKIT_URL"), token, RoomOptions())
    
    return room

async def run_translation_agent(room_name: str, language: str):
    """
    运行特定语言的翻译代理
    
    Args:
        room_name: LiveKit房间名
        language: 目标语言代码
    """
    logger.info(f"正在为房间 '{room_name}' 启动 {language} 语言翻译代理...")
    
    try:
        # 连接到房间
        room = await create_room_connection(room_name)
        
        # 构建代理和会话
        agent, session = build_agent_for(language)
        
        # 保存会话实例，以便后续管理
        active_sessions[room_name] = session
        
        # 启动会话
        await session.start(agent=agent, room=room)
        
        # 生成初始回复
        language_name = LANGUAGE_CONFIG.get(language, {}).get("name", language)
        await session.generate_reply(
            instructions=f"向用户问好，告诉他们这是一个中文到{language_name}的翻译助手"
        )
        
        # 保持会话运行
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            
    except Exception as e:
        logger.error(f"运行翻译代理时出错 ({room_name}/{language}): {str(e)}")
    finally:
        # 停止会话
        if room_name in active_sessions:
            try:
                await active_sessions[room_name].stop()
                logger.info(f"已停止 {room_name} 房间的翻译会话")
            except Exception as e:
                logger.error(f"停止会话时出错 ({room_name}): {str(e)}")
            
            # 从活动会话中移除
            del active_sessions[room_name]

async def run_all_agents():
    """启动所有语言的翻译代理"""
    # 检查必要的环境变量
    required_env_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        logger.error("请确保在.env文件中设置了这些变量")
        return
    
    # 为每个房间创建并启动代理
    tasks = []
    for room_name, language in ROOM_LANGUAGE_MAP.items():
        task = asyncio.create_task(run_translation_agent(room_name, language))
        tasks.append(task)
        logger.info(f"已创建 {room_name} 房间的 {language} 语言翻译代理任务")
    
    # 等待所有任务完成（实际上它们会一直运行）
    if tasks:
        await asyncio.gather(*tasks)

async def shutdown_sessions():
    """关闭所有运行中的会话"""
    for room_name, session in active_sessions.items():
        try:
            await session.stop()
            logger.info(f"已关闭 {room_name} 房间的会话")
        except Exception as e:
            logger.error(f"关闭会话时出错 ({room_name}): {str(e)}")

async def main_async():
    """异步主函数"""
    try:
        await run_all_agents()
    except asyncio.CancelledError:
        logger.info("收到取消信号")
    except Exception as e:
        logger.error(f"运行代理时出错: {str(e)}")
    finally:
        await shutdown_sessions()

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
