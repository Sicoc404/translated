#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent配置 - 构建多语言翻译代理
"""

from livekit.agents import Agent, JobContext
from livekit.plugins import deepgram, groq, cartesia, silero
from typing import Dict, Any

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
    
    return f"""
    你是一个专业的实时翻译助手。
    你的任务是将源语言（中文）内容翻译成目标语言（{language_name}）。
    
    翻译规则：
    1. 保持原文的意思和语气
    2. 使用自然流畅的表达方式
    3. 保留专业术语的准确性
    4. 只输出翻译结果，不要添加解释或原文
    5. 如果听不清或无法理解某些词语，尝试根据上下文推断
    
    请直接输出翻译结果，不要包含"翻译："等前缀。
    """

async def create_agent_session_for_language(ctx: JobContext, language: str):
    """
    在JobContext内部为指定语言创建Agent和AgentSession
    
    Args:
        ctx: JobContext实例
        language: 目标语言代码
        
    Returns:
        配置好的Agent
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_info = LANGUAGE_CONFIG[language]
    
    # 在JobContext内部创建各个组件
    # VAD（语音活动检测）- 使用Silero VAD
    vad = silero.VAD.load()
    
    # STT配置 - 设置为源语言（中文）
    stt = deepgram.STT(
        model="nova-2-zh",  # 中文模型
        language="zh",
    )
    
    # LLM配置 - 使用Groq的Llama3进行翻译
    llm = groq.LLM(
        model="llama3-8b-8192",
    )
    
    # TTS配置 - 设置为目标语言
    tts = cartesia.TTS(
        model="sonic-multilingual",  # 使用多语言模型
        voice=language_info["voice_id"],
    )
    
    # 创建Agent
    agent = Agent(
        instructions=get_translation_instructions(language),
        vad=vad,
        stt=stt, 
        llm=llm,
        tts=tts,
    )
    
    return agent 
