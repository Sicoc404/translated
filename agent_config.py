#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent配置 - 构建多语言翻译代理
符合LiveKit Agents 1.1.7 API规范
"""

import os
import logging
from livekit.agents import Agent, AgentSession, llm
from livekit.plugins import deepgram, cartesia, silero
from typing import Dict, Any, Tuple, AsyncIterator
from groq import Groq
import asyncio

# 配置日志
logger = logging.getLogger("agent-config")

# 语言配置
LANGUAGE_CONFIG = {
    "ja": {
        "name": "日语",
        "voice_id": "95856005-0332-41b0-935f-352e296aa0df",  # Cartesia日语voice ID
        "deepgram_model": "nova-2",  # 使用标准nova-2模型
    },
    "ko": {
        "name": "韩语", 
        "voice_id": "7d787990-4c3a-4766-9450-8c3ac6718b13",  # Cartesia韩语voice ID
        "deepgram_model": "nova-2",  # 使用标准nova-2模型
    },
    "vi": {
        "name": "越南语",
        "voice_id": "f9836c6e-a0bd-460e-9d3c-f7299fa60f94",  # Cartesia越南语voice ID  
        "deepgram_model": "nova-2",  # 使用标准nova-2模型
    },
    "ms": {
        "name": "马来语",
        "voice_id": "7d787990-4c3a-4766-9450-8c3ac6718b13",  # 使用英语voice作为马来语
        "deepgram_model": "nova-2",  # 使用标准nova-2模型
    }
}

# 源语言配置（讲者语言）
SOURCE_LANGUAGE = "zh"  # 中文

class CustomGroqLLM(llm.LLM):
    """
    自定义Groq LLM实现，使用官方groq客户端
    """
    
    def __init__(self, model: str = "llama3-8b-8192"):
        super().__init__()
        self._model = model
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])
        logger.info(f"🧠 初始化官方Groq客户端 - 模型: {model}")
    
    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        tool_choice: str | None = None,
        conn_options: dict | None = None,
        temperature: float | None = None,
        n: int | None = None,
    ) -> "llm.LLMStream":
        """
        发送聊天请求到Groq
        支持LiveKit Agents 1.1.7的完整参数签名
        """
        logger.info(f"🧠 Groq chat调用 - tools: {len(tools) if tools else 0}, tool_choice: {tool_choice}")
        
        return CustomGroqLLMStream(
            client=self._client,
            model=self._model,
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature or 0.7,
        )

class CustomGroqLLMStream(llm.LLMStream):
    """
    自定义Groq LLM流实现
    实现LiveKit Agents 1.1.7 LLMStream抽象方法
    """
    
    def __init__(
        self,
        client: Groq,
        model: str,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.7,
    ):
        super().__init__(chat_ctx=chat_ctx)
        self._client = client
        self._model = model
        self._temperature = temperature
        self._tools = tools
        self._tool_choice = tool_choice
        
    async def _run(self) -> AsyncIterator[llm.ChatChunk]:
        """
        实现LiveKit Agents 1.1.7要求的_run抽象方法
        返回ChatChunk异步生成器用于流式响应
        """
        try:
            # 转换ChatContext为Groq API格式
            messages = []
            for msg in self._chat_ctx.messages:
                if hasattr(msg, 'role') and hasattr(msg, 'content'):
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            logger.info(f"🧠 发送请求到Groq: {len(messages)} 条消息")
            if messages:
                logger.info(f"🧠 用户输入: '{messages[-1]['content'][:100]}...'")
            
            # 准备API调用参数
            api_params = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,
                "max_tokens": 1000,
                "stream": True,  # 启用流式模式
            }
            
            # 添加tools支持（如果提供）
            if self._tools:
                logger.info(f"🔧 使用工具: {len(self._tools)} 个")
                # 注意：Groq可能不支持所有工具功能，这里先记录
                logger.warning("⚠️ Groq工具支持有限，仅用于翻译任务")
            
            if self._tool_choice:
                logger.info(f"🎯 工具选择: {self._tool_choice}")
            
            # 调用官方Groq客户端流式API
            logger.info(f"📡 调用Groq流式API - 模型: {self._model}")
            stream = self._client.chat.completions.create(**api_params)
            
            # 处理流式响应
            full_content = ""
            for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and choice.delta:
                        # 处理流式delta内容
                        delta_content = choice.delta.content or ""
                        full_content += delta_content
                        
                        if delta_content:
                            logger.debug(f"🔄 Groq流式片段: '{delta_content}'")
                            
                            # 创建符合LiveKit格式的ChatChunk
                            # 使用正确的ChatChunk构造方式
                            chat_chunk = llm.ChatChunk(
                                request_id=getattr(chunk, 'id', ''),
                                choices=[
                                    llm.Choice(
                                        delta=llm.ChoiceDelta(
                                            content=delta_content,
                                            role="assistant"
                                        )
                                    )
                                ]
                            )
                            yield chat_chunk
            
            logger.info(f"🌍 Groq完整翻译结果: '{full_content}'")
            
        except Exception as e:
            logger.error(f"❌ Groq LLM流式处理失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            raise

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
        logger.info(f"🗣️ 初始化STT (Deepgram nova-2)...")
        stt = deepgram.STT(
            model="nova-2",  # 中文模型
            language="zh",
        )
        logger.info(f"✅ STT初始化成功 - 模型: nova-2, 语言: zh")
    except Exception as e:
        logger.error(f"❌ STT初始化失败: {e}")
        raise
    
    # LLM配置 - 使用自定义Groq客户端
    try:
        logger.info(f"🧠 初始化自定义Groq LLM (llama3-8b-8192)...")
        llm_instance = CustomGroqLLM(model="llama3-8b-8192")
        logger.info(f"✅ 自定义Groq LLM初始化成功 - 模型: llama3-8b-8192")
    except Exception as e:
        logger.error(f"❌ 自定义Groq LLM初始化失败: {e}")
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
    return vad, stt, llm_instance, tts

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
