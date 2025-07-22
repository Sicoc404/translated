#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Token 服务器
为前端提供房间访问token
干净的CORS解决方案（只使用flask-cors）
"""

import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from livekit import api
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 【唯一的CORS配置】- 只使用flask-cors，避免重复头部
CORS(app, 
     resources={
         r"/api/*": {
             "origins": ["https://translated-frontend-02q6.onrender.com"],
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "supports_credentials": True
         },
         r"/health": {
             "origins": ["https://translated-frontend-02q6.onrender.com"],
             "methods": ["GET"],
             "allow_headers": ["Content-Type"]
         },
         r"/": {
             "origins": ["https://translated-frontend-02q6.onrender.com"],
             "methods": ["GET"],
             "allow_headers": ["Content-Type"]
         }
     }
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LiveKit配置
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')
LIVEKIT_URL = os.getenv('LIVEKIT_URL')

if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL]):
    logger.error("❌ 缺少必要的LiveKit环境变量")
    exit(1)

@app.route('/api/token', methods=['POST', 'OPTIONS'])
def get_token():
    """
    生成LiveKit房间访问token
    【注意】：不使用@cross_origin装饰器，避免重复CORS头
    
    请求参数:
    - room: 房间名称
    - identity: 参与者身份标识
    """
    # 打印请求信息用于调试
    logger.info(f"🌐 收到请求: {request.method} {request.path}")
    logger.info(f"🔍 Origin: {request.headers.get('Origin', 'None')}")
    logger.info(f"🔍 Content-Type: {request.headers.get('Content-Type', 'None')}")
    
    # OPTIONS请求由flask-cors自动处理，不需要手动处理
    if request.method == 'OPTIONS':
        logger.info("✈️ OPTIONS请求由flask-cors自动处理")
        return '', 200
        
    try:
        logger.info("📥 开始处理POST请求...")
        
        # 打印原始请求体
        raw_data = request.get_data()
        logger.info(f"📄 原始请求体: {raw_data}")
        
        data = request.get_json()
        logger.info(f"📋 解析后的JSON: {data}")
        
        if not data:
            logger.error("❌ 请求体为空或格式错误")
            return jsonify({'error': '请求体为空或格式错误'}), 400
            
        room_name = data.get('room')
        identity = data.get('identity', f'user-{os.urandom(4).hex()}')
        
        if not room_name:
            logger.error("❌ 缺少房间名称")
            return jsonify({'error': '缺少房间名称'}), 400
        
        logger.info(f"🎫 为用户 {identity} 生成房间 {room_name} 的token")
        
        # 检查环境变量
        logger.info(f"🔑 LIVEKIT_API_KEY: {'已设置' if LIVEKIT_API_KEY else '❌未设置'}")
        logger.info(f"🔑 LIVEKIT_API_SECRET: {'已设置' if LIVEKIT_API_SECRET else '❌未设置'}")
        logger.info(f"🔑 LIVEKIT_URL: {LIVEKIT_URL if LIVEKIT_URL else '❌未设置'}")
        
        # 创建AccessToken
        token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
            .with_identity(identity) \
            .with_name(identity) \
            .with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                # 允许发布音频（用于语音输入）
                can_publish=True,
                can_publish_data=True,
                # 允许订阅（用于接收翻译音频）
                can_subscribe=True
            ))
        
        jwt_token = token.to_jwt()
        
        logger.info(f"✅ Token生成成功 - 房间: {room_name}, 用户: {identity}")
        
        # 【重要】：直接返回jsonify结果，不手动添加CORS头
        response_data = {
            'token': jwt_token,
            'room': room_name,
            'identity': identity,
            'livekit_url': LIVEKIT_URL
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ 生成token失败: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        
        # 【重要】：不手动添加CORS头，让flask-cors处理
        return jsonify({'error': f'生成token失败: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    logger.info("🔍 健康检查请求")
    return jsonify({
        'status': 'ok', 
        'service': 'livekit-token-server',
        'cors': 'flask-cors only',
        'allowed_origins': ['https://translated-frontend-02q6.onrender.com']
    })

@app.route('/', methods=['GET'])
def root():
    """根路径"""
    logger.info("🏠 根路径访问")
    return jsonify({
        'message': 'LiveKit Token Server',
        'version': '2.0.0',
        'cors_enabled': True,
        'cors_method': 'flask-cors only',
        'endpoints': {
            'token': '/api/token (POST)',
            'health': '/health (GET)'
        },
        'allowed_origins': ['https://translated-frontend-02q6.onrender.com']
    })

# 全局错误处理器 - 不手动添加CORS头
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"🔍 404错误: {request.path}")
    return jsonify({'error': 'API端点未找到', 'path': request.path}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"💥 500错误: {error}")
    return jsonify({'error': '服务器内部错误'}), 500

# 全局请求日志
@app.before_request
def log_request_info():
    logger.info(f"📥 {request.method} {request.path} - Origin: {request.headers.get('Origin', 'None')}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    logger.info(f"🚀 启动Token服务器")
    logger.info(f"📡 端口: {port}")
    logger.info(f"🌐 允许的前端域名: https://translated-frontend-02q6.onrender.com")
    logger.info(f"🔒 CORS策略: 仅使用flask-cors（避免重复头部）")
    
    app.run(host='0.0.0.0', port=port, debug=False) 
