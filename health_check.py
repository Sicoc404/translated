#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
语音翻译流水线健康检查脚本
测试 Deepgram STT、Groq LLM、Cartesia TTS 和 LiveKit 连接
"""

import os
import sys
import json
import time
import asyncio
import argparse
import logging
import websockets
import requests
import wave
import struct
from typing import Optional, Dict, Any
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("health-check")

class HealthChecker:
    """语音翻译流水线健康检查器"""
    
    def __init__(self):
        self.deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY")
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.cartesia_api_key = os.environ.get("CARTESIA_API_KEY")
        self.livekit_api_key = os.environ.get("LIVEKIT_API_KEY")
        self.livekit_api_secret = os.environ.get("LIVEKIT_API_SECRET")
        self.livekit_url = os.environ.get("LIVEKIT_URL")
        
        # 检查必需的环境变量
        self.check_environment()
    
    def check_environment(self):
        """检查环境变量"""
        logger.info("🔍 检查环境变量...")
        
        env_vars = {
            "DEEPGRAM_API_KEY": self.deepgram_api_key,
            "GROQ_API_KEY": self.groq_api_key,
            "CARTESIA_API_KEY": self.cartesia_api_key,
            "LIVEKIT_API_KEY": self.livekit_api_key,
            "LIVEKIT_API_SECRET": self.livekit_api_secret,
            "LIVEKIT_URL": self.livekit_url,
        }
        
        missing_vars = []
        for var_name, var_value in env_vars.items():
            if var_value:
                logger.info(f"✅ {var_name}: {'*' * 8}{var_value[-4:]}")
            else:
                logger.warning(f"❌ {var_name}: 未设置")
                missing_vars.append(var_name)
        
        if missing_vars:
            logger.warning(f"⚠️ 缺少环境变量: {', '.join(missing_vars)}")
            logger.warning("某些测试可能会失败")
    
    def create_test_audio(self, filename: str = "test_audio.wav", duration: float = 3.0):
        """创建测试音频文件"""
        logger.info(f"🎵 创建测试音频文件: {filename}")
        
        try:
            # 生成简单的正弦波音频
            sample_rate = 16000
            frequency = 440  # A4 音符
            frames = int(duration * sample_rate)
            
            # 创建音频数据
            audio_data = []
            for i in range(frames):
                # 生成正弦波
                value = int(32767 * 0.3 * (
                    0.5 * (1 + (i % 8000) / 8000) *  # 音量渐变
                    (1 if i < frames // 2 else 0.5)  # 后半段音量减半
                ))
                audio_data.append(struct.pack('<h', value))
            
            # 写入WAV文件
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(b''.join(audio_data))
            
            logger.info(f"✅ 测试音频文件创建成功: {filename} ({duration}秒)")
            return filename
            
        except Exception as e:
            logger.error(f"❌ 创建测试音频失败: {e}")
            return None

    async def test_deepgram_stt(self) -> bool:
        """测试 Deepgram STT WebSocket 连接"""
        logger.info("\n" + "="*50)
        logger.info("🎤 开始测试 Deepgram STT")
        logger.info("="*50)
        
        if not self.deepgram_api_key:
            logger.error("❌ DEEPGRAM_API_KEY 未设置")
            return False
        
        try:
            # 构建 WebSocket URL
            ws_url = "wss://api.deepgram.com/v1/listen"
            params = {
                "model": "nova-2",
                "language": "zh",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1",
                "interim_results": "true",
                "smart_format": "true"
            }
            
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{ws_url}?{query_string}"
            
            logger.info(f"📡 连接到 Deepgram: {ws_url}")
            logger.info(f"🔧 参数: {params}")
            
            # 创建测试音频
            audio_file = self.create_test_audio()
            if not audio_file:
                return False
            
            # 连接 WebSocket
            headers = {
                "Authorization": f"Token {self.deepgram_api_key}"
            }
            
            async with websockets.connect(full_url, extra_headers=headers) as websocket:
                logger.info("✅ WebSocket 连接成功")
                
                # 监听初始消息
                try:
                    initial_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    initial_data = json.loads(initial_message)
                    
                    if "metadata" in initial_data:
                        request_id = initial_data["metadata"].get("request_id")
                        logger.info(f"🆔 dg-request-id: {request_id}")
                        logger.info("🔓 WebSocket 已打开 (open)")
                    
                except asyncio.TimeoutError:
                    logger.warning("⚠️ 未收到初始消息")
                
                # 发送音频数据
                logger.info("📤 发送测试音频数据...")
                with open(audio_file, 'rb') as f:
                    # 跳过 WAV 头部
                    f.seek(44)
                    audio_data = f.read()
                
                # 分块发送音频
                chunk_size = 8000  # 每块 0.5 秒的音频
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]
                    await websocket.send(chunk)
                    await asyncio.sleep(0.1)  # 模拟实时流
                
                # 发送结束标记
                await websocket.send(json.dumps({"type": "CloseStream"}))
                logger.info("📤 音频发送完成")
                
                # 接收转写结果
                transcript_received = False
                timeout_count = 0
                max_timeout = 10
                
                while timeout_count < max_timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(message)
                        
                        if "channel" in data:
                            alternatives = data["channel"]["alternatives"]
                            if alternatives and len(alternatives) > 0:
                                transcript = alternatives[0].get("transcript", "")
                                confidence = alternatives[0].get("confidence", 0)
                                is_final = data.get("is_final", False)
                                
                                if transcript.strip():
                                    transcript_received = True
                                    status = "final" if is_final else "interim"
                                    logger.info(f"🎯 转写结果 ({status}): '{transcript}' (置信度: {confidence:.2f})")
                        
                        elif "metadata" in data:
                            logger.info(f"📊 元数据: {data['metadata']}")
                        
                        # 如果是最终结果，可以结束
                        if data.get("is_final"):
                            break
                            
                    except asyncio.TimeoutError:
                        timeout_count += 1
                        logger.debug(f"⏱️ 等待响应超时 ({timeout_count}/{max_timeout})")
                        continue
                    except Exception as e:
                        logger.error(f"❌ 接收消息错误: {e}")
                        break
                
                # 清理测试文件
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                
                if transcript_received:
                    logger.info("✅ Deepgram STT 测试成功")
                    return True
                else:
                    logger.warning("⚠️ 未收到有效转写结果")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Deepgram STT 测试失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False

    async def test_groq_llm(self) -> bool:
        """测试 Groq LLM 翻译"""
        logger.info("\n" + "="*50)
        logger.info("🧠 开始测试 Groq LLM 翻译")
        logger.info("="*50)
        
        if not self.groq_api_key:
            logger.error("❌ GROQ_API_KEY 未设置")
            return False
        
        try:
            # 测试用例
            test_cases = [
                {
                    "input": "你好世界",
                    "target_language": "韩语",
                    "expected_contains": ["안녕", "세계", "하세요"]
                },
                {
                    "input": "今天天气很好",
                    "target_language": "日语", 
                    "expected_contains": ["今日", "天気", "いい"]
                }
            ]
            
            success_count = 0
            
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n📝 测试案例 {i}: 中文 → {test_case['target_language']}")
                logger.info(f"🔤 输入: '{test_case['input']}'")
                
                # 准备请求
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                }
                
                messages = [
                    {
                        "role": "system",
                        "content": f"你是一个专业的翻译助手，将中文翻译成{test_case['target_language']}。直接输出翻译结果，不要添加任何解释。"
                    },
                    {
                        "role": "user", 
                        "content": test_case['input']
                    }
                ]
                
                data = {
                    "model": "llama3-8b-8192",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 100,
                    "stream": True
                }
                
                logger.info(f"📡 调用 Groq API...")
                logger.info(f"🔧 模型: {data['model']}")
                logger.info(f"🔧 消息数: {len(messages)}")
                
                # 发送流式请求
                response = requests.post(url, headers=headers, json=data, stream=True)
                
                if response.status_code != 200:
                    logger.error(f"❌ HTTP 错误: {response.status_code}")
                    logger.error(f"响应: {response.text}")
                    continue
                
                # 处理流式响应
                full_response = ""
                chunk_count = 0
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data_str = line[6:]  # 移除 'data: ' 前缀
                            
                            if data_str.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                choices = chunk_data.get('choices', [])
                                
                                if choices:
                                    delta = choices[0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        full_response += content
                                        chunk_count += 1
                                        logger.debug(f"🔄 流式片段 {chunk_count}: '{content}'")
                                        
                            except json.JSONDecodeError as e:
                                logger.debug(f"⚠️ JSON 解析错误: {e}, 数据: {data_str}")
                
                logger.info(f"🌍 完整翻译结果: '{full_response}'")
                logger.info(f"📊 接收到 {chunk_count} 个流式片段")
                
                # 验证结果
                if full_response.strip():
                    # 检查是否包含预期内容（可选）
                    contains_expected = any(
                        expected in full_response 
                        for expected in test_case.get('expected_contains', [])
                    )
                    
                    if contains_expected:
                        logger.info(f"✅ 翻译结果包含预期内容")
                    else:
                        logger.info(f"ℹ️ 翻译结果未包含预期关键词（这是正常的）")
                    
                    success_count += 1
                    logger.info(f"✅ 测试案例 {i} 成功")
                else:
                    logger.error(f"❌ 测试案例 {i} 失败: 翻译结果为空")
                
                # 添加延迟避免API限制
                await asyncio.sleep(1)
            
            if success_count == len(test_cases):
                logger.info(f"✅ Groq LLM 测试完全成功 ({success_count}/{len(test_cases)})")
                return True
            else:
                logger.warning(f"⚠️ Groq LLM 测试部分成功 ({success_count}/{len(test_cases)})")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"❌ Groq LLM 测试失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False

    async def test_cartesia_tts(self) -> bool:
        """测试 Cartesia TTS"""
        logger.info("\n" + "="*50)
        logger.info("🔊 开始测试 Cartesia TTS")
        logger.info("="*50)
        
        if not self.cartesia_api_key:
            logger.error("❌ CARTESIA_API_KEY 未设置")
            return False
        
        try:
            # 测试用例
            test_cases = [
                {
                    "text": "안녕하세요, 세계!",
                    "language": "韩语",
                    "voice_id": "7d787990-4c3a-4766-9450-8c3ac6718b13",
                    "filename": "test_korean.wav"
                },
                {
                    "text": "こんにちは、世界！",
                    "language": "日语",
                    "voice_id": "95856005-0332-41b0-935f-352e296aa0df", 
                    "filename": "test_japanese.wav"
                }
            ]
            
            success_count = 0
            
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n🎵 测试案例 {i}: {test_case['language']} TTS")
                logger.info(f"🔤 文本: '{test_case['text']}'")
                logger.info(f"🎭 语音ID: {test_case['voice_id']}")
                
                # 准备请求
                url = "https://api.cartesia.ai/tts/bytes"
                headers = {
                    "Cartesia-Version": "2024-06-10",
                    "X-API-Key": self.cartesia_api_key,
                    "Content-Type": "application/json"
                }
                
                data = {
                    "model_id": "sonic-multilingual",
                    "transcript": test_case['text'],
                    "voice": {
                        "mode": "id",
                        "id": test_case['voice_id']
                    },
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 44100
                    }
                }
                
                logger.info(f"📡 调用 Cartesia API...")
                logger.info(f"🔧 模型: {data['model_id']}")
                
                # 发送请求
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 200:
                    # 保存音频文件
                    filename = test_case['filename']
                    with open(filename, 'wb') as f:
                        f.write(response.content)
                    
                    # 验证文件
                    file_size = os.path.getsize(filename)
                    logger.info(f"💾 音频文件已保存: {filename} ({file_size} bytes)")
                    
                    # 简单验证音频文件格式
                    try:
                        with wave.open(filename, 'rb') as wav_file:
                            frames = wav_file.getnframes()
                            sample_rate = wav_file.getframerate()
                            duration = frames / sample_rate
                            logger.info(f"🎵 音频信息: {duration:.2f}秒, {sample_rate}Hz, {frames} frames")
                    except Exception as wav_error:
                        logger.warning(f"⚠️ 音频文件格式验证失败: {wav_error}")
                    
                    success_count += 1
                    logger.info(f"✅ 测试案例 {i} 成功")
                    
                else:
                    logger.error(f"❌ 测试案例 {i} 失败: HTTP {response.status_code}")
                    logger.error(f"响应: {response.text}")
                
                # 添加延迟避免API限制
                await asyncio.sleep(1)
            
            if success_count == len(test_cases):
                logger.info(f"✅ Cartesia TTS 测试完全成功 ({success_count}/{len(test_cases)})")
                return True
            else:
                logger.warning(f"⚠️ Cartesia TTS 测试部分成功 ({success_count}/{len(test_cases)})")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"❌ Cartesia TTS 测试失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False

    async def test_livekit_connection(self) -> bool:
        """测试 LiveKit 连接"""
        logger.info("\n" + "="*50)
        logger.info("🔗 开始测试 LiveKit 连接")
        logger.info("="*50)
        
        if not all([self.livekit_api_key, self.livekit_api_secret, self.livekit_url]):
            logger.error("❌ LiveKit 环境变量未完整设置")
            return False
        
        try:
            # 这里可以添加 LiveKit 连接测试
            # 由于 LiveKit SDK 比较复杂，这里先做基础的 HTTP 健康检查
            
            logger.info(f"📡 检查 LiveKit 服务器: {self.livekit_url}")
            
            # 尝试连接到 LiveKit 服务器
            import urllib.parse
            parsed_url = urllib.parse.urlparse(self.livekit_url)
            health_url = f"{parsed_url.scheme}://{parsed_url.netloc}/health"
            
            response = requests.get(health_url, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ LiveKit 服务器健康检查通过")
                logger.info(f"📊 响应: {response.text}")
                return True
            else:
                logger.warning(f"⚠️ LiveKit 健康检查失败: HTTP {response.status_code}")
                logger.info(f"响应: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ LiveKit 连接测试失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            return False

    async def run_all_tests(self, tests_to_run: list) -> Dict[str, bool]:
        """运行所有测试"""
        logger.info("\n" + "🚀" + "="*48 + "🚀")
        logger.info("🚀 开始语音翻译流水线健康检查")
        logger.info("🚀" + "="*48 + "🚀")
        
        results = {}
        
        if 'deepgram' in tests_to_run:
            results['deepgram'] = await self.test_deepgram_stt()
        
        if 'groq' in tests_to_run:
            results['groq'] = await self.test_groq_llm()
        
        if 'tts' in tests_to_run:
            results['tts'] = await self.test_cartesia_tts()
        
        if 'livekit' in tests_to_run:
            results['livekit'] = await self.test_livekit_connection()
        
        # 输出总结
        logger.info("\n" + "📊" + "="*48 + "📊")
        logger.info("📊 测试结果总结")
        logger.info("📊" + "="*48 + "📊")
        
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{test_name.upper():>10}: {status}")
        
        logger.info(f"\n🎯 总体结果: {passed_tests}/{total_tests} 测试通过")
        
        if passed_tests == total_tests:
            logger.info("🎉 所有测试通过！语音翻译流水线健康状况良好")
        else:
            logger.warning("⚠️ 部分测试失败，请检查相关配置和服务")
        
        return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="语音翻译流水线健康检查")
    parser.add_argument("--deepgram", action="store_true", help="测试 Deepgram STT")
    parser.add_argument("--groq", action="store_true", help="测试 Groq LLM")
    parser.add_argument("--tts", action="store_true", help="测试 Cartesia TTS")
    parser.add_argument("--livekit", action="store_true", help="测试 LiveKit 连接")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 确定要运行的测试
    tests_to_run = []
    if args.all:
        tests_to_run = ['deepgram', 'groq', 'tts', 'livekit']
    else:
        if args.deepgram:
            tests_to_run.append('deepgram')
        if args.groq:
            tests_to_run.append('groq')
        if args.tts:
            tests_to_run.append('tts')
        if args.livekit:
            tests_to_run.append('livekit')
    
    if not tests_to_run:
        parser.print_help()
        sys.exit(1)
    
    # 运行测试
    checker = HealthChecker()
    results = asyncio.run(checker.run_all_tests(tests_to_run))
    
    # 退出码
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main() 