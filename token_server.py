#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LiveKit Token 服务器
为前端提供房间访问token
完整的CORS解决方案
"""

import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from livekit import api
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 完整的CORS配置 - 明确指定前端域名
CORS(app, 
     resources={
         r"/api/*": {
             "origins": [
                 "https://translated-frontend.onrender.com",
                 "http://localhost:3000",  # 本地开发
                 "http://localhost:5173",  # Vite开发服务器
                 "https://localhost:3000",
                 "https://localhost:5173"
             ],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": [
                 "Content-Type", 
                 "Authorization", 
                 "X-Requested-With", 
                 "Accept",
                 "Origin",
                 "Access-Control-Request-Method",
                 "Access-Control-Request-Headers"
             ],
             "supports_credentials": True,
             "send_wildcard": False,  # 明确不使用通配符
             "max_age": 3600  # 缓存预检请求1小时
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
@cross_origin(origins=['https://translated-frontend.onrender.com'])
def get_token():
    """
    生成LiveKit房间访问token
    支持CORS预检请求
    
    请求参数:
    - room: 房间名称
    - identity: 参与者身份标识
    """
    # 打印请求信息用于调试
    logger.info(f"🌐 收到请求: {request.method} {request.path}")
    logger.info(f"🔍 Origin: {request.headers.get('Origin', 'None')}")
    logger.info(f"🔍 Content-Type: {request.headers.get('Content-Type', 'None')}")
    
    # 明确处理OPTIONS预检请求
    if request.method == 'OPTIONS':
        logger.info("✈️ 处理CORS预检请求")
        response = jsonify({'status': 'preflight ok'})
        response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With,Accept')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        response.headers.add('Access-Control-Max-Age', '3600')
        return response, 200
        
    try:
        data = request.get_json()
        if not data:
            logger.error("❌ 请求体为空或格式错误")
            return jsonify({'error': '请求体为空或格式错误'}), 400
            
        room_name = data.get('room')
        identity = data.get('identity', f'user-{os.urandom(4).hex()}')
        
        if not room_name:
            logger.error("❌ 缺少房间名称")
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
        
        # 构建响应并明确设置CORS头
        response_data = {
            'token': jwt_token,
            'room': room_name,
            'identity': identity,
            'livekit_url': LIVEKIT_URL
        }
        
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        
        return response, 200
        
    except Exception as e:
        logger.error(f"❌ 生成token失败: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        
        error_response = jsonify({'error': f'生成token失败: {str(e)}'})
        error_response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
        return error_response, 500

@app.route('/health', methods=['GET'])
@cross_origin(origins=['https://translated-frontend.onrender.com'])
def health_check():
    """健康检查接口"""
    logger.info("🔍 健康检查请求")
    response = jsonify({
        'status': 'ok', 
        'service': 'livekit-token-server',
        'cors': 'enabled',
        'allowed_origins': ['https://translated-frontend.onrender.com']
    })
    response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
    return response

@app.route('/', methods=['GET'])
@cross_origin(origins=['https://translated-frontend.onrender.com'])
def root():
    """根路径"""
    logger.info("🏠 根路径访问")
    response = jsonify({
        'message': 'LiveKit Token Server',
        'version': '1.0.0',
        'cors_enabled': True,
        'endpoints': {
            'token': '/api/token (POST)',
            'health': '/health (GET)'
        },
        'allowed_origins': ['https://translated-frontend.onrender.com']
    })
    response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
    return response

# 全局错误处理器 - 也要添加CORS头
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"🔍 404错误: {request.path}")
    response = jsonify({'error': 'API端点未找到', 'path': request.path})
    response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
    return response, 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"💥 500错误: {error}")
    response = jsonify({'error': '服务器内部错误'})
    response.headers.add('Access-Control-Allow-Origin', 'https://translated-frontend.onrender.com')
    return response, 500

# 全局请求日志
@app.before_request
def log_request_info():
    logger.info(f"📥 {request.method} {request.path} - Origin: {request.headers.get('Origin', 'None')}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    logger.info(f"🚀 启动Token服务器")
    logger.info(f"📡 端口: {port}")
    logger.info(f"🌐 允许的前端域名: https://translated-frontend.onrender.com")
    logger.info(f"🔒 CORS策略: 严格模式（明确指定域名）")
    
    app.run(host='0.0.0.0', port=port, debug=False) 
