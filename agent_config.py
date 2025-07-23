#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent配置 - 构建多语言翻译代理
符合LiveKit Agents 1.1.7 API规范
"""

import os
import logging
import time
import uuid
from livekit.agents import Agent, AgentSession, llm
from livekit.plugins import deepgram, cartesia, silero
from typing import Dict, Any, Tuple, AsyncIterator
from groq import Groq
import asyncio

# 配置日志
logger = logging.getLogger("agent-config")

# 导入调试功能
try:
    from debug_integration import (
        debug_audio_frame, debug_transcription, debug_translation, 
        debug_tts_request, debug_audio_publish, debug_error, debug_warning,
        flow_debugger, debug_function
    )
    DEBUG_ENABLED = True
    logger.info("✅ 调试功能已启用")
except ImportError:
    # 如果调试模块不存在，创建空的调试函数
    DEBUG_ENABLED = False
    def debug_audio_frame(*args, **kwargs): pass
    def debug_transcription(*args, **kwargs): pass
    def debug_translation(*args, **kwargs): pass
    def debug_tts_request(*args, **kwargs): pass
    def debug_audio_publish(*args, **kwargs): pass
    def debug_error(*args, **kwargs): pass
    def debug_warning(*args, **kwargs): pass
    def debug_function(name): 
        def decorator(func): return func
        return decorator
    logger.warning("⚠️ 调试功能未启用（debug_integration.py 不存在）")

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

class TTSWithRetry:
    """
    TTS包装器，添加重试机制和错误处理
    """
    
    def __init__(self, base_tts, max_retries: int = 3):
        self.base_tts = base_tts
        self.max_retries = max_retries
        logger.info(f"🔄 TTS重试包装器初始化 - 最大重试次数: {max_retries}")
    
    async def synthesize(self, text: str, *args, **kwargs):
        """
        合成语音，带重试机制
        """
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                logger.debug(f"🔊 TTS合成尝试 {retry_count + 1}/{self.max_retries}: '{text[:50]}...'")
                result = await self.base_tts.synthesize(text, *args, **kwargs)
                
                if retry_count > 0:
                    logger.info(f"✅ TTS合成成功 (重试 {retry_count} 次)")
                
                return result
                
            except Exception as e:
                retry_count += 1
                last_error = e
                logger.warning(f"⚠️ TTS合成失败 (尝试 {retry_count}/{self.max_retries}): {e}")
                
                if retry_count >= self.max_retries:
                    logger.error(f"❌ TTS合成最终失败: {last_error}")
                    raise last_error
                
                # 指数退避
                await asyncio.sleep(0.5 * retry_count)
        
        raise last_error
    
    def __getattr__(self, name):
        """代理所有其他方法到原始TTS"""
        return getattr(self.base_tts, name)

class CustomGroqLLM(llm.LLM):
    """
    自定义Groq LLM实现，使用官方groq客户端
    支持流式翻译片段回调
    """
    
    def __init__(self, model: str = "llama3-8b-8192"):
        super().__init__()
        self._model = model
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self._stream_callback = None
        logger.info(f"🧠 初始化官方Groq客户端 - 模型: {model}")
    
    def set_stream_callback(self, callback):
        """设置流式翻译片段回调函数"""
        self._stream_callback = callback
        logger.info("✅ 已设置Groq LLM流式回调")
    
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
        
        stream = CustomGroqLLMStream(
            llm_instance=self,
            client=self._client,
            model=self._model,
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature or 0.2,  # 降低默认temperature
            conn_options=conn_options,
        )
        
        # 传递流式回调
        if self._stream_callback:
            stream.set_stream_callback(self._stream_callback)
        
        return stream

class CustomGroqLLMStream(llm.LLMStream):
    """
    自定义Groq LLM流实现
    实现LiveKit Agents 1.1.7 LLMStream抽象方法
    支持实时流式翻译片段推送
    """
    
    def __init__(
        self,
        llm_instance: llm.LLM,
        client: Groq,
        model: str,
        chat_ctx: llm.ChatContext,
        tools: list | None = None,
        tool_choice: str | None = None,
        temperature: float = 0.2,  # 降低temperature提高翻译一致性
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
        self._stream_callback = None  # 用于实时推送翻译片段
    
    def set_stream_callback(self, callback):
        """设置流式翻译片段回调函数"""
        self._stream_callback = callback
        
    async def push_event(self, chunk: llm.ChatChunk) -> None:
        """
        将ChatChunk推入LiveKit事件队列
        这是LiveKit框架要求的方法，用于处理流式响应
        """
        try:
            # LiveKit LLMStream 基类通常使用 _event_aiter 或 _event_ch 来管理事件
            # 我们需要检查多种可能的事件通道名称
            event_channel = None
            
            # 尝试找到正确的事件通道
            for attr_name in ['_event_ch', '_event_queue', '_event_aiter', '_events']:
                if hasattr(self, attr_name):
                    event_channel = getattr(self, attr_name)
                    if event_channel is not None:
                        logger.debug(f"🔍 找到事件通道: {attr_name}")
                        break
            
            if event_channel is not None:
                # 检查事件通道是否有 put 方法（队列类型）
                if hasattr(event_channel, 'put'):
                    await event_channel.put(chunk)
                    logger.debug(f"✅ ChatChunk已推入事件队列")
                # 检查是否有 send 方法（通道类型）
                elif hasattr(event_channel, 'send'):
                    await event_channel.send(chunk)
                    logger.debug(f"✅ ChatChunk已发送到事件通道")
                else:
                    logger.warning(f"⚠️ 事件通道 {type(event_channel)} 没有支持的方法")
            else:
                # 最后尝试调用父类的 push_event 方法（如果存在）
                try:
                    # 获取父类方法
                    super_class = super()
                    if hasattr(super_class, 'push_event'):
                        await super_class.push_event(chunk)
                        logger.debug(f"✅ 使用父类push_event推送ChatChunk")
                    else:
                        # 如果没有找到任何方法，记录警告但不抛出错误
                        logger.warning("⚠️ 无法找到事件通道，但ChatChunk已创建成功")
                except Exception as parent_error:
                    logger.warning(f"⚠️ 调用父类push_event失败: {parent_error}")
                    
        except Exception as e:
            logger.error(f"❌ push_event失败: {e}")
            # 不要抛出错误，以免中断整个流程
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
        
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
                        # 正确处理content格式
                        content = msg.content
                        
                        # 如果content是列表，使用join合并
                        if isinstance(content, list):
                            content = ''.join(str(item) for item in content if item is not None)
                        elif not isinstance(content, str):
                            # 如果不是字符串也不是列表，转换为字符串
                            content = str(content) if content is not None else ""
                        
                        # 确保content不为空
                        if content and content.strip():
                            messages.append({
                                "role": str(msg.role),  # 确保role也是字符串
                                "content": content.strip()  # 去除前后空格
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
                        content = msg['content']
                        
                        # 正确处理content格式（二次验证）
                        if isinstance(content, list):
                            content = ''.join(str(item) for item in content if item is not None)
                        elif not isinstance(content, str):
                            content = str(content) if content is not None else ""
                        
                        # 确保content不为空字符串
                        if content and content.strip():
                            validated_messages.append({
                                "role": role,
                                "content": content.strip()
                            })
                            logger.debug(f"✅ 消息 {i} 验证通过: role={role}, content_length={len(content)} chars")
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
            
            # 无条件确保系统指令存在 - 修复问题1
            has_system_message = any(msg.get('role') == 'system' for msg in validated_messages)
            if not has_system_message:
                validated_messages.insert(0, {
                    "role": "system",
                    "content": "你是一个专业的实时翻译助手，将中文翻译成目标语言。"
                })
                
            messages = validated_messages
            
            logger.info(f"🧠 发送请求到Groq: {len(messages)} 条消息")
            if messages:
                logger.info(f"🧠 最后消息内容: '{messages[-1]['content'][:100]}...'")
                # 调试：打印所有消息的详细格式
                for i, msg in enumerate(messages):
                    content_preview = msg.get('content', '')[:50] + ('...' if len(msg.get('content', '')) > 50 else '')
                    logger.info(f"🔍 消息 {i}: role={msg.get('role', None)}, content=\"{content_preview}\" ({len(msg.get('content', ''))} chars)")
                    
                # 特别检查用户消息的格式
                user_messages = [msg for msg in messages if msg.get('role') == 'user']
                if user_messages:
                    last_user_msg = user_messages[-1]
                    logger.info(f"🎯 最后用户消息完整内容: \"{last_user_msg['content']}\"")
            
            # 准备API调用参数 - 优化翻译质量和响应速度
            api_params = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,  # 已调整为0.2
                "max_tokens": 2048,  # 增加token限制
                "stream": True,  # 启用流式模式
                "top_p": 0.9,  # 添加top_p参数提高翻译质量
                "frequency_penalty": 0.1,  # 减少重复内容
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
            
            # 调用官方Groq客户端流式API - 添加重试机制
            logger.info(f"📡 调用Groq流式API - 模型: {self._model}")
            
            max_retries = 3
            retry_count = 0
            stream = None
            
            while retry_count < max_retries:
                try:
                    stream = self._client.chat.completions.create(**api_params)
                    break
                except Exception as api_error:
                    retry_count += 1
                    logger.warning(f"⚠️ Groq API调用失败 (尝试 {retry_count}/{max_retries}): {api_error}")
                    if retry_count >= max_retries:
                        logger.error(f"❌ Groq API调用最终失败: {api_error}")
                        raise
                    await asyncio.sleep(0.5 * retry_count)  # 指数退避
            
            # 处理流式响应 - 修复重复累积问题
            full_content = ""
            for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and choice.delta:
                        # 处理流式delta内容
                        delta_content = choice.delta.content or ""
                        
                        if delta_content:
                            # 修复：只累积一次，避免重复
                            full_content += delta_content
                            logger.debug(f"🔄 Groq流式片段: '{delta_content}' (累积长度: {len(full_content)})")
                            
                            # 调试：记录翻译片段
                            if DEBUG_ENABLED:
                                debug_translation(delta_content, "zh", "target")
                            
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
                                
                                # 创建完整的ChatChunk，包含所有必需字段
                                chunk_id = getattr(chunk, 'id', f"chatcmpl-{str(uuid.uuid4())}")
                                chat_chunk = llm.ChatChunk(
                                    id=chunk_id,
                                    object="chat.completion.chunk",
                                    created=int(time.time()),
                                    model=self._model,
                                    choices=choices
                                )
                                
                                # 使用自定义的push_event方法推送事件
                                await self.push_event(chat_chunk)
                                logger.debug(f"✅ ChatChunk推送成功: ID={chunk_id}, 内容: '{delta_content}'")
                                
                                # 如果有流式回调，立即推送翻译片段
                                if self._stream_callback:
                                    try:
                                        await self._stream_callback(delta_content, is_final=False)
                                    except Exception as callback_error:
                                        logger.warning(f"⚠️ 流式回调失败: {callback_error}")
                            except Exception as chunk_error:
                                logger.error(f"❌ 创建ChatChunk失败: {chunk_error}")
                                debug_error(f"创建ChatChunk失败: {chunk_error}", "CustomGroqLLMStream")
                                import traceback
                                logger.error(f"错误详情:\n{traceback.format_exc()}")
                                # 继续处理下一个chunk，不中断整个流程
            
            logger.info(f"🌍 Groq完整翻译结果: '{full_content}'")
            
            # 发送最终完整翻译结果
            if self._stream_callback and full_content.strip():
                try:
                    await self._stream_callback(full_content, is_final=True)
                except Exception as callback_error:
                    logger.warning(f"⚠️ 最终结果回调失败: {callback_error}")
            
            # 调试：记录完整翻译结果
            if DEBUG_ENABLED and full_content.strip():
                debug_translation(full_content, "zh", "target")
            
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
            model="nova-2",  # 使用nova-2模型
            language="zh-CN",  # 明确指定简体中文
            interim_results=True,  # 启用中间结果
            smart_format=True,  # 启用智能格式化
            punctuate=True,  # 启用标点符号
        )
        logger.info(f"✅ STT初始化成功 - 模型: nova-2, 语言: zh-CN")
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
    
    # TTS配置 - 设置为目标语言，添加重试机制
    try:
        logger.info(f"🔊 初始化TTS (Cartesia {language_name})...")
        base_tts = cartesia.TTS(
            model="sonic-multilingual",  # 使用多语言模型
            voice=language_info["voice_id"],
        )
        
        # 包装TTS以添加重试机制
        tts = TTSWithRetry(base_tts, max_retries=3)
        logger.info(f"✅ TTS初始化成功 - 模型: sonic-multilingual, 语音ID: {language_info['voice_id']}")
    except Exception as e:
        logger.error(f"❌ TTS初始化失败: {e}")
        raise
    
    logger.info(f"🎉 {language_name} 翻译组件创建完成!")
    return vad, stt, llm_instance, tts

def create_translation_agent(language: str) -> Agent:
    """
    为指定语言创建翻译Agent（仅包含指令，不包含组件）
    符合LiveKit官方文档规范
    
    Args:
        language: 目标语言代码
        
    Returns:
        配置好的Agent实例
    """
    if language not in LANGUAGE_CONFIG:
        raise ValueError(f"不支持的语言代码: {language}，支持的语言: {list(LANGUAGE_CONFIG.keys())}")
    
    language_name = LANGUAGE_CONFIG[language]["name"]
    logger.info(f"🤖 创建 {language_name} Agent框架...")
    
    # 创建Agent - 只包含指令，组件由AgentSession管理
    agent = Agent(
        instructions=get_translation_instructions(language)
    )
    
    logger.info(f"✅ {language_name} Agent创建成功")
    return agent 
