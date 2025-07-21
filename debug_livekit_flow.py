#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit 语音翻译流水线调试脚本
追踪每个关键节点的状态和数据流
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger("livekit-debug")

# 设置不同组件的日志级别
logging.getLogger("livekit").setLevel(logging.DEBUG)
logging.getLogger("websockets").setLevel(logging.INFO)

class LiveKitFlowDebugger:
    """LiveKit 语音翻译流水线调试器"""
    
    def __init__(self):
        self.stats = {
            "room_connection": False,
            "participant_joined": False,
            "microphone_enabled": False,
            "audio_track_received": False,
            "audio_frames_count": 0,
            "deepgram_messages_sent": 0,
            "transcriptions_received": 0,
            "translations_generated": 0,
            "tts_requests": 0,
            "audio_tracks_published": 0,
            "subtitle_broadcasts": 0,
        }
        self.start_time = time.time()
        
    def log_event(self, event_type: str, details: Dict[str, Any] = None):
        """记录事件和统计信息"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        elapsed = time.time() - self.start_time
        
        if details is None:
            details = {}
        
        # 更新统计信息
        if event_type == "audio_frame_received":
            self.stats["audio_frames_count"] += 1
        elif event_type == "deepgram_message_sent":
            self.stats["deepgram_messages_sent"] += 1
        elif event_type == "transcription_received":
            self.stats["transcriptions_received"] += 1
        elif event_type == "translation_generated":
            self.stats["translations_generated"] += 1
        elif event_type == "tts_request":
            self.stats["tts_requests"] += 1
        elif event_type == "audio_track_published":
            self.stats["audio_tracks_published"] += 1
        elif event_type == "subtitle_broadcast":
            self.stats["subtitle_broadcasts"] += 1
        
        # 格式化日志输出
        event_emoji = {
            "room_connection": "🏠",
            "participant_joined": "👤",
            "microphone_enabled": "🎤",
            "audio_track_received": "🎵",
            "audio_frame_received": "🔈",
            "deepgram_message_sent": "📤",
            "transcription_received": "📝",
            "translation_generated": "🌍",
            "tts_request": "🔊",
            "audio_track_published": "📢",
            "subtitle_broadcast": "💬",
            "error": "❌",
            "warning": "⚠️",
            "success": "✅"
        }.get(event_type, "🔍")
        
        # 构建详细信息字符串
        details_str = ""
        if details:
            details_list = []
            for key, value in details.items():
                if isinstance(value, str) and len(value) > 50:
                    value = value[:50] + "..."
                details_list.append(f"{key}={value}")
            details_str = f" | {', '.join(details_list)}"
        
        logger.info(f"{event_emoji} [{elapsed:6.2f}s] {event_type.upper()}{details_str}")
        
        # 每10秒输出一次统计信息
        if int(elapsed) % 10 == 0 and int(elapsed) > 0:
            self.print_stats()
    
    def print_stats(self):
        """打印当前统计信息"""
        logger.info("📊 === 流水线统计信息 ===")
        for key, value in self.stats.items():
            status = "✅" if value > 0 or (isinstance(value, bool) and value) else "❌"
            logger.info(f"📊 {status} {key}: {value}")
        logger.info("📊 ========================")

# 全局调试器实例
debugger = LiveKitFlowDebugger()

# 猴子补丁：为 LiveKit 组件添加调试日志
def patch_livekit_logging():
    """为 LiveKit 组件添加调试日志"""
    try:
        from livekit.agents import Agent, AgentSession
        from livekit import rtc
        
        # 保存原始方法
        original_agent_start = Agent.start if hasattr(Agent, 'start') else None
        original_session_init = AgentSession.__init__ if hasattr(AgentSession, '__init__') else None
        
        # 包装 Agent.start 方法
        def debug_agent_start(self, *args, **kwargs):
            debugger.log_event("agent_start", {"args_count": len(args), "kwargs": list(kwargs.keys())})
            if original_agent_start:
                return original_agent_start(self, *args, **kwargs)
        
        # 包装 AgentSession.__init__ 方法
        def debug_session_init(self, *args, **kwargs):
            debugger.log_event("session_init", {"session_id": getattr(self, 'id', 'unknown')})
            if original_session_init:
                return original_session_init(self, *args, **kwargs)
        
        # 应用补丁
        if original_agent_start:
            Agent.start = debug_agent_start
        if original_session_init:
            AgentSession.__init__ = debug_session_init
            
        logger.info("✅ LiveKit 调试补丁已应用")
        
    except ImportError as e:
        logger.warning(f"⚠️ 无法导入 LiveKit 组件进行调试补丁: {e}")

def create_debug_agent_session():
    """创建带调试功能的 Agent Session"""
    
    class DebugAgentSession:
        """带调试功能的 Agent Session 包装器"""
        
        def __init__(self, original_session):
            self.original_session = original_session
            self._setup_event_handlers()
        
        def _setup_event_handlers(self):
            """设置事件处理器"""
            
            @self.original_session.on("participant_connected")
            def on_participant_connected(participant):
                debugger.log_event("participant_joined", {
                    "participant_id": participant.identity,
                    "name": getattr(participant, 'name', 'unknown')
                })
                debugger.stats["participant_joined"] = True
            
            @self.original_session.on("track_subscribed")
            def on_track_subscribed(track, publication, participant):
                debugger.log_event("audio_track_received", {
                    "track_id": track.sid,
                    "kind": track.kind,
                    "participant": participant.identity
                })
                debugger.stats["audio_track_received"] = True
                
                # 如果是音频轨道，设置音频帧处理器
                if track.kind == "audio":
                    self._setup_audio_frame_handler(track)
            
            @self.original_session.on("track_unsubscribed")
            def on_track_unsubscribed(track, publication, participant):
                debugger.log_event("track_unsubscribed", {
                    "track_id": track.sid,
                    "participant": participant.identity
                })
        
        def _setup_audio_frame_handler(self, audio_track):
            """设置音频帧处理器"""
            
            async def on_audio_frame(frame):
                frame_size = len(frame.data) if hasattr(frame, 'data') else 0
                debugger.log_event("audio_frame_received", {
                    "frame_size": frame_size,
                    "sample_rate": getattr(frame, 'sample_rate', 'unknown'),
                    "channels": getattr(frame, 'channels', 'unknown')
                })
                
                # 检查是否有音频数据
                if frame_size > 0:
                    debugger.stats["microphone_enabled"] = True
                    logger.debug(f"🔈 音频帧详情: 大小={frame_size}字节")
                else:
                    logger.warning("⚠️ 收到空音频帧")
            
            # 注册音频帧处理器
            if hasattr(audio_track, 'on'):
                audio_track.on("frame", on_audio_frame)
            else:
                logger.warning("⚠️ 音频轨道不支持帧事件监听")
        
        def __getattr__(self, name):
            """代理所有其他方法到原始 session"""
            return getattr(self.original_session, name)
    
    return DebugAgentSession

def create_debug_deepgram_wrapper():
    """创建带调试功能的 Deepgram 包装器"""
    
    class DebugDeepgramSTT:
        """带调试功能的 Deepgram STT 包装器"""
        
        def __init__(self, original_stt):
            self.original_stt = original_stt
            self._setup_debug_handlers()
        
        def _setup_debug_handlers(self):
            """设置调试处理器"""
            
            # 包装 WebSocket 发送方法
            if hasattr(self.original_stt, '_websocket'):
                original_send = getattr(self.original_stt._websocket, 'send', None)
                
                async def debug_send(data):
                    data_size = len(data) if isinstance(data, (bytes, str)) else 0
                    debugger.log_event("deepgram_message_sent", {
                        "data_type": type(data).__name__,
                        "data_size": data_size
                    })
                    
                    if original_send:
                        return await original_send(data)
                
                if original_send:
                    self.original_stt._websocket.send = debug_send
            
            # 包装转写结果处理
            original_on_message = getattr(self.original_stt, '_on_message', None)
            
            def debug_on_message(message):
                try:
                    if isinstance(message, str):
                        data = json.loads(message)
                        
                        # 检查是否是转写结果
                        if "channel" in data:
                            alternatives = data.get("channel", {}).get("alternatives", [])
                            if alternatives:
                                transcript = alternatives[0].get("transcript", "")
                                is_final = data.get("is_final", False)
                                confidence = alternatives[0].get("confidence", 0)
                                
                                debugger.log_event("transcription_received", {
                                    "transcript": transcript,
                                    "is_final": is_final,
                                    "confidence": confidence
                                })
                                
                                if transcript.strip():
                                    logger.info(f"📝 转写内容: '{transcript}' (最终: {is_final}, 置信度: {confidence:.2f})")
                
                except Exception as e:
                    logger.error(f"❌ 解析 Deepgram 消息失败: {e}")
                
                if original_on_message:
                    return original_on_message(message)
            
            if original_on_message:
                self.original_stt._on_message = debug_on_message
        
        def __getattr__(self, name):
            """代理所有其他方法到原始 STT"""
            return getattr(self.original_stt, name)
    
    return DebugDeepgramSTT

def create_debug_llm_wrapper():
    """创建带调试功能的 LLM 包装器"""
    
    class DebugLLMWrapper:
        """带调试功能的 LLM 包装器"""
        
        def __init__(self, original_llm):
            self.original_llm = original_llm
        
        async def chat(self, *args, **kwargs):
            """包装 chat 方法"""
            debugger.log_event("llm_chat_request", {
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys())
            })
            
            # 调用原始方法
            result = await self.original_llm.chat(*args, **kwargs)
            
            # 包装结果流
            return DebugLLMStream(result)
        
        def __getattr__(self, name):
            """代理所有其他方法"""
            return getattr(self.original_llm, name)
    
    class DebugLLMStream:
        """带调试功能的 LLM Stream 包装器"""
        
        def __init__(self, original_stream):
            self.original_stream = original_stream
        
        async def __aiter__(self):
            """异步迭代器"""
            full_response = ""
            async for chunk in self.original_stream:
                # 记录 LLM 响应
                content = getattr(chunk, 'content', '')
                if content:
                    full_response += content
                    debugger.log_event("llm_chunk_received", {
                        "chunk_content": content[:50],
                        "total_length": len(full_response)
                    })
                
                yield chunk
            
            # 记录完整翻译结果
            if full_response:
                debugger.log_event("translation_generated", {
                    "translation": full_response[:100],
                    "length": len(full_response)
                })
                logger.info(f"🌍 完整翻译: '{full_response}'")
        
        def __getattr__(self, name):
            """代理所有其他方法"""
            return getattr(self.original_stream, name)
    
    return DebugLLMWrapper

def create_debug_tts_wrapper():
    """创建带调试功能的 TTS 包装器"""
    
    class DebugTTSWrapper:
        """带调试功能的 TTS 包装器"""
        
        def __init__(self, original_tts):
            self.original_tts = original_tts
        
        async def synthesize(self, text, *args, **kwargs):
            """包装合成方法"""
            debugger.log_event("tts_request", {
                "text": text[:50],
                "text_length": len(text),
                "args_count": len(args)
            })
            logger.info(f"🔊 TTS 请求: '{text}'")
            
            # 调用原始方法
            result = await self.original_tts.synthesize(text, *args, **kwargs)
            
            # 记录合成结果
            if result:
                debugger.log_event("tts_completed", {
                    "result_type": type(result).__name__,
                    "has_audio": hasattr(result, 'audio')
                })
                logger.info("✅ TTS 合成完成")
            
            return result
        
        def __getattr__(self, name):
            """代理所有其他方法"""
            return getattr(self.original_tts, name)
    
    return DebugTTSWrapper

def create_debug_room_wrapper():
    """创建带调试功能的 Room 包装器"""
    
    class DebugRoomWrapper:
        """带调试功能的 Room 包装器"""
        
        def __init__(self, original_room):
            self.original_room = original_room
            self._setup_room_handlers()
        
        def _setup_room_handlers(self):
            """设置房间事件处理器"""
            
            @self.original_room.on("connected")
            def on_connected():
                debugger.log_event("room_connection", {"status": "connected"})
                debugger.stats["room_connection"] = True
                logger.info("✅ 成功连接到 LiveKit 房间")
            
            @self.original_room.on("disconnected")
            def on_disconnected():
                debugger.log_event("room_connection", {"status": "disconnected"})
                debugger.stats["room_connection"] = False
                logger.warning("⚠️ 与 LiveKit 房间断开连接")
            
            @self.original_room.on("track_published")
            def on_track_published(publication, participant):
                debugger.log_event("audio_track_published", {
                    "track_id": publication.sid,
                    "kind": publication.kind,
                    "participant": participant.identity
                })
                logger.info(f"📢 发布音频轨道: {publication.kind}")
            
            @self.original_room.on("data_received")
            def on_data_received(data, participant):
                try:
                    # 尝试解析字幕数据
                    if isinstance(data, bytes):
                        data_str = data.decode('utf-8')
                        subtitle_data = json.loads(data_str)
                        
                        debugger.log_event("subtitle_broadcast", {
                            "subtitle": subtitle_data.get("text", "")[:50],
                            "participant": participant.identity
                        })
                        logger.info(f"💬 收到字幕广播: '{subtitle_data.get('text', '')}'")
                        
                except Exception as e:
                    logger.debug(f"🔍 收到数据（非字幕）: {len(data)} bytes")
        
        async def publish_track(self, track, *args, **kwargs):
            """包装发布轨道方法"""
            track_info = {
                "track_type": type(track).__name__,
                "track_kind": getattr(track, 'kind', 'unknown')
            }
            
            debugger.log_event("track_publish_attempt", track_info)
            logger.info(f"📤 尝试发布轨道: {track_info}")
            
            # 调用原始方法
            result = await self.original_room.publish_track(track, *args, **kwargs)
            
            debugger.log_event("track_publish_success", track_info)
            logger.info("✅ 轨道发布成功")
            
            return result
        
        def __getattr__(self, name):
            """代理所有其他方法"""
            return getattr(self.original_room, name)
    
    return DebugRoomWrapper

def apply_debug_patches():
    """应用所有调试补丁"""
    logger.info("🔧 正在应用调试补丁...")
    
    try:
        # 应用 LiveKit 调试补丁
        patch_livekit_logging()
        
        # 在这里可以添加更多补丁
        logger.info("✅ 所有调试补丁已应用")
        
    except Exception as e:
        logger.error(f"❌ 应用调试补丁失败: {e}")

def start_flow_monitoring():
    """启动流水线监控"""
    logger.info("🚀 开始 LiveKit 语音翻译流水线调试监控")
    logger.info("📊 监控以下关键事件:")
    logger.info("   🏠 房间连接状态")
    logger.info("   👤 参与者加入/离开")
    logger.info("   🎤 麦克风权限和音频采集")
    logger.info("   🔈 音频帧接收和处理")
    logger.info("   📤 Deepgram WebSocket 通信")
    logger.info("   📝 语音转写结果")
    logger.info("   🌍 LLM 翻译生成")
    logger.info("   🔊 TTS 语音合成")
    logger.info("   📢 音频轨道发布")
    logger.info("   💬 字幕数据广播")
    
    # 应用调试补丁
    apply_debug_patches()
    
    # 启动统计信息定期输出
    async def periodic_stats():
        while True:
            await asyncio.sleep(30)  # 每30秒输出一次统计
            debugger.print_stats()
    
    # 在后台运行统计输出
    asyncio.create_task(periodic_stats())

if __name__ == "__main__":
    # 如果直接运行此脚本，启动监控
    start_flow_monitoring()
    
    # 保持脚本运行
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 调试监控已停止")
        debugger.print_stats() 