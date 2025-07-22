#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit 语音翻译流水线调试集成脚本
可以直接导入到现有的 agent_config.py 中使用
"""

import logging
import time
import json
from typing import Dict, Any
from datetime import datetime

# 设置调试日志
debug_logger = logging.getLogger("livekit-flow-debug")
debug_logger.setLevel(logging.INFO)

class FlowDebugger:
    """简化版流水线调试器"""
    
    def __init__(self):
        self.stats = {
            "audio_frames": 0,
            "transcriptions": 0,
            "translations": 0,
            "tts_calls": 0,
            "audio_published": 0,
        }
        self.start_time = time.time()
        self.last_activity = time.time()
    
    def log_step(self, step_name: str, details: str = "", data_size: int = 0):
        """记录流水线步骤"""
        elapsed = time.time() - self.start_time
        since_last = time.time() - self.last_activity
        self.last_activity = time.time()
        
        # 选择合适的表情符号
        emoji = {
            "audio_frame": "🔈",
            "transcription": "📝", 
            "translation": "🌍",
            "tts_request": "🔊",
            "audio_publish": "📢",
            "error": "❌",
            "warning": "⚠️"
        }.get(step_name, "🔍")
        
        # 构建日志消息
        msg_parts = [f"{emoji} [{elapsed:6.1f}s]"]
        if since_last > 0.1:  # 只显示有意义的间隔
            msg_parts.append(f"(+{since_last:.1f}s)")
        msg_parts.append(step_name.upper())
        
        if details:
            msg_parts.append(f"- {details}")
        if data_size > 0:
            msg_parts.append(f"({data_size} bytes)")
            
        debug_logger.info(" ".join(msg_parts))
        
        # 更新统计
        if step_name == "audio_frame":
            self.stats["audio_frames"] += 1
        elif step_name == "transcription":
            self.stats["transcriptions"] += 1
        elif step_name == "translation":
            self.stats["translations"] += 1
        elif step_name == "tts_request":
            self.stats["tts_calls"] += 1
        elif step_name == "audio_publish":
            self.stats["audio_published"] += 1
    
    def print_summary(self):
        """打印统计摘要 - 已禁用以减少日志噪音"""
        # 统计摘要已禁用，只在需要时手动调用
        pass

# 全局调试器实例
flow_debugger = FlowDebugger()

def debug_audio_frame(frame_data):
    """调试音频帧接收"""
    frame_size = len(frame_data) if frame_data else 0
    if frame_size > 0:
        flow_debugger.log_step("audio_frame", f"收到音频帧", frame_size)
    else:
        flow_debugger.log_step("warning", "收到空音频帧")

def debug_transcription(transcript: str, is_final: bool = False, confidence: float = 0.0):
    """调试转写结果"""
    status = "最终" if is_final else "临时"
    details = f"'{transcript[:30]}...' ({status}, 置信度: {confidence:.2f})"
    flow_debugger.log_step("transcription", details)

def debug_translation(translation: str, source_lang: str = "zh", target_lang: str = "unknown"):
    """调试翻译结果"""
    details = f"'{translation[:30]}...' ({source_lang} → {target_lang})"
    flow_debugger.log_step("translation", details)

def debug_tts_request(text: str, voice_id: str = "unknown"):
    """调试TTS请求"""
    details = f"'{text[:30]}...' (voice: {voice_id[:8]}...)"
    flow_debugger.log_step("tts_request", details)

def debug_audio_publish(audio_data, track_type: str = "audio"):
    """调试音频发布"""
    data_size = len(audio_data) if audio_data else 0
    flow_debugger.log_step("audio_publish", f"发布{track_type}轨道", data_size)

def debug_error(error_msg: str, component: str = "unknown"):
    """调试错误"""
    flow_debugger.log_step("error", f"{component}: {error_msg}")

def debug_warning(warning_msg: str, component: str = "unknown"):
    """调试警告"""
    flow_debugger.log_step("warning", f"{component}: {warning_msg}")

# 装饰器：自动调试函数调用
def debug_function(func_name: str):
    """装饰器：为函数添加调试日志"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start_time
                debug_logger.debug(f"✅ {func_name} 完成 ({elapsed:.2f}s)")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                debug_error(f"{func_name} 失败: {str(e)} ({elapsed:.2f}s)")
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                debug_logger.debug(f"✅ {func_name} 完成 ({elapsed:.2f}s)")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                debug_error(f"{func_name} 失败: {str(e)} ({elapsed:.2f}s)")
                raise
        
        # 检查是否是异步函数
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def start_debug_monitoring():
    """启动调试监控"""
    debug_logger.info("🚀 启动 LiveKit 语音翻译流水线调试")
    debug_logger.info("📊 将监控以下关键步骤:")
    debug_logger.info("   🔈 音频帧接收")
    debug_logger.info("   📝 语音转写")
    debug_logger.info("   🌍 文本翻译")
    debug_logger.info("   🔊 语音合成")
    debug_logger.info("   📢 音频发布")
    debug_logger.info("   ❌ 错误和警告")
    
    # 定期统计输出已禁用以减少日志噪音
    # 如需要统计信息，可以手动调用 get_debug_stats() 或 flow_debugger.print_summary()

def get_debug_stats():
    """获取当前调试统计"""
    return flow_debugger.stats.copy()

# 在导入时自动启动监控
start_debug_monitoring() 
