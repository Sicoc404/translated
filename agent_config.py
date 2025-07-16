#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent配置 - 构建多语言翻译代理
"""

from livekit.agents import AgentSession
from livekit.plugins import deepgram, groq, cartesia
from typing import Dict, Any

# 语言配置
LANGUAGE_CONFIG = {
    "ja": {
        "name": "日语",
        "voice_id": "your-japanese-voice-id",  # 替换为实际的Cartesia日语voice ID
    },
    "ko": {
        "name": "韩语",
        "voice_id": "your-korean-voice-id",  # 替换为实际的Cartesia韩语voice ID
    },
    "vi": {
        "name": "越南语",
        "voice_id": "your-vietnamese-voice-id",  # 替换为实际的Cartesia越南语voice ID
    },
    "ms": {
        "name": "马来语",
        "voice_id": "your-malay-voice-id",  # 替换为实际的Cartesia马来语voice ID
    }
}

# 源语言配置（讲者语言）
SOURCE_LANGUAGE = "zh"  # 中文

def build_agent_for(language: str) -> AgentSession:
    """
    为指定语言构建翻译代理会话
    
    Args:
        language: 目标语言代码，例如 "ja"、"ko"、"vi"、"ms"
        
    Returns:
        配置好的AgentSession实例
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_info = LANGUAGE_CONFIG.get(language, {})
    target_voice_id = language_info.get("voice_id")
    language_name = language_info.get("name", language)
    
    # 为不同语言的翻译创建提示词（仅作为注释，实际使用需通过其他方式设置）
    # 日语翻译提示词: f"""
    # 你是一个专业的实时翻译助手。
    # 你的任务是将源语言（中文）内容翻译成目标语言（日语）。
    # 
    # 翻译规则：
    # 1. 保持原文的意思和语气
    # 2. 使用自然流畅的表达方式
    # 3. 保留专业术语的准确性
    # 4. 只输出翻译结果，不要添加解释或原文
    # 5. 如果听不清或无法理解某些词语，尝试根据上下文推断
    # 
    # 请直接输出翻译结果，不要包含"翻译："等前缀。
    # """
    
    # 创建代理会话
    session = AgentSession(
        # Deepgram STT配置 - 设置为源语言（讲者语言）
        stt=deepgram.STT(
            model="nova-3",
            language=SOURCE_LANGUAGE,
            smart_format=True,
            endpointing_ms=1000  # 1秒静音后结束当前句子
        ),
        
        # Groq LLM配置 - 使用Llama3进行翻译
        # 注意：Groq插件只支持model参数，不支持system_prompt等参数
        llm=groq.LLM(
            model="llama3-8b-8192"  # 8B参数的Llama3模型
        ),
        
        # Cartesia TTS配置 - 设置为目标语言
        tts=cartesia.TTS(
            model="sonic-2",  # 使用Sonic-2模型
            voice=target_voice_id,  # 目标语言的语音ID
            language=language  # 目标语言代码
        ),
        
        # 启用VAD（语音活动检测）
        vad=True,
        
        # 设置转录选项
        transcription_options={
            "enabled": True,  # 启用字幕
            "language": language,  # 字幕语言为目标语言
        }
    )
    
    return session 
