#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Agents 多语言实时翻译广播系统 - 主入口
使用LiveKit Agents 1.1.7的标准工作流程
同时提供Token服务器功能
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext, 
    WorkerOptions, 
    cli, 
    JobProcess,
    RunContext
)
from agent_config import create_translation_agent, create_translation_components, LANGUAGE_CONFIG

# Token服务器相关导入
from flask import Flask, request, jsonify
from flask_cors import CORS
from livekit import api
import threading

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("translation-agent")

# 房间与语言的映射关系
ROOM_LANGUAGE_MAP = {
    "Pryme-Japanese": "ja",
    "Pryme-Korean": "ko", 
    "Pryme-Vietnamese": "vi",
    "Pryme-Malay": "ms"
}

# Token服务器配置
app = Flask(__name__)
CORS(app, origins=["https://translated-frontend.onrender.com", "http://localhost:5173", "http://localhost:3000"])

LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')
LIVEKIT_URL = os.getenv('LIVEKIT_URL')

@app.route('/api/token', methods=['POST'])
def get_token():
    """生成LiveKit房间访问token"""
    try:
        data = request.get_json()
        room_name = data.get('room')
        identity = data.get('identity', f'user-{os.urandom(4).hex()}')
        
        if not room_name:
            return jsonify({'error': '缺少房间名称'}), 400
        
        logger.info(f"为用户 {identity} 生成房间 {room_name} 的token")
        
        # 创建AccessToken
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(identity) \
            .with_name(identity) \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_publish_data=True,
                can_subscribe=True
            ))
        
        jwt_token = token.to_jwt()
        
        return jsonify({
            'token': jwt_token,
            'room': room_name,
            'identity': identity,
            'livekit_url': LIVEKIT_URL
        })
        
    except Exception as e:
        logger.error(f"生成token失败: {e}")
        return jsonify({'error': f'生成token失败: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'service': 'livekit-translation-system'})

@app.route('/', methods=['GET'])
def root():
    """根路径"""
    return jsonify({
        'message': 'LiveKit Translation System',
        'services': ['agent', 'token-server'],
        'endpoints': {
            'token': '/api/token (POST)',
            'health': '/health (GET)'
        }
    })

def start_flask_server():
    """在单独线程中启动Flask服务器"""
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

async def entrypoint(ctx: JobContext):
    """
    LiveKit Agent的入口点函数
    根据房间名称确定翻译语言并启动相应的代理
    
    Args:
        ctx: JobContext实例，包含房间连接信息
    """
    # 连接到房间
    await ctx.connect()
    
    # 获取房间名称
    room_name = ctx.room.name
    logger.info(f"🏠 连接到房间: {room_name}")
    logger.info(f"🔍 房间参与者数量: {ctx.room.num_participants}")
    
    # 根据房间名称确定目标语言
    target_language = None
    for room_prefix, language_code in ROOM_LANGUAGE_MAP.items():
        if room_name.startswith(room_prefix):
            target_language = language_code
            break
    
    if not target_language:
        logger.error(f"❌ 未知的房间名称: {room_name}，支持的房间前缀: {list(ROOM_LANGUAGE_MAP.keys())}")
        return
    
    language_name = LANGUAGE_CONFIG[target_language]["name"]
    logger.info(f"🌍 为房间 '{room_name}' 启动 {language_name} 翻译代理...")
    
    try:
        # 创建翻译组件
        vad, stt, llm, tts = create_translation_components(target_language)
        logger.info(f"🤖 {language_name} 组件创建成功")
        
        # 创建翻译Agent
        agent = create_translation_agent(target_language)
        logger.info(f"🤖 {language_name} Agent创建成功")
        
        # 创建AgentSession并配置组件
        session = AgentSession(
            vad=vad,
            stt=stt,
            llm=llm,
            tts=tts,
        )
        
        logger.info(f"📝 组件配置:")
        logger.info(f"  VAD: {type(vad).__name__}")
        logger.info(f"  STT: {type(stt).__name__} (模型: nova-2-zh)")
        logger.info(f"  LLM: {type(llm).__name__} (模型: llama3-8b-8192)")
        logger.info(f"  TTS: {type(tts).__name__} (语言: {target_language})")
        
        logger.info(f"🚀 启动 {language_name} 翻译代理...")
        
        # 启动session - 根据1.1.7 API
        await session.start(agent=agent, room=ctx.room)
        
        logger.info(f"✅ {language_name} 翻译代理已成功启动并连接到房间")
        logger.info(f"🎧 正在监听音频输入...")
        
        # 发送欢迎消息
        try:
            await session.generate_reply(
                instructions=f"简短地用{language_name}向用户问好，告诉他们你是{language_name}实时翻译助手。"
            )
            logger.info(f"👋 {language_name} 欢迎消息已发送")
        except Exception as e:
            logger.warning(f"⚠️ 发送欢迎消息失败: {e}")
        
        logger.info(f"🔄 {language_name} 翻译代理正在运行，等待语音输入...")
        
        # 监听音频事件
        def on_audio_received(audio_frame):
            logger.debug(f"🎵 收到音频帧: {len(audio_frame.data)} bytes")
        
        def on_stt_start():
            logger.info(f"🎤 STT开始识别...")
        
        def on_stt_result(text):
            logger.info(f"📝 STT识别结果: '{text}'")
        
        def on_llm_start(prompt):
            logger.info(f"🧠 LLM开始翻译: '{prompt[:50]}...'")
        
        def on_llm_result(translation):
            logger.info(f"🌍 LLM翻译结果: '{translation}'")
        
        def on_tts_start(text):
            logger.info(f"🗣️ TTS开始合成: '{text}'")
        
        def on_tts_result(audio_len):
            logger.info(f"🔊 TTS合成完成: {audio_len} bytes音频")
        
        # 保持运行状态，等待session完成
        # 注意：在1.1.7中，session会自动处理音频流和翻译
        
    except Exception as e:
        logger.error(f"❌ 启动 {language_name} 翻译代理时出错: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        raise

def prewarm(proc: JobProcess):
    """
    预热函数 - 在每个子进程启动时执行
    可以在此处加载模型或执行其他预热操作
    
    Args:
        proc: JobProcess实例
    """
    logger.info("正在预热翻译模型和连接...")
    # 这里可以添加模型预加载代码
    # 例如预加载Silero VAD模型等

def main():
    """
    主函数 - 使用LiveKit CLI启动Worker
    """
    # 检查必要的环境变量
    required_env_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY", 
        "LIVEKIT_API_SECRET",
        "DEEPGRAM_API_KEY",
        "GROQ_API_KEY",
        "CARTESIA_API_KEY"
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {missing_vars}")
        sys.exit(1)
    
    logger.info("LiveKit 多语言翻译代理启动中...")
    logger.info(f"支持的语言: {', '.join([f'{code}({info['name']})' for code, info in LANGUAGE_CONFIG.items()])}")
    logger.info(f"支持的房间: {', '.join(ROOM_LANGUAGE_MAP.keys())}")
    
    # 在生产环境中启动Flask服务器
    if len(sys.argv) > 1 and sys.argv[1] == 'start':
        logger.info("启动Token服务器...")
        flask_thread = threading.Thread(target=start_flask_server, daemon=True)
        flask_thread.start()
    
    # 配置Worker选项
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,  # 使用正确的参数名
        num_idle_processes=1,  # 控制空闲进程数量
    )
    
    # 运行Agent Worker
    cli.run_app(opts)

if __name__ == "__main__":
    main() 
