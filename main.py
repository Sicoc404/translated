#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agent翻译服务 - 专门的翻译服务
为前端提供翻译API和LiveKit Agent功能
"""

import os
import sys
import asyncio
import logging
import threading
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext, 
    WorkerOptions, 
    cli, 
    JobProcess,
    AutoSubscribe
)
from agent_config import create_translation_agent, create_translation_components, LANGUAGE_CONFIG

# 加载环境变量
load_dotenv()

# 配置日志 - 确保所有错误都输出到stdout供Render捕获
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别捕获更多信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 明确输出到stdout
        logging.StreamHandler(sys.stderr)   # 同时输出到stderr
    ]
)

# 设置所有相关logger的级别
logging.getLogger("livekit").setLevel(logging.DEBUG)
logging.getLogger("livekit.agents").setLevel(logging.DEBUG)
logging.getLogger("agent-config").setLevel(logging.DEBUG)
logger = logging.getLogger("agent-translation")

# Flask应用配置
app = Flask(__name__)

# CORS配置 - 只允许前端域名访问
CORS(app, origins=["https://translated-frontend-02q6.onrender.com"])

# 房间与语言的映射关系
ROOM_LANGUAGE_MAP = {
    "Pryme-Japanese": "ja",
    "Pryme-Korean": "ko", 
    "Pryme-Vietnamese": "vi",
    "Pryme-Malay": "ms"
}

# Agent状态管理
active_agents = {}
agent_stats = {
    "total_sessions": 0,
    "active_sessions": 0,
    "supported_languages": list(LANGUAGE_CONFIG.keys())
}

@app.route('/health', methods=['GET'])
def health():
    """健康检查端点 - Render.com监控使用"""
    return jsonify({
        "status": "ok", 
        "service": "agent-translation",
        "active_agents": len(active_agents),
        "supported_languages": agent_stats["supported_languages"]
    })

@app.route('/', methods=['GET'])
def root():
    """根路径 - 服务信息"""
    return jsonify({
        "message": "Agent Translation Service is running", 
        "status": "active",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health (GET)",
            "status": "/api/status (GET)",
            "agents": "/api/agents (GET)"
        },
        "supported_rooms": list(ROOM_LANGUAGE_MAP.keys()),
        "cors_enabled": True
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取服务状态"""
    try:
        # 检查环境变量
        required_vars = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", 
                        "DEEPGRAM_API_KEY", "GROQ_API_KEY", "CARTESIA_API_KEY"]
        
        env_status = {}
        for var in required_vars:
            env_status[var] = "configured" if os.getenv(var) else "missing"
        
        return jsonify({
            "service": "agent-translation",
            "status": "running",
            "statistics": agent_stats,
            "environment": env_status,
            "active_agents": list(active_agents.keys())
        })
        
    except Exception as e:
        logger.error(f"❌ 获取状态失败: {e}")
        return jsonify({"error": f"获取状态失败: {str(e)}"}), 500

@app.route('/api/agents', methods=['GET'])
def get_agents():
    """获取活跃的Agent信息"""
    try:
        agents_info = []
        for room_name, agent_info in active_agents.items():
            agents_info.append({
                "room": room_name,
                "language": agent_info.get("language"),
                "started_at": agent_info.get("started_at"),
                "status": "active"
            })
        
        return jsonify({
            "active_agents": agents_info,
            "total_count": len(agents_info),
            "supported_languages": LANGUAGE_CONFIG
        })
        
    except Exception as e:
        logger.error(f"❌ 获取Agent信息失败: {e}")
        return jsonify({"error": f"获取Agent信息失败: {str(e)}"}), 500

def start_flask_api():
    """在单独线程中启动Flask API服务器"""
    try:
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"🚀 启动Agent翻译API服务器 - 端口: {port}")
        logger.info(f"🌐 CORS允许域名: https://translated-frontend-02q6.onrender.com")
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Flask API服务器启动失败: {e}")

