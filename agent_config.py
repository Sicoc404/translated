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
                            full_content += delta_content
                            
                            # 调试：记录翻译片段
                            if DEBUG_ENABLED and len(full_content) > 10:
                                debug_translation(full_content, "zh", "target")
                            
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
                                logger.debug(f"✅ ChatChunk推送成功: ID={chunk_id}")
                            except Exception as chunk_error:
                                logger.error(f"❌ 创建ChatChunk失败: {chunk_error}")
                                debug_error(f"创建ChatChunk失败: {chunk_error}", "CustomGroqLLMStream")
                                import traceback
                                logger.error(f"错误详情:\n{traceback.format_exc()}")
                                # 继续处理下一个chunk，不中断整个流程
            
            logger.info(f"🌍 Groq完整翻译结果: '{full_content}'")
            
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
        
        # 添加VAD调试回调
        original_detect = vad.detect
        def debug_vad_detect(*args, **kwargs):
            result = original_detect(*args, **kwargs)
            if result:
                logger.info(f"[LOG][vad] 🎤 检测到语音活动")
            return result
        vad.detect = debug_vad_detect
        
    except Exception as e:
        logger.error(f"❌ VAD初始化失败: {e}")
        raise
    
    # STT配置 - 设置为源语言（中文）
    try:
        logger.info(f"🗣️ 初始化STT (Deepgram nova-2)...")
        stt = deepgram.STT(
            model="nova-2",  # 使用nova-2模型
            language="zh",  # 使用zh而不是zh-CN
            interim_results=True,  # 启用中间结果
            smart_format=True,  # 启用智能格式化
            punctuate=True,  # 启用标点符号
        )
        logger.info(f"✅ STT初始化成功 - 模型: nova-2, 语言: zh")
        
        # 添加STT调试
        original_recognize = stt.recognize
        async def debug_stt_recognize(*args, **kwargs):
            logger.info(f"[LOG][stt] 🗣️ 开始语音识别...")
            result = await original_recognize(*args, **kwargs)
            if result and hasattr(result, 'alternatives') and result.alternatives:
                transcript = result.alternatives[0].text
                confidence = result.alternatives[0].confidence
                logger.info(f"[LOG][stt] 📝 识别结果: '{transcript}' (置信度: {confidence:.2f})")
            else:
                logger.warning(f"[LOG][stt] ⚠️ 识别结果为空")
            return result
        stt.recognize = debug_stt_recognize
        
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
        
        # 添加TTS调试
        original_synthesize = tts.synthesize
        async def debug_tts_synthesize(text, *args, **kwargs):
            logger.info(f"[LOG][tts] 🔊 开始语音合成: '{text[:50]}...'")
            result = await original_synthesize(text, *args, **kwargs)
            logger.info(f"[LOG][tts] ✅ 语音合成完成")
            return result
        tts.synthesize = debug_tts_synthesize
        
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
    
    # 添加语音处理回调
    @agent.on("user_speech_committed")
    async def on_user_speech(speech_event):
        """处理用户语音输入"""
        if speech_event.alternatives:
            transcript = speech_event.alternatives[0].text
            confidence = speech_event.alternatives[0].confidence
            logger.info(f"[LOG][speech-in] 收到用户语音: '{transcript}' (置信度: {confidence:.2f})")
            if DEBUG_ENABLED:
                debug_transcription(transcript, True, confidence)
        else:
            logger.warning(f"[LOG][speech-in] 收到空的语音事件")
    
    @agent.on("agent_speech_committed") 
    async def on_agent_speech(speech_event):
        """处理Agent语音输出"""
        if speech_event.alternatives:
            translation = speech_event.alternatives[0].text
            logger.info(f"[LOG][speech-out] Agent语音输出: '{translation}'")
            if DEBUG_ENABLED:
                debug_tts_request(translation, language)
        else:
            logger.warning(f"[LOG][speech-out] 收到空的语音输出事件")
    
    @agent.on("function_calls_finished")
    async def on_function_calls_finished(called_functions):
        """处理函数调用完成"""
        logger.info(f"[LOG][functions] 函数调用完成: {len(called_functions)} 个")
        for func_call in called_functions:
            logger.info(f"[LOG][functions] 调用函数: {func_call.function_info.name}")
    
    # 添加更多调试回调
    @agent.on("user_started_speaking")
    async def on_user_started_speaking():
        """用户开始说话"""
        logger.info(f"[LOG][speech-in] 🎤 用户开始说话...")
    
    @agent.on("user_stopped_speaking") 
    async def on_user_stopped_speaking():
        """用户停止说话"""
        logger.info(f"[LOG][speech-in] 🎤 用户停止说话")
    
    @agent.on("agent_started_speaking")
    async def on_agent_started_speaking():
        """Agent开始说话"""
        logger.info(f"[LOG][speech-out] 🔊 Agent开始语音合成...")
    
    @agent.on("agent_stopped_speaking")
    async def on_agent_stopped_speaking():
        """Agent停止说话"""
        logger.info(f"[LOG][speech-out] 🔊 Agent语音合成完成")
    
    logger.info(f"✅ {language_name} Agent框架创建成功")
    return agent 
