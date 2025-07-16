#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agents 多语言实时翻译广播系统 - 主入口
使用LiveKit Agents 1.1.7的标准工作流程
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, JobProcess
from agent_config import create_agent_session_for_language, LANGUAGE_CONFIG

# 加载环境变量
load_dotenv()

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

async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent的入口点函数
    根据房间名称确定翻译语言并启动相应的代理
    
    Args:
        ctx: JobContext实例，包含房间连接信息
    """
    # 连接到房间
    await ctx.connect()
    
    # 获取房间名称
    room_name = ctx.room.name
    logger.info(f"连接到房间: {room_name}")
    
    # 根据房间名称确定目标语言
    target_language = None
    for room_prefix, language_code in ROOM_LANGUAGE_MAP.items():
        if room_name.startswith(room_prefix):
            target_language = language_code
            break
    
    if not target_language:
        logger.error(f"未知的房间名称: {room_name}，支持的房间前缀: {list(ROOM_LANGUAGE_MAP.keys())}")
        return
    
    language_name = LANGUAGE_CONFIG[target_language]["name"]
    logger.info(f"为房间 '{room_name}' 启动 {language_name} 翻译代理...")
    
    # 记录保持会话的变量
    session_to_close = None
    
    try:
        # 在JobContext内部创建Agent
        agent, session = await create_agent_session_for_language(ctx, target_language)
        session_to_close = session
        
        # 启动Agent
        agent.start(ctx.room)
        
        logger.info(f"{language_name} 翻译代理已成功启动")
        
        # 可选：发送初始消息
        await agent.say(f"你好！我是 {language_name} 翻译助手，我会将中文实时翻译成 {language_name}。")
        
    except Exception as e:
        logger.error(f"启动 {language_name} 翻译代理时出错: {e}")
        if session_to_close:
            await session_to_close.close()
        raise
    
    # 保持连接直到代理关闭
    await agent.aclose()
    
    # 清理资源
    if session_to_close:
        await session_to_close.close()
        logger.info(f"{language_name} 翻译代理已停止，资源已清理")

def prewarm(proc: JobProcess):
    """
    预热函数 - 在每个子进程启动时执行
    可以在此处加载模型或执行其他预热操作
    
    Args:
        proc: JobProcess实例
    """
    logger.info("正在预热翻译模型和连接...")
    # 这里可以添加模型预加载代码
    # 例如预加载Silero VAD模型等

def main():
    """
    主函数 - 使用LiveKit CLI启动Worker
    """
    # 检查必要的环境变量
    required_env_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY", 
        "LIVEKIT_API_SECRET",
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY",
        "CARTESIA_API_KEY"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {missing_vars}")
        sys.exit(1)
    
    logger.info("LiveKit 多语言翻译代理启动中...")
    logger.info(f"支持的语言: {', '.join([f'{code}({info['name']})' for code, info in LANGUAGE_CONFIG.items()])}")
    logger.info(f"支持的房间: {', '.join(ROOM_LANGUAGE_MAP.keys())}")
    
    # 配置Worker选项
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        num_idle_processes=1,  # 控制空闲进程数量
    )
    
    # 运行Agent Worker
    cli.run_app(opts)

if __name__ == "__main__":
    main() 