async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent入口点 - 处理翻译逻辑
    符合LiveKit官方文档规范
    
    Args:
        ctx: JobContext实例，包含房间连接信息
    """
    try:
        # 正确连接到房间，包含auto_subscribe参数
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        
        # 获取房间信息
        room_name = ctx.room.name
        logger.info(f"🏠 Agent连接到房间: {room_name}")
        logger.info(f"👥 当前房间参与者数量: {ctx.room.num_participants}")
        
        # 确定目标语言
        target_language = None
        for room_prefix, language_code in ROOM_LANGUAGE_MAP.items():
            if room_name.startswith(room_prefix):
                target_language = language_code
                break
        
        if not target_language:
            logger.error(f"❌ 不支持的房间: {room_name}")
            logger.error(f"支持的房间前缀: {list(ROOM_LANGUAGE_MAP.keys())}")
            return
        
        language_name = LANGUAGE_CONFIG[target_language]["name"]
        logger.info(f"🌍 启动 {language_name} 翻译Agent...")
        
        # 更新统计信息
        agent_stats["total_sessions"] += 1
        agent_stats["active_sessions"] += 1
        active_agents[room_name] = {
            "language": target_language,
            "language_name": language_name,
            "started_at": asyncio.get_event_loop().time()
        }
        
        # 创建翻译组件
        logger.info(f"🔧 创建 {language_name} 翻译组件...")
        vad, stt, llm, tts = create_translation_components(target_language)
        
        # 创建Agent（不包含事件监听器）
        logger.info(f"🤖 创建 {language_name} Agent...")
        agent = create_translation_agent(target_language)
        
        logger.info(f"✅ {language_name} 翻译Agent配置完成:")
        logger.info(f"  🎤 VAD: {type(vad).__name__}")
        logger.info(f"  🗣️ STT: {type(stt).__name__} (中文识别)")
        logger.info(f"  🧠 LLM: {type(llm).__name__} (Groq翻译)")
        logger.info(f"  🔊 TTS: {type(tts).__name__} ({language_name}合成)")
        
        # 正确的事件监听方式 - 使用同步回调 + asyncio.create_task
        async def handle_data_received_async(data: bytes, participant):
            """异步处理从客户端接收的数据消息"""
            try:
                message = data.decode('utf-8')
                logger.info(f"[LOG][rpc-recv] 收到数据消息: {message[:100]}...")
                
                # 尝试解析JSON消息
                try:
                    json_data = json.loads(message)
                    if json_data.get('type') == 'translation_control':
                        action = json_data.get('action')
                        logger.info(f"[LOG][rpc-recv] 翻译控制命令: {action}")
                        
                        if action == 'start':
                            logger.info(f"[LOG][rpc-recv] 启动翻译模式")
                            # 发送确认消息
                            response_data = json.dumps({
                                'type': 'translation_status',
                                'status': 'started',
                                'language': language_name,
                                'timestamp': asyncio.get_event_loop().time()
                            }).encode('utf-8')
                            await ctx.room.local_participant.publish_data(response_data)
                            logger.info(f"[LOG][subtitles-send] 翻译启动确认已发送")
                            
                        elif action == 'stop':
                            logger.info(f"[LOG][rpc-recv] 停止翻译模式")
                            # 发送确认消息
                            response_data = json.dumps({
                                'type': 'translation_status', 
                                'status': 'stopped',
                                'timestamp': asyncio.get_event_loop().time()
                            }).encode('utf-8')
                            await ctx.room.local_participant.publish_data(response_data)
                            logger.info(f"[LOG][subtitles-send] 翻译停止确认已发送")
                            
                except json.JSONDecodeError:
                    logger.warning(f"[LOG][rpc-recv] 无法解析JSON消息: {message}")
                    
            except Exception as e:
                logger.error(f"[LOG][rpc-recv] 处理数据消息失败: {e}")
        
        @ctx.room.on("data_received")
        def handle_data_received(*args, **kwargs):
            """同步回调包装器 - 使用*args动态接收参数"""
            try:
                logger.info(f"🚨 CRITICAL: data_received参数数量: {len(args)}")
                logger.info(f"🚨 CRITICAL: 参数类型: {[type(arg) for arg in args]}")
                logger.info(f"🚨 CRITICAL: kwargs: {kwargs}")
                
                # 根据参数数量动态处理
                if len(args) == 1:
                    # 单个事件对象
                    event = args[0]
                    data = event.data if hasattr(event, 'data') else event
                    participant = event.participant if hasattr(event, 'participant') else None
                elif len(args) == 2:
                    # data, participant
                    data, participant = args
                elif len(args) == 3:
                    # data, kind, participant
                    data, kind, participant = args
                else:
                    logger.error(f"❌ 未知的参数格式: {len(args)} 个参数")
                    return
                
                logger.info(f"🚨 CRITICAL: 提取的数据长度: {len(data) if data else 0}")
                logger.info(f"🚨 CRITICAL: 参与者: {participant.identity if participant and hasattr(participant, 'identity') else 'None'}")
                
                asyncio.create_task(handle_data_received_async(data, participant))
            except Exception as e:
                logger.error(f"❌ 处理data_received事件失败: {e}")
                import traceback
                logger.error(f"错误详情:\n{traceback.format_exc()}")
        
        @ctx.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            """监听音频轨道订阅 - 增强调试信息"""
            # 原有的日志
            logger.info(f"[LOG][audio-in] 订阅到轨道: {track.kind} from {participant.identity}")
            
            # 新增的调试信息
            print(f"🎧 订阅了音轨: {track.kind}, 来自: {participant.identity}", file=sys.stdout, flush=True)
            logger.info(f"🎧 TRACK_SUBSCRIBED: kind={track.kind}, participant={participant.identity}, publication_sid={publication.sid if publication else 'N/A'}")
            
            if track.kind == "audio":
                logger.info(f"[LOG][audio-in] 开始监听音频输入...")
                print(f"🔊 音频轨道已订阅，开始处理音频流", file=sys.stdout, flush=True)
                
                # 额外的音频轨道调试信息
                try:
                    logger.info(f"🎵 音频轨道详情: source={track.source if hasattr(track, 'source') else 'unknown'}")
                    if hasattr(track, 'sample_rate'):
                        logger.info(f"🎵 采样率: {track.sample_rate}Hz")
                    if hasattr(track, 'num_channels'):
                        logger.info(f"🎵 声道数: {track.num_channels}")
                except Exception as track_info_error:
                    logger.warning(f"⚠️ 获取音频轨道详情失败: {track_info_error}")
            else:
                logger.info(f"📹 非音频轨道: {track.kind}")
                print(f"📹 订阅了非音频轨道: {track.kind}", file=sys.stdout, flush=True)
        
        # 添加参与者连接监听器
        @ctx.room.on("participant_connected")
        def on_participant_connected(participant):
            """监听参与者连接事件"""
            logger.info(f"👤 参与者已连接: {participant.identity}")
            print(f"👤 新参与者加入房间: {participant.identity}", file=sys.stdout, flush=True)
        
        @ctx.room.on("participant_disconnected")
        def on_participant_disconnected(participant):
            """监听参与者断开连接事件"""
            logger.info(f"👋 参与者已断开: {participant.identity}")
            print(f"👋 参与者离开房间: {participant.identity}", file=sys.stdout, flush=True)
        
        logger.info(f"📨 房间事件监听器已注册")
        
        # 创建并启动AgentSession - 正确传入agent和room参数
        logger.info(f"📡 初始化 {language_name} AgentSession...")
        session = AgentSession(
            vad=vad,
            stt=stt,
            llm=llm,
            tts=tts,
        )
        
        # 添加AgentSession事件监听 - 支持流式实时处理
        
        # 用于累积部分翻译结果的缓冲区
        partial_translation_buffer = ""
        
        async def on_user_speech_async(event):
            """异步处理用户语音转写结果 - 支持实时和最终结果"""
            transcript = event.alternatives[0].text if event.alternatives else ""
            confidence = event.alternatives[0].confidence if event.alternatives else 0.0
            is_final = getattr(event, 'is_final', True)  # 检查是否为最终结果
            
            logger.info(f"[LOG][speech-in] 用户语音转写: '{transcript}' (置信度: {confidence:.2f}, 最终: {is_final})")
            
            # 发送转写结果到前端 - 区分实时和最终结果
            try:
                transcript_data = json.dumps({
                    'type': 'transcript',
                    'text': transcript,
                    'confidence': confidence,
                    'language': 'zh',
                    'is_final': is_final,
                    'timestamp': asyncio.get_event_loop().time()
                }).encode('utf-8')
                await ctx.room.local_participant.publish_data(transcript_data)
                logger.info(f"[LOG][subtitles-send] 转写结果已发送: {transcript} (最终: {is_final})")
            except Exception as e:
                logger.error(f"❌ 发送转写结果失败: {e}")
        
        # 监听实时语音转写事件（包括部分结果）
        @session.on("user_speech_committed")
        def on_user_speech_committed(event):
            """处理最终确认的语音转写"""
            asyncio.create_task(on_user_speech_async(event))
        
        # 尝试监听部分语音结果（如果LiveKit支持）
        try:
            @session.on("user_speech_interim")
            def on_user_speech_interim(event):
                """处理部分语音转写结果"""
                asyncio.create_task(on_user_speech_async(event))
            logger.info("✅ 已启用实时语音转写监听")
        except Exception as e:
            logger.warning(f"⚠️ 无法启用实时语音转写监听: {e}")
        
        async def on_agent_speech_async(event):
            """异步处理Agent语音合成结果 - 支持流式翻译片段"""
            nonlocal partial_translation_buffer
            
            # 获取翻译片段
            translation_chunk = ""
            if hasattr(event, 'alternatives') and event.alternatives:
                translation_chunk = event.alternatives[0].text or ""
            elif hasattr(event, 'text'):
                translation_chunk = event.text or ""
            
            is_final = getattr(event, 'is_final', True)
            
            if translation_chunk:
                # 累积翻译片段
                if not is_final:
                    partial_translation_buffer += translation_chunk
                    current_translation = partial_translation_buffer
                else:
                    # 最终结果，清空缓冲区
                    current_translation = partial_translation_buffer + translation_chunk
                    partial_translation_buffer = ""
                
                logger.info(f"[LOG][speech-out] Agent翻译输出: '{translation_chunk}' (累积: '{current_translation}', 最终: {is_final})")
                
                # 实时发送翻译结果到前端
                try:
                    translation_data = json.dumps({
                        'type': 'translation',
                        'text': current_translation,
                        'chunk': translation_chunk,
                        'source_language': 'zh',
                        'target_language': target_language,
                        'is_final': is_final,
                        'timestamp': asyncio.get_event_loop().time()
                    }).encode('utf-8')
                    await ctx.room.local_participant.publish_data(translation_data)
                    logger.info(f"[LOG][subtitles-send] 翻译结果已发送: '{translation_chunk}' (最终: {is_final})")
                except Exception as e:
                    logger.error(f"❌ 发送翻译结果失败: {e}")
        
        @session.on("agent_speech_committed")
        def on_agent_speech_committed(event):
            """处理最终确认的翻译结果"""
            asyncio.create_task(on_agent_speech_async(event))
        
        # 尝试监听流式翻译片段（如果LiveKit支持）
        try:
            @session.on("agent_speech_interim")
            def on_agent_speech_interim(event):
                """处理流式翻译片段"""
                asyncio.create_task(on_agent_speech_async(event))
            logger.info("✅ 已启用流式翻译片段监听")
        except Exception as e:
            logger.warning(f"⚠️ 无法启用流式翻译片段监听: {e}")
        
        # 监听LLM流式输出（直接从ChatChunk获取）
        async def on_llm_stream_chunk(chunk_content: str, is_final: bool = False):
            """处理LLM流式输出片段"""
            nonlocal partial_translation_buffer
            
            if chunk_content:
                # 累积翻译片段
                if not is_final:
                    partial_translation_buffer += chunk_content
                    current_translation = partial_translation_buffer
                else:
                    current_translation = partial_translation_buffer + chunk_content
                    partial_translation_buffer = ""
                
                logger.info(f"[LOG][llm-stream] LLM流式片段: '{chunk_content}' (累积: '{current_translation}', 最终: {is_final})")
                
                # 实时发送翻译片段到前端
                try:
                    translation_data = json.dumps({
                        'type': 'translation_stream',
                        'text': current_translation,
                        'chunk': chunk_content,
                        'source_language': 'zh',
                        'target_language': target_language,
                        'is_final': is_final,
                        'timestamp': asyncio.get_event_loop().time()
                    }).encode('utf-8')
                    await ctx.room.local_participant.publish_data(translation_data)
                    logger.info(f"[LOG][subtitles-send] LLM流式片段已发送: '{chunk_content}' (最终: {is_final})")
                except Exception as e:
                    logger.error(f"❌ 发送LLM流式片段失败: {e}")
        
        # 连接流式翻译回调
        try:
            # 获取LLM实例并设置流式回调
            if hasattr(session, 'llm') and hasattr(session.llm, 'set_stream_callback'):
                session.llm.set_stream_callback(on_llm_stream_chunk)
                logger.info("✅ 已连接LLM流式翻译回调")
            elif hasattr(llm, 'set_stream_callback'):
                llm.set_stream_callback(on_llm_stream_chunk)
                logger.info("✅ 已连接LLM流式翻译回调")
            else:
                logger.warning("⚠️ 无法连接LLM流式翻译回调")
        except Exception as callback_error:
            logger.warning(f"⚠️ 设置流式翻译回调失败: {callback_error}")
        
        # 启动Agent会话 - 正确传入agent和room参数
        logger.info(f"▶️ 启动 {language_name} 翻译会话...")
        await session.start(agent=agent, room=ctx.room)
        
        logger.info(f"🎉 {language_name} 翻译Agent已成功运行!")
        logger.info(f"🎧 等待用户语音输入进行实时翻译...")
        
        # 监听现有参与者的轨道 - 使用正确的方法获取参与者
        try:
            # 根据LiveKit Python SDK文档，使用remote_participants属性
            if hasattr(ctx.room, 'remote_participants'):
                participants = ctx.room.remote_participants
                logger.info(f"[LOG][participants] 发现 {len(participants)} 个远程参与者")
                for participant in participants.values():
                    logger.info(f"[LOG][participants] 检查参与者: {participant.identity}")
                    for track_pub in participant.tracks.values():
                        if track_pub.track:
                            logger.info(f"[LOG][audio-in] 发现现有轨道: {track_pub.track.kind}")
                            if track_pub.track.kind == "audio":
                                logger.info(f"[LOG][audio-in] 音频轨道已就绪")
            else:
                logger.info(f"[LOG][participants] 房间暂无远程参与者或无法访问参与者列表")
        except Exception as e:
            logger.warning(f"[LOG][participants] 获取参与者信息失败: {e}")
            logger.info(f"[LOG][participants] 将通过事件监听器处理新加入的参与者")
        
        # 发送欢迎消息到数据通道
        try:
            welcome_data = json.dumps({
                'type': 'translation',
                'text': f"你好！我是{language_name}实时翻译助手，我会将你的中文转换为{language_name}。",
                'language': target_language,
                'timestamp': asyncio.get_event_loop().time()
            }).encode('utf-8')
            await ctx.room.local_participant.publish_data(welcome_data)
            logger.info(f"[LOG][subtitles-send] 欢迎消息已通过数据通道发送: {language_name}")
        except Exception as e:
            logger.warning(f"⚠️ 发送欢迎消息失败: {e}")
        
        # 保持会话运行
        logger.info(f"🔄 {language_name} Agent运行中，监听语音输入...")
        print(f"🔄 Agent已启动完成，开始持续监听音频流...", file=sys.stdout, flush=True)
        
        # 保持 Agent 持续运行，防止自动退出
        logger.info(f"⏳ Agent进入持续运行模式，等待音频输入...")
        print(f"⏳ Agent持续运行中，等待用户音频输入...", file=sys.stdout, flush=True)
        
        # 使用 asyncio.Event().wait() 保持Agent持续运行
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            logger.info(f"🛑 Agent收到取消信号，准备退出...")
            print(f"🛑 Agent正在优雅退出...", file=sys.stdout, flush=True)
        except KeyboardInterrupt:
            logger.info(f"🛑 Agent收到中断信号，准备退出...")
            print(f"🛑 Agent收到中断信号，正在退出...", file=sys.stdout, flush=True)
        
    except Exception as e:
        logger.error(f"❌ Agent启动失败: {e}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"错误详情:\n{error_details}")
        
        # 强制输出到stdout和stderr确保Render能看到
        print(f"RENDER_ERROR: Agent启动失败: {e}", file=sys.stdout, flush=True)
        print(f"RENDER_ERROR_DETAILS:\n{error_details}", file=sys.stdout, flush=True)
        print(f"RENDER_ERROR: Agent启动失败: {e}", file=sys.stderr, flush=True)
        print(f"RENDER_ERROR_DETAILS:\n{error_details}", file=sys.stderr, flush=True)
        
        raise
    finally:
        # 清理Agent状态
        try:
            if 'room_name' in locals() and room_name in active_agents:
                del active_agents[room_name]
                agent_stats["active_sessions"] -= 1
                logger.info(f"🧹 清理Agent状态: {room_name}")
                print(f"🧹 Agent状态已清理: {room_name}", file=sys.stdout, flush=True)
            
            if 'language_name' in locals():
                logger.info(f"🔌 {language_name} Agent会话已结束")
                print(f"🔌 {language_name} Agent会话已结束", file=sys.stdout, flush=True)
            else:
                logger.info(f"🔌 Agent会话已结束")
                print(f"🔌 Agent会话已结束", file=sys.stdout, flush=True)
                
        except Exception as cleanup_error:
            logger.error(f"❌ 清理Agent状态时出错: {cleanup_error}")
            print(f"❌ 清理Agent状态时出错: {cleanup_error}", file=sys.stdout, flush=True)

def prewarm(proc: JobProcess):
    """预热函数 - 预加载模型和资源"""
    logger.info("🔥 正在预热翻译模型...")
    # 这里可以预加载模型
    logger.info("✅ 预热完成")

def main():
    """主函数 - 启动Agent翻译服务"""
    logger.info("🌟 Agent翻译服务启动中...")
    
    # 检查环境变量
    required_env_vars = [
        "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
        "DEEPGRAM_API_KEY", "GROQ_API_KEY", "CARTESIA_API_KEY"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ 缺少环境变量: {missing_vars}")
        sys.exit(1)
    
    logger.info(f"🌍 支持的语言: {', '.join([f'{code}({info['name']})' for code, info in LANGUAGE_CONFIG.items()])}")
    logger.info(f"🏠 支持的房间: {', '.join(ROOM_LANGUAGE_MAP.keys())}")
    
    # 启动Flask API服务器
    logger.info("🚀 启动Flask API服务器...")
    flask_thread = threading.Thread(target=start_flask_api, daemon=True)
    flask_thread.start()
    
    # 配置LiveKit Agent Worker
    logger.info("⚡ 启动LiveKit Agent Worker...")
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        num_idle_processes=1
    )
    
    # 运行Agent Worker
    cli.run_app(opts)

if __name__ == "__main__":
    main() 
