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
            llm_instance=self,
            client=self._client,
            model=self._model,
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature or 0.7,
            conn_options=conn_options,
        )

class CustomGroqLLMStream(llm.LLMStream):
    """
    自定义Groq LLM流实现
    实现LiveKit Agents 1.1.7 LLMStream抽象方法
    """
    
    def __init__(
        self,
        llm_instance: llm.LLM,
        client: Groq,
        model: str,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.7,
        conn_options: dict | None = None,
    ):
        super().__init__(
            llm=llm_instance, 
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or {}
        )
        self._client = client
        self._model = model
        self._temperature = temperature
        self._tools = tools
        self._tool_choice = tool_choice
        self._conn_options = conn_options
        
    async def _run(self) -> None:
        """
        实现LiveKit Agents 1.1.7要求的_run抽象方法
        使用普通async def函数，不使用yield，通过父类方法处理响应
        """
        try:
            # 转换ChatContext为Groq API格式
            messages = []
            
            # 在 LiveKit Agents 1.1.7 中，ChatContext 可能不直接有 messages 属性
            # 我们需要检查如何正确访问消息历史
            try:
                # 尝试获取消息历史 - 使用不同的方法
                if hasattr(self._chat_ctx, 'messages'):
                    # 如果有直接的 messages 属性
                    chat_messages = self._chat_ctx.messages
                elif hasattr(self._chat_ctx, 'items'):
                    # 如果使用 items 属性
                    chat_messages = self._chat_ctx.items
                else:
                    # 如果没有消息历史，创建基本的系统消息
                    logger.warning("⚠️ ChatContext 没有找到消息历史，使用默认系统消息")
                    chat_messages = []
                
                # 转换消息格式 - 确保content始终是字符串
                for msg in chat_messages:
                    if hasattr(msg, 'role') and hasattr(msg, 'content'):
                        # 确保content是字符串类型
                        content = msg.content
                        if not isinstance(content, str):
                            content = str(content) if content is not None else ""
                        
                        # 确保content不为空
                        if content.strip():
                            messages.append({
                                "role": str(msg.role),  # 确保role也是字符串
                                "content": content
                            })
                
                # 如果没有消息，添加一个基本的系统提示
                if not messages:
                    messages.append({
                        "role": "system",
                        "content": "你是一个专业的实时翻译助手，将中文翻译成目标语言。"
                    })
                    
            except Exception as ctx_error:
                logger.warning(f"⚠️ 访问ChatContext失败: {ctx_error}, 使用默认消息")
                messages = [{
                    "role": "system",
                    "content": "你是一个专业的实时翻译助手，将中文翻译成目标语言。"
                }]
                
            # 验证所有消息格式 - 确保符合Groq API要求
            validated_messages = []
            for i, msg in enumerate(messages):
                try:
                    # 验证每个消息的格式
                    if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                        role = str(msg['role'])
                        content = str(msg['content']) if msg['content'] is not None else ""
                        
                        # 确保content不为空字符串
                        if content.strip():
                            validated_messages.append({
                                "role": role,
                                "content": content
                            })
                        else:
                            logger.warning(f"⚠️ 消息 {i} 的content为空，跳过")
                    else:
                        logger.warning(f"⚠️ 消息 {i} 格式无效，跳过: {msg}")
                except Exception as msg_error:
                    logger.error(f"❌ 验证消息 {i} 时出错: {msg_error}")
                    
            # 如果验证后没有有效消息，使用默认消息
            if not validated_messages:
                validated_messages = [{
                    "role": "system",
                    "content": "你是一个专业的实时翻译助手，将中文翻译成目标语言。"
                }]
                
            messages = validated_messages
            
            logger.info(f"🧠 发送请求到Groq: {len(messages)} 条消息")
            if messages:
                logger.info(f"🧠 最后消息内容: '{str(messages[-1]['content'])[:100]}...'")
                # 调试：打印所有消息的类型和格式
                for i, msg in enumerate(messages):
                    logger.debug(f"🔍 消息 {i}: role={type(msg.get('role', None))}({msg.get('role', None)}), content={type(msg.get('content', None))}({len(str(msg.get('content', '')))} chars)")
            
            # 准备API调用参数
            api_params = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,
                "max_tokens": 1000,
                "stream": True,  # 启用流式模式
            }
            
            # 调试：确保API参数格式正确
            logger.debug(f"🔍 API参数: model={api_params['model']}, messages_count={len(api_params['messages'])}, temp={api_params['temperature']}")
            
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
                            
                            # 创建符合LiveKit格式的ChatChunk并推送事件
                            try:
                                # 使用字典格式构造choices，符合OpenAI/Groq风格的响应格式
                                choices = [
                                    {
                                        "delta": {
                                            "content": delta_content,
                                            "role": "assistant"
                                        },
                                        "index": 0,
                                        "finish_reason": None
                                    }
                                ]
                                
                                # LiveKit Agents 1.1.7 需要 id 字段而不是 request_id
                                chat_chunk = llm.ChatChunk(
                                    id=getattr(chunk, 'id', ''),
                                    choices=choices
                                )
                                
                                # 使用父类的方法推送事件而不是yield
                                await self.push_event(chat_chunk)
                            except Exception as chunk_error:
                                logger.error(f"❌ 创建ChatChunk失败: {chunk_error}")
                                # 继续处理下一个chunk，不中断整个流程
            
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
