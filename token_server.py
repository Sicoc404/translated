#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Token 服务器
为前端提供房间访问token
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

# 配置CORS，允许所有来源和方法
CORS(app, 
     origins=["*"],  # 允许所有来源
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 允许所有方法
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],  # 允许所有常用头
     supports_credentials=True  # 支持凭证
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
    
    请求参数:
    - room: 房间名称
    - identity: 参与者身份标识
    """
    # 处理OPTIONS预检请求
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        room_name = data.get('room')
        identity = data.get('identity', f'user-{os.urandom(4).hex()}')
        
        if not room_name:
            return jsonify({'error': '缺少房间名称'}), 400
        
        logger.info(f"🎫 为用户 {identity} 生成房间 {room_name} 的token")
        
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
        
        return jsonify({
            'token': jwt_token,
            'room': room_name,
            'identity': identity,
            'livekit_url': LIVEKIT_URL
        })
        
    except Exception as e:
        logger.error(f"❌ 生成token失败: {e}")
        return jsonify({'error': '生成token失败'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({'status': 'ok', 'service': 'livekit-token-server'})

@app.route('/', methods=['GET'])
def root():
    """根路径"""
    return jsonify({
        'message': 'LiveKit Token Server',
        'endpoints': {
            'token': '/api/token (POST)',
            'health': '/health (GET)'
        }
    })

# 添加全局错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'API端点未找到'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': '服务器内部错误'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    logger.info(f"🚀 启动Token服务器 - 端口: {port}")
    app.run(host='0.0.0.0', port=port, debug=False) 
