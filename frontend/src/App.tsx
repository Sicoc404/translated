import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Volume2, Mic, Settings, ArrowLeft } from 'lucide-react';
import { LiveKitRoom } from '@livekit/components-react';
import { Room, RoomOptions, RemoteTrack, DataPacket_Kind, ConnectionState, RoomEvent, RemoteParticipant, RemoteTrackPublication, Track } from 'livekit-client';

export default function PrymeUI() {
  // 状态变量
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [token, setToken] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [subtitle, setSubtitle] = useState('');
  const [volume, setVolume] = useState(0.8); // 音量控制，范围0-1
  const [isPlaying, setIsPlaying] = useState(true); // 音频播放状态
  const [agentParticipant, setAgentParticipant] = useState<any>(null);
  
  // 引用
  const roomRef = useRef<any>(null);
  const audioRef = useRef<any>(null);
  
  // 语言房间配置
  const languages = [
    { lang: '한국어', flag: '🇰🇷', name: '韩语', id: 'korean', roomName: 'Pryme-Korean' },
    { lang: '日本語', flag: '🇯🇵', name: '日语', id: 'japanese', roomName: 'Pryme-Japanese' },
    { lang: 'Tiếng Việt', flag: '🇻🇳', name: '越南语', id: 'vietnamese', roomName: 'Pryme-Vietnamese' },
    { lang: 'Bahasa Melayu', flag: '🇲🇾', name: '马来语', id: 'malay', roomName: 'Pryme-Malay' }
  ];

  // 获取房间token的函数
  const joinRoom = async (language: any) => {
    try {
      const roomName = language.roomName;
      // 模拟token获取，实际应该调用后端API
      const mockToken = `mock-token-${roomName}-${Date.now()}`;
      setToken(mockToken);
      setSelectedRoom(language);
      console.log(`正在加入房间: ${roomName}`);
    } catch (error) {
      console.error('获取房间token失败:', error);
      alert('连接房间失败，请稍后重试');
    }
  };
  
  // 控制翻译开始/停止
  const toggleTranslation = async () => {
    if (!isConnected || !roomRef.current || !agentParticipant) {
      console.error('房间未连接或未找到翻译代理');
      return;
    }
    
    try {
      const room = roomRef.current;
      
      if (!isTranslating) {
        // 开始翻译
        console.log('调用RPC: start_translation');
        const result = await room.localParticipant.rpc(
          agentParticipant.identity, 
          'start_translation'
        );
        console.log('RPC结果:', result);
        setIsTranslating(true);
      } else {
        // 停止翻译
        console.log('调用RPC: stop_translation');
        const result = await room.localParticipant.rpc(
          agentParticipant.identity, 
          'stop_translation'
        );
        console.log('RPC结果:', result);
        setIsTranslating(false);
      }
    } catch (error) {
      console.error('控制翻译失败:', error);
      alert('控制翻译失败，请稍后重试');
    }
  };

  // 音频控制函数
  const togglePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleVolumeChange = (e: any) => {
    const newVolume = e.target.value;
    setVolume(newVolume);
    if (audioRef.current) {
      audioRef.current.volume = newVolume;
    }
  };

  // 处理房间连接
  const handleRoomConnected = (room: any) => {
    console.log('已连接到LiveKit房间:', room.name);
    roomRef.current = room;
    setIsConnected(true);
    
    // 监听参与者加入
    room.on(RoomEvent.ParticipantConnected, handleParticipantConnected);
    
    // 检查已有参与者
    room.participants.forEach(participant => {
      handleParticipantConnected(participant);
    });
    
    // 监听连接状态变化
    room.on(RoomEvent.ConnectionStateChanged, (state: any) => {
      console.log('房间连接状态变化:', state);
      if (state === ConnectionState.Disconnected || state === ConnectionState.Failed) {
        setIsConnected(false);
        setAgentParticipant(null);
      }
    });
  };

  // 处理参与者加入
  const handleParticipantConnected = (participant: any) => {
    console.log('参与者加入:', participant.identity);
    
    // 检查是否是翻译代理
    if (participant.identity.includes('translator')) {
      console.log('找到翻译代理:', participant.identity);
      setAgentParticipant(participant);
      
      // 订阅参与者的轨道
      participant.on('trackSubscribed', handleTrackSubscribed);
      participant.on('trackUnsubscribed', handleTrackUnsubscribed);
      
      // 检查已有轨道
      participant.tracks.forEach(publication => {
        if (publication.track) {
          handleTrackSubscribed(publication.track, publication);
        }
      });
    }
  };

  // 处理轨道订阅
  const handleTrackSubscribed = (track: any, publication: any) => {
    console.log('订阅轨道:', track.kind);
    
    if (track.kind === Track.Kind.Audio) {
      const audioElement = track.attach();
      audioRef.current = audioElement;
      audioElement.volume = volume;
      audioElement.play();
      setIsPlaying(true);
    }
  };

  // 处理轨道取消订阅
  const handleTrackUnsubscribed = (track: any) => {
    console.log('取消订阅轨道:', track.kind);
    track.detach();
  };

  // 处理数据消息
  const handleDataReceived = (e: any) => {
    const decoder = new TextDecoder();
    const message = decoder.decode(e.payload);
    console.log('收到翻译数据:', message);
    setSubtitle(message);
  };

  // 断开连接
  const disconnect = () => {
    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }
    setSelectedRoom(null);
    setToken('');
    setIsConnected(false);
    setAgentParticipant(null);
    setSubtitle('');
    setIsTranslating(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-purple-800 to-purple-700 flex flex-col relative overflow-hidden">
      {/* Multi-layer Background */}
      <div className="absolute inset-0 bg-gradient-to-t from-purple-900/50 via-transparent to-purple-600/30"></div>
      <div className="absolute inset-0 bg-gradient-to-bl from-blue-900/20 via-transparent to-pink-900/20"></div>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-purple-500/10 to-transparent"></div>
      
      {/* Animated Background Layers */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-r from-purple-400/30 via-transparent to-transparent animate-pulse"></div>
        <div className="absolute top-20 left-20 w-64 h-64 bg-gradient-to-r from-blue-400/20 via-purple-400/10 to-transparent rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute top-60 right-40 w-80 h-80 bg-gradient-to-r from-pink-400/20 via-purple-400/10 to-transparent rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-40 left-60 w-48 h-48 bg-gradient-to-r from-indigo-400/20 via-purple-400/10 to-transparent rounded-full blur-2xl animate-pulse"></div>
      </div>
      
      {/* Connection Status Indicator */}
      <div className="absolute top-6 left-6 z-10">
        <div className={`px-6 py-3 bg-white/20 backdrop-blur-md text-white rounded-full font-semibold shadow-lg flex items-center space-x-2 border border-white/20`}>
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
          <span>{isConnected ? 'LiveKit 已连接' : '未连接'}</span>
        </div>
      </div>
      
      {/* Header with Logo */}
      <header className="flex justify-center items-center pt-8 pb-6 relative z-10">
        <div className="relative">
          {/* Animated Golden Ring */}
          <div className="absolute inset-0 rounded-full border-4 border-yellow-400 animate-pulse shadow-lg shadow-yellow-400/50"></div>
          <div className="absolute inset-0 rounded-full border-2 border-yellow-300 animate-spin"></div>
          
          {/* Logo Text */}
          <div className="relative px-12 py-6 bg-gradient-to-r from-purple-800 to-purple-900 rounded-full shadow-2xl">
            <h1 className="text-4xl md:text-6xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-200 to-white animate-pulse">
              Pryme+
            </h1>
            {/* Sparkle Effect */}
            <div className="absolute top-2 right-4 w-2 h-2 bg-yellow-400 rounded-full animate-ping"></div>
            <div className="absolute bottom-3 left-6 w-1 h-1 bg-yellow-300 rounded-full animate-ping"></div>
          </div>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8 relative z-10">
        {!selectedRoom ? (
          /* Language Room Selection */
          <section className="mb-12">
            <h2 className="text-xl font-semibold text-white/90 mb-6 text-center">语言房间选择</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
              {languages.map((item, index) => (
                <div 
                  key={index} 
                  onClick={() => joinRoom(item)}
                  className="relative z-10 bg-white rounded-2xl p-6 shadow-lg hover:shadow-xl transition-all duration-300 cursor-pointer hover:scale-105 border-2 border-gray-100 hover:border-purple-200"
                >
                  <div className="text-center">
                    <div className="text-3xl mb-2">{item.flag}</div>
                    <div className="text-lg font-medium text-gray-800">{item.name}</div>
                    <div className="text-sm text-gray-500 mt-1">{item.lang}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          /* Room Content */
          <div>
            {/* Back Button */}
            <div className="mb-8 flex items-center">
              <button 
                onClick={disconnect}
                className="flex items-center space-x-2 px-4 py-2 bg-white/20 backdrop-blur-md text-white rounded-full font-semibold shadow-lg hover:bg-white/30 transition-all duration-300 border border-white/20"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>返回语言选择</span>
              </button>
            </div>

            {/* Current Room Display */}
            <div className="mb-8 text-center">
              <div className="inline-flex items-center space-x-4 px-6 py-3 bg-white/20 backdrop-blur-md text-white rounded-full font-semibold shadow-lg border border-white/20">
                <div className="text-2xl">{selectedRoom.flag}</div>
                <span className="text-lg">{selectedRoom.name} 房间</span>
              </div>
            </div>

            {/* Subtitle Display Area */}
            <section className="mb-12">
              <div className="relative z-10 bg-white rounded-3xl shadow-lg p-8 max-w-4xl mx-auto border-2 border-gray-100">
                <h2 className="text-xl font-semibold text-gray-800 mb-6 text-center">字幕显示区</h2>
                <div className="bg-gray-50 rounded-2xl p-8 min-h-[200px] flex items-center justify-center">
                  {subtitle ? (
                    <div className="text-center">
                      <p className="text-lg text-gray-800 mb-2">{subtitle}</p>
                      <p className="text-sm text-gray-500">当前语言: {selectedRoom.lang}</p>
                    </div>
                  ) : (
                    <div className="text-center text-gray-400">
                      <div className="text-6xl mb-4">📺</div>
                      <p className="text-lg">实时翻译字幕将在此显示</p>
                      <p className="text-sm mt-2">当前语言: {selectedRoom.lang}</p>
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Audio Control Bar */}
            <section className="mb-12">
              <div className="relative z-10 bg-white rounded-3xl shadow-lg p-6 max-w-4xl mx-auto border-2 border-gray-100">
                <h2 className="text-xl font-semibold text-gray-800 mb-6 text-center">音频播放控制</h2>
                <div className="flex items-center justify-center space-x-6">
                  <button 
                    onClick={togglePlayPause}
                    className="p-4 bg-purple-100 rounded-full hover:bg-purple-200 transition-colors"
                  >
                    {isPlaying ? (
                      <Pause className="w-6 h-6 text-purple-700" />
                    ) : (
                      <Play className="w-6 h-6 text-purple-700" />
                    )}
                  </button>
                  <div className="flex-1 max-w-md mx-4">
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={volume}
                      onChange={handleVolumeChange}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                    />
                  </div>
                  <button className="p-4 bg-purple-100 rounded-full hover:bg-purple-200 transition-colors">
                    <Volume2 className="w-6 h-6 text-purple-700" />
                  </button>
                </div>
              </div>
            </section>

            {/* Translation Control Area */}
            <section className="mb-8">
              <h2 className="text-xl font-semibold text-white/90 mb-6 text-center">翻译控制区域</h2>
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center max-w-2xl mx-auto">
                <button 
                  onClick={toggleTranslation}
                  disabled={!isConnected || !agentParticipant}
                  className={`group relative px-8 py-4 ${
                    !isConnected ? 'bg-gray-500' : 
                    isTranslating ? 'bg-red-600' : 'bg-gradient-to-r from-purple-600 to-purple-700'
                  } text-white rounded-2xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 flex items-center space-x-3 disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  <Mic className="w-5 h-5" />
                  <span>{isTranslating ? '停止实时翻译' : '启动实时翻译'}</span>
                </button>
                
                <button className="px-8 py-4 bg-white text-purple-700 rounded-2xl font-semibold shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-105 border-2 border-purple-200 hover:border-purple-300 flex items-center space-x-3">
                  <Settings className="w-5 h-5" />
                  <span>设置选项</span>
                </button>
              </div>
            </section>

            {/* LiveKit Connection */}
            {token && (
              <LiveKitRoom
                token={token}
                serverUrl={process.env.VITE_LIVEKIT_URL || 'wss://your-livekit-url.livekit.cloud'}
                options={{
                  adaptiveStream: true,
                  dynacast: true,
                }}
                onConnected={handleRoomConnected}
                onDisconnected={() => {
                  console.log('已断开LiveKit房间连接');
                  setIsConnected(false);
                  setAgentParticipant(null);
                }}
              />
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-6 text-center text-gray-500 text-sm relative z-10">
        <p className="text-white/80 font-medium">© 2025 Pryme+ | 实时语音翻译系统</p>
      </footer>
    </div>
  );
}
