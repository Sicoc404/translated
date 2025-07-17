#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent配置 - 构建多语言翻译代理
符合LiveKit Agents 1.1.7 API规范
"""

import logging
from livekit.agents import Agent, AgentSession
from livekit.plugins import deepgram, groq, cartesia, silero
from typing import Dict, Any, Tuple

# 配置日志
logger = logging.getLogger("agent-config")

# 语言配置
LANGUAGE_CONFIG = {
    "ja": {
        "name": "日语",
        "voice_id": "95856005-0332-41b0-935f-352e296aa0df",  # Cartesia日语voice ID
        "deepgram_model": "nova-2-ja",
    },
    "ko": {
        "name": "韩语", 
        "voice_id": "7d787990-4c3a-4766-9450-8c3ac6718b13",  # Cartesia韩语voice ID
        "deepgram_model": "nova-2-ko",
    },
    "vi": {
        "name": "越南语",
        "voice_id": "f9836c6e-a0bd-460e-9d3c-f7299fa60f94",  # Cartesia越南语voice ID  
        "deepgram_model": "nova-2-general",
    },
    "ms": {
        "name": "马来语",
        "voice_id": "7d787990-4c3a-4766-9450-8c3ac6718b13",  # 使用英语voice作为马来语
        "deepgram_model": "nova-2-general",
    }
}

# 源语言配置（讲者语言）
SOURCE_LANGUAGE = "zh"  # 中文

def get_translation_instructions(language: str) -> str:
    """
    获取指定语言的翻译指令
    
    Args:
        language: 目标语言代码
        
    Returns:
        翻译指令字符串
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_info = LANGUAGE_CONFIG.get(language, {})
    language_name = language_info.get("name", language)
    
    return f"""你是一个专业的实时翻译助手，专门将中文翻译成{language_name}。

核心职责：
1. 实时翻译中文语音到{language_name}
2. 保持翻译的准确性和自然流畅性
3. 保留原文的语气和意图

翻译规则：
- 直接输出{language_name}翻译结果，不要添加"翻译："等前缀
- 保持口语化和自然的表达方式  
- 对于专业术语保持准确性
- 如果音频不清晰，根据上下文推断最可能的意思
- 保持原文的情感色彩和语气

请始终用{language_name}回应，提供准确且自然的翻译。"""

def create_translation_components(language: str) -> Tuple[Any, Any, Any, Any]:
    """
    为指定语言创建翻译组件
    
    Args:
        language: 目标语言代码
        
    Returns:
        (vad, stt, llm, tts) 组件元组
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_info = LANGUAGE_CONFIG[language]
    language_name = language_info["name"]
    
    logger.info(f"🔧 开始创建 {language_name} 翻译组件...")
    
    # VAD组件 - 语音活动检测
    try:
        logger.info(f"🎤 初始化VAD (Silero)...")
        vad = silero.VAD.load()
        logger.info(f"✅ VAD初始化成功")
    except Exception as e:
        logger.error(f"❌ VAD初始化失败: {e}")
        raise
    
    # STT配置 - 设置为源语言（中文）
    try:
        logger.info(f"🗣️ 初始化STT (Deepgram nova-2-zh)...")
        stt = deepgram.STT(
            model="nova-2-zh",  # 中文模型
            language="zh",
        )
        logger.info(f"✅ STT初始化成功 - 模型: nova-2-zh, 语言: zh")
    except Exception as e:
        logger.error(f"❌ STT初始化失败: {e}")
        raise
    
    # LLM配置 - 使用Groq的Llama3进行翻译
    try:
        logger.info(f"🧠 初始化LLM (Groq Llama3-8b-8192)...")
        llm = groq.LLM(
            model="llama3-8b-8192",
        )
        logger.info(f"✅ LLM初始化成功 - 模型: llama3-8b-8192")
    except Exception as e:
        logger.error(f"❌ LLM初始化失败: {e}")
        raise
    
    # TTS配置 - 设置为目标语言
    try:
        logger.info(f"🔊 初始化TTS (Cartesia {language_name})...")
        tts = cartesia.TTS(
            model="sonic-multilingual",  # 使用多语言模型
            voice=language_info["voice_id"],
        )
        logger.info(f"✅ TTS初始化成功 - 模型: sonic-multilingual, 语音ID: {language_info['voice_id']}")
    except Exception as e:
        logger.error(f"❌ TTS初始化失败: {e}")
        raise
    
    logger.info(f"🎉 {language_name} 翻译组件创建完成!")
    return vad, stt, llm, tts

def create_translation_agent(language: str) -> Agent:
    """
    为指定语言创建翻译Agent（仅包含指令）
    
    Args:
        language: 目标语言代码
        
    Returns:
        配置好的Agent实例
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_name = LANGUAGE_CONFIG[language]["name"]
    logger.info(f"🤖 创建 {language_name} Agent框架...")
    
    # 创建Agent，只包含指令，不设置组件
    agent = Agent(
        instructions=get_translation_instructions(language)
    )
    
    logger.info(f"✅ {language_name} Agent框架创建成功")
    return agent 
