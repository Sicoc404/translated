import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Volume2, Mic, Settings, ArrowLeft } from 'lucide-react';
import { LiveKitRoom, TrackToggle, useConnectionState, useRoomInfo, RoomAudioRenderer, useRoomContext } from '@livekit/components-react';
import { Room, RoomOptions, RemoteTrack, DataPacket_Kind, ConnectionState, RoomEvent, RemoteParticipant, RemoteTrackPublication, Track } from 'livekit-client';

// LiveKit房间内部组件，用于访问room实例
function LiveKitRoomComponents({ 
  roomRef, 
  setIsConnected, 
  setAgentParticipant, 
  handleParticipantConnected, 
  handleDataReceived 
}: any) {
  const room = useRoomContext();
  
  useEffect(() => {
    if (!room) return;
    
    console.log('🎉 已连接到LiveKit房间:', room.name);
    console.log('🔍 房间详细信息:', {
      name: room.name,
      localParticipant: room.localParticipant?.identity,
      participants: Array.from(room.participants.keys())
    });
    
    roomRef.current = room;
    setIsConnected(true);
    
    // 监听本地participant的track发布事件
    room.localParticipant.on('trackPublished', (publication: any) => {
      console.log('📤 本地track已发布:', {
        kind: publication.kind,
        source: publication.source,
        trackSid: publication.trackSid,
        enabled: publication.track?.enabled,
        muted: publication.track?.muted
      });
    });
    
    // 监听本地participant的track取消发布事件
    room.localParticipant.on('trackUnpublished', (publication: any) => {
      console.log('📤❌ 本地track已取消发布:', publication.kind);
    });
    
    // 监听远程参与者事件
    room.on(RoomEvent.ParticipantConnected, handleParticipantConnected);
    room.participants.forEach(participant => {
      handleParticipantConnected(participant);
    });
    
    // 监听数据接收
    room.on(RoomEvent.DataReceived, handleDataReceived);
    
    room.on(RoomEvent.ConnectionStateChanged, (state: any) => {
      console.log('🔗 房间连接状态变化:', state);
      if (state === ConnectionState.Disconnected) {
        setIsConnected(false);
        setAgentParticipant(null);
      }
    });
    
         // 检查麦克风track
     setTimeout(() => {
       const micTrack = room.localParticipant.getTrack(Track.Source.Microphone);
       console.log('🎤 当前麦克风track状态:', {
         hasTrack: !!micTrack,
         enabled: micTrack?.track ? !micTrack.track.isMuted : false,
         muted: micTrack?.track?.isMuted,
         publication: micTrack ? {
           trackSid: micTrack.trackSid,
           subscribed: micTrack.isSubscribed
         } : null
       });
     }, 1000);
    
  }, [room]);
  
  return null;
}

export default function PrymeUI() {
  // 状态变量
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [token, setToken] = useState('');
  const [liveKitUrl, setLiveKitUrl] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [subtitle, setSubtitle] = useState('');
  const [volume, setVolume] = useState(0.8);
  const [isPlaying, setIsPlaying] = useState(true);
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
      const identity = `listener-${Date.now()}`;
      
      console.log(`正在获取房间 ${roomName} 的token...`);
      
      // 调用后端API获取token
      const tokenServerUrl = import.meta.env.VITE_TOKEN_SERVER_URL || 'https://translated-backend.onrender.com';
      const response = await fetch(`${tokenServerUrl}/api/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          room: roomName,
          identity: identity
        })
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      console.log('成功获取token:', data);
      setToken(data.token);
      setLiveKitUrl(data.livekit_url);
      setSelectedRoom(language);
      
    } catch (error) {
      console.error('获取房间token失败:', error);
      alert(`连接房间失败: ${error.message}。请检查后端服务是否正常运行。`);
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
        console.log('调用RPC: start_translation');
        const result = await room.localParticipant.rpc(
          agentParticipant.identity, 
          'start_translation'
        );
        console.log('RPC结果:', result);
        setIsTranslating(true);
      } else {
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
  const handleRoomConnected = () => {
    // 延迟获取room实例，因为onConnected不传递room参数
    setTimeout(() => {
      const room = roomRef.current;
      if (!room) return;
      
      console.log('🎉 已连接到LiveKit房间:', room.name);
      console.log('🔍 房间详细信息:', {
        name: room.name,
        localParticipant: room.localParticipant?.identity,
        participants: Array.from(room.participants.keys())
      });
      
      setIsConnected(true);
      
      // 监听本地participant的track发布事件
      room.localParticipant.on('trackPublished', (publication: any) => {
        console.log('📤 本地track已发布:', {
          kind: publication.kind,
          source: publication.source,
          trackSid: publication.trackSid,
          enabled: publication.track?.enabled,
          muted: publication.track?.muted
        });
      });
      
      // 监听本地participant的track取消发布事件
      room.localParticipant.on('trackUnpublished', (publication: any) => {
        console.log('📤❌ 本地track已取消发布:', publication.kind);
      });
      
      // 监听麦克风权限和状态
      room.localParticipant.on('permissionChanged', (permission: any) => {
        console.log('🎤 权限变化:', permission);
      });
      
      // 监听远程参与者事件
      room.on(RoomEvent.ParticipantConnected, handleParticipantConnected);
      room.participants.forEach(participant => {
        handleParticipantConnected(participant);
      });
      
      // 监听数据接收
      room.on(RoomEvent.DataReceived, handleDataReceived);
      
      room.on(RoomEvent.ConnectionStateChanged, (state: any) => {
        console.log('🔗 房间连接状态变化:', state);
        if (state === ConnectionState.Disconnected) {
          setIsConnected(false);
          setAgentParticipant(null);
        }
      });
      
      // 立即检查是否有麦克风track
      setTimeout(() => {
        const micTrack = room.localParticipant.getTrack(Track.Source.Microphone);
        console.log('🎤 当前麦克风track状态:', {
          hasTrack: !!micTrack,
          enabled: micTrack?.track?.enabled,
          muted: micTrack?.track?.muted,
          publication: micTrack ? {
            trackSid: micTrack.trackSid,
            subscribed: micTrack.subscribed
          } : null
        });
      }, 1000);
    }, 100);
  };

  // 处理参与者加入
  const handleParticipantConnected = (participant: any) => {
    console.log('👥 参与者加入:', {
      identity: participant.identity,
      kind: participant.kind,
      tracks: Array.from(participant.tracks.keys())
    });
    
    if (participant.identity.includes('translator') || participant.identity.includes('agent')) {
      console.log('🤖 找到翻译代理:', participant.identity);
      setAgentParticipant(participant);
      
      // 监听track订阅事件
      participant.on('trackSubscribed', (track: any, publication: any) => {
        console.log('📥 Agent track已订阅:', {
          kind: track.kind,
          source: publication.source,
          trackSid: publication.trackSid
        });
        handleTrackSubscribed(track, publication);
      });
      
      participant.on('trackUnsubscribed', (track: any) => {
        console.log('📥❌ Agent track已取消订阅:', track.kind);
        handleTrackUnsubscribed(track);
      });
      
      // 检查已有tracks
      participant.tracks.forEach((publication: any) => {
        console.log('🔍 检查现有Agent track:', {
          kind: publication.kind,
          subscribed: publication.subscribed,
          track: !!publication.track
        });
        if (publication.track) {
          handleTrackSubscribed(publication.track, publication);
        }
      });
    }
  };

  // 处理轨道订阅
  const handleTrackSubscribed = (track: any, publication: any) => {
    console.log('📥 订阅到新轨道:', {
      kind: track.kind,
      source: publication?.source,
      enabled: track.enabled,
      muted: track.muted
    });
    
    if (track.kind === Track.Kind.Audio) {
      console.log('🔊 处理音频轨道...');
      try {
        const audioElement = track.attach();
        audioRef.current = audioElement;
        audioElement.volume = volume;
        
        // 添加音频事件监听
        audioElement.addEventListener('play', () => {
          console.log('🔊✅ 音频开始播放');
        });
        
        audioElement.addEventListener('pause', () => {
          console.log('🔊⏸️ 音频暂停');
        });
        
        audioElement.addEventListener('ended', () => {
          console.log('🔊🔚 音频播放结束');
        });
        
        audioElement.addEventListener('error', (e: any) => {
          console.error('🔊❌ 音频播放错误:', e);
        });
        
        audioElement.play().then(() => {
          console.log('🔊🎵 音频播放成功启动');
          setIsPlaying(true);
        }).catch((e: any) => {
          console.error('🔊❌ 音频自动播放失败:', e);
        });
        
      } catch (error) {
        console.error('🔊❌ 音频track处理失败:', error);
      }
    }
  };

  // 处理轨道取消订阅
  const handleTrackUnsubscribed = (track: any) => {
    console.log('取消订阅轨道:', track.kind);
    track.detach();
  };

  // 处理数据消息
  const handleDataReceived = (e: any) => {
    try {
      const decoder = new TextDecoder();
      const message = decoder.decode(e.payload);
      console.log('📨 收到数据消息:', {
        sender: e.participant?.identity,
        messageLength: message.length,
        message: message.substring(0, 100) + (message.length > 100 ? '...' : '')
      });
      
      // 尝试解析JSON
      try {
        const jsonData = JSON.parse(message);
        console.log('📋 解析JSON数据:', jsonData);
        
        if (jsonData.type === 'translation' || jsonData.type === 'transcript') {
          setSubtitle(jsonData.text || jsonData.content || message);
          console.log('📺 更新字幕:', jsonData.text || jsonData.content);
        } else {
          setSubtitle(message);
        }
      } catch (parseError) {
        // 如果不是JSON，直接作为纯文本处理
        console.log('📝 纯文本消息:', message);
        setSubtitle(message);
      }
    } catch (error) {
      console.error('❌ 处理数据消息失败:', error);
    }
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

  // 样式定义
  const containerStyle: React.CSSProperties = {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #581c87 0%, #6d28d9 50%, #5b21b6 100%)',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    overflow: 'hidden'
  };

  const backgroundOverlay1: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to top, rgba(88, 28, 135, 0.5), transparent, rgba(109, 40, 217, 0.3))',
    zIndex: 1
  };

  const backgroundOverlay2: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to bottom left, rgba(30, 58, 138, 0.2), transparent, rgba(131, 24, 67, 0.2))',
    zIndex: 1
  };

  const backgroundOverlay3: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to right, transparent, rgba(139, 92, 246, 0.1), transparent)',
    zIndex: 1
  };

  const animatedBgContainer: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    opacity: 0.2,
    zIndex: 2
  };

  const pulseAnimation = `
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    @keyframes ping {
      75%, 100% {
        transform: scale(2);
        opacity: 0;
      }
    }
  `;

  return (
    <>
      <style>{pulseAnimation}</style>
      <div style={containerStyle}>
        {/* Multi-layer Background */}
        <div style={backgroundOverlay1}></div>
        <div style={backgroundOverlay2}></div>
        <div style={backgroundOverlay3}></div>
        
        {/* Animated Background Layers */}
        <div style={animatedBgContainer}>
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            background: 'linear-gradient(to right, rgba(139, 92, 246, 0.3), transparent, transparent)',
            animation: 'pulse 2s infinite'
          }}></div>
          <div style={{
            position: 'absolute',
            top: '80px',
            left: '80px',
            width: '256px',
            height: '256px',
            background: 'linear-gradient(to right, rgba(59, 130, 246, 0.2), rgba(139, 92, 246, 0.1), transparent)',
            borderRadius: '50%',
            filter: 'blur(64px)',
            animation: 'pulse 4s infinite'
          }}></div>
          <div style={{
            position: 'absolute',
            top: '240px',
            right: '160px',
            width: '320px',
            height: '320px',
            background: 'linear-gradient(to right, rgba(236, 72, 153, 0.2), rgba(139, 92, 246, 0.1), transparent)',
            borderRadius: '50%',
            filter: 'blur(64px)',
            animation: 'pulse 6s infinite'
          }}></div>
          <div style={{
            position: 'absolute',
            bottom: '160px',
            left: '240px',
            width: '192px',
            height: '192px',
            background: 'linear-gradient(to right, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.1), transparent)',
            borderRadius: '50%',
            filter: 'blur(40px)',
            animation: 'pulse 3s infinite'
          }}></div>
        </div>
        
        {/* Connection Status */}
        <div style={{
          position: 'absolute',
          top: '24px',
          left: '24px',
          zIndex: 10
        }}>
          <div style={{
            padding: '12px 24px',
            background: 'rgba(255, 255, 255, 0.2)',
            backdropFilter: 'blur(12px)',
            color: 'white',
            borderRadius: '9999px',
            fontWeight: '600',
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            border: '1px solid rgba(255, 255, 255, 0.2)'
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isConnected ? '#4ade80' : '#f87171',
              animation: isConnected ? 'pulse 2s infinite' : 'none'
            }}></div>
            <span>{isConnected ? 'LiveKit 已连接' : '未连接'}</span>
          </div>
        </div>
        
        {/* Header with Logo */}
        <header style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          paddingTop: '32px',
          paddingBottom: '24px',
          position: 'relative',
          zIndex: 10
        }}>
          <div style={{ position: 'relative' }}>
            {/* Animated Golden Ring */}
            <div style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '4px solid #fbbf24',
              animation: 'pulse 2s infinite',
              boxShadow: '0 10px 25px rgba(251, 191, 36, 0.5)'
            }}></div>
            <div style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              border: '2px solid #fde047',
              animation: 'spin 10s linear infinite'
            }}></div>
            
            {/* Logo Text */}
            <div style={{
              position: 'relative',
              padding: '24px 48px',
              background: 'linear-gradient(to right, #6b21a8, #581c87)',
              borderRadius: '50%',
              boxShadow: '0 25px 50px rgba(0, 0, 0, 0.25)'
            }}>
              <h1 style={{
                fontSize: '4rem',
                fontWeight: 'bold',
                background: 'linear-gradient(to right, #e9d5ff, #ffffff)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                color: 'transparent',
                animation: 'pulse 2s infinite',
                margin: 0
              }}>
                Pryme+
              </h1>
              {/* Sparkle Effect */}
              <div style={{
                position: 'absolute',
                top: '8px',
                right: '16px',
                width: '8px',
                height: '8px',
                backgroundColor: '#fbbf24',
                borderRadius: '50%',
                animation: 'ping 2s infinite'
              }}></div>
              <div style={{
                position: 'absolute',
                bottom: '12px',
                left: '24px',
                width: '4px',
                height: '4px',
                backgroundColor: '#fde047',
                borderRadius: '50%',
                animation: 'ping 2s infinite'
              }}></div>
            </div>
          </div>
        </header>

        {/* Main Content Container */}
        <main style={{
          flex: 1,
          maxWidth: '1152px',
          margin: '0 auto',
          width: '100%',
          padding: '32px 16px',
          position: 'relative',
          zIndex: 10
        }}>
          {!selectedRoom ? (
            /* Language Room Selection */
            <section style={{ marginBottom: '48px' }}>
              <h2 style={{
                fontSize: '20px',
                fontWeight: '600',
                color: 'rgba(255, 255, 255, 0.9)',
                marginBottom: '24px',
                textAlign: 'center'
              }}>语言房间选择</h2>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '16px',
                maxWidth: '800px',
                margin: '0 auto'
              }}>
                {languages.map((item, index) => (
                  <div 
                    key={index} 
                    onClick={() => joinRoom(item)}
                    style={{
                      position: 'relative',
                      zIndex: 10,
                      background: 'white',
                      borderRadius: '16px',
                      padding: '24px',
                      boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                      transition: 'all 0.3s ease',
                      cursor: 'pointer',
                      border: '2px solid #f3f4f6'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.transform = 'scale(1.05)';
                      e.currentTarget.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.25)';
                      e.currentTarget.style.borderColor = '#c084fc';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'scale(1)';
                      e.currentTarget.style.boxShadow = '0 10px 25px rgba(0, 0, 0, 0.1)';
                      e.currentTarget.style.borderColor = '#f3f4f6';
                    }}
                  >
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '48px', marginBottom: '8px' }}>{item.flag}</div>
                      <div style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937' }}>{item.name}</div>
                      <div style={{ fontSize: '14px', color: '#6b7280', marginTop: '4px' }}>{item.lang}</div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : (
            /* Room Content */
            <div>
              {/* Back Button */}
              <div style={{ marginBottom: '32px', display: 'flex', alignItems: 'center' }}>
                <button 
                  onClick={disconnect}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 16px',
                    background: 'rgba(255, 255, 255, 0.2)',
                    backdropFilter: 'blur(12px)',
                    color: 'white',
                    borderRadius: '9999px',
                    fontWeight: '600',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                    border: '1px solid rgba(255, 255, 255, 0.2)',
                    cursor: 'pointer',
                    transition: 'all 0.3s ease'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.3)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)';
                  }}
                >
                  <ArrowLeft style={{ width: '16px', height: '16px' }} />
                  <span>返回语言选择</span>
                </button>
              </div>

              {/* Current Room Display */}
              <div style={{ marginBottom: '32px', textAlign: 'center' }}>
                <div style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '16px',
                  padding: '12px 24px',
                  background: 'rgba(255, 255, 255, 0.2)',
                  backdropFilter: 'blur(12px)',
                  color: 'white',
                  borderRadius: '9999px',
                  fontWeight: '600',
                  boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.2)'
                }}>
                  <div style={{ fontSize: '32px' }}>{selectedRoom.flag}</div>
                  <span style={{ fontSize: '18px' }}>{selectedRoom.name} 房间</span>
                </div>
              </div>

              {/* Subtitle Display Area */}
              <section style={{ marginBottom: '48px' }}>
                <div style={{
                  position: 'relative',
                  zIndex: 10,
                  background: 'white',
                  borderRadius: '24px',
                  boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                  padding: '32px',
                  maxWidth: '800px',
                  margin: '0 auto',
                  border: '2px solid #f3f4f6'
                }}>
                  <h2 style={{
                    fontSize: '20px',
                    fontWeight: '600',
                    color: '#1f2937',
                    marginBottom: '24px',
                    textAlign: 'center'
                  }}>字幕显示区</h2>
                  <div style={{
                    background: '#f9fafb',
                    borderRadius: '16px',
                    padding: '32px',
                    minHeight: '200px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {subtitle ? (
                      <div style={{ textAlign: 'center' }}>
                        <p style={{ fontSize: '18px', color: '#1f2937', marginBottom: '8px' }}>{subtitle}</p>
                        <p style={{ fontSize: '14px', color: '#6b7280' }}>当前语言: {selectedRoom.lang}</p>
                      </div>
                    ) : (
                      <div style={{ textAlign: 'center', color: '#9ca3af' }}>
                        <div style={{ fontSize: '64px', marginBottom: '16px' }}>📺</div>
                        <p style={{ fontSize: '18px' }}>实时翻译字幕将在此显示</p>
                        <p style={{ fontSize: '14px', marginTop: '8px' }}>当前语言: {selectedRoom.lang}</p>
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* Audio Control Bar */}
              <section style={{ marginBottom: '48px' }}>
                <div style={{
                  position: 'relative',
                  zIndex: 10,
                  background: 'white',
                  borderRadius: '24px',
                  boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                  padding: '24px',
                  maxWidth: '800px',
                  margin: '0 auto',
                  border: '2px solid #f3f4f6'
                }}>
                  <h2 style={{
                    fontSize: '20px',
                    fontWeight: '600',
                    color: '#1f2937',
                    marginBottom: '24px',
                    textAlign: 'center'
                  }}>音频播放控制</h2>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '24px'
                  }}>
                    <button 
                      onClick={togglePlayPause}
                      style={{
                        padding: '16px',
                        background: '#ede9fe',
                        borderRadius: '50%',
                        border: 'none',
                        cursor: 'pointer',
                        transition: 'all 0.3s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = '#ddd6fe';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = '#ede9fe';
                      }}
                    >
                      {isPlaying ? (
                        <Pause style={{ width: '24px', height: '24px', color: '#6d28d9' }} />
                      ) : (
                        <Play style={{ width: '24px', height: '24px', color: '#6d28d9' }} />
                      )}
                    </button>
                    <div style={{ flex: 1, maxWidth: '300px', margin: '0 16px' }}>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={handleVolumeChange}
                        style={{
                          width: '100%',
                          height: '8px',
                          background: '#e5e7eb',
                          borderRadius: '4px',
                          appearance: 'none',
                          cursor: 'pointer'
                        }}
                      />
                    </div>
                    <button style={{
                      padding: '16px',
                      background: '#ede9fe',
                      borderRadius: '50%',
                      border: 'none',
                      cursor: 'pointer'
                    }}>
                      <Volume2 style={{ width: '24px', height: '24px', color: '#6d28d9' }} />
                    </button>
                  </div>
                </div>
              </section>

              {/* Translation Control Area */}
              <section style={{ marginBottom: '32px' }}>
                <h2 style={{
                  fontSize: '20px',
                  fontWeight: '600',
                  color: 'rgba(255, 255, 255, 0.9)',
                  marginBottom: '24px',
                  textAlign: 'center'
                }}>翻译控制区域</h2>



                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  justifyContent: 'center',
                  alignItems: 'center',
                  maxWidth: '500px',
                  margin: '0 auto'
                }}>
                  <button 
                    onClick={toggleTranslation}
                    disabled={!isConnected || !agentParticipant}
                    style={{
                      position: 'relative',
                      padding: '16px 32px',
                      background: !isConnected ? '#6b7280' : 
                        isTranslating ? '#dc2626' : 'linear-gradient(to right, #7c3aed, #6d28d9)',
                      color: 'white',
                      borderRadius: '16px',
                      fontWeight: '600',
                      boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                      border: 'none',
                      cursor: (!isConnected || !agentParticipant) ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      transition: 'all 0.3s ease',
                      opacity: (!isConnected || !agentParticipant) ? 0.5 : 1
                    }}
                  >
                    <Settings style={{ width: '20px', height: '20px' }} />
                    <span>{isTranslating ? '停止实时翻译' : '启动实时翻译'}</span>
                  </button>
                  
                  <button style={{
                    padding: '16px 32px',
                    background: 'white',
                    color: '#7c3aed',
                    borderRadius: '16px',
                    fontWeight: '600',
                    boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)',
                    border: '2px solid #c084fc',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    transition: 'all 0.3s ease'
                  }}>
                    <Settings style={{ width: '20px', height: '20px' }} />
                    <span>设置选项</span>
                  </button>
                </div>
              </section>

              {/* LiveKit Connection */}
              {token && (
                <LiveKitRoom
                  token={token}
                  serverUrl={liveKitUrl || 'wss://your-livekit-url.livekit.cloud'}
                  options={{
                    adaptiveStream: true,
                    dynacast: true,
                  }}
                  onConnected={handleRoomConnected}
                  onDisconnected={() => {
                    console.log('🔌 已断开LiveKit房间连接');
                    setIsConnected(false);
                    setAgentParticipant(null);
                  }}
                >
                  <LiveKitRoomComponents 
                    roomRef={roomRef}
                    setIsConnected={setIsConnected}
                    setAgentParticipant={setAgentParticipant}
                    handleParticipantConnected={handleParticipantConnected}
                    handleDataReceived={handleDataReceived}
                  />
                  {/* Microphone Toggle in Top Right Corner */}
                  <div style={{
                    position: 'fixed',
                    top: '24px',
                    right: '24px',
                    zIndex: 1000
                  }}>
                    <div style={{
                      padding: '12px',
                      background: 'rgba(255, 255, 255, 0.2)',
                      backdropFilter: 'blur(12px)',
                      borderRadius: '50%',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      boxShadow: '0 10px 25px rgba(0, 0, 0, 0.1)'
                    }}>
                      <TrackToggle 
                        source={Track.Source.Microphone}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'white',
                          cursor: 'pointer',
                          width: '24px',
                          height: '24px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                      />
                    </div>
                  </div>
                                      {/* 自动播放房间内所有音频轨道 */}
                    <RoomAudioRenderer />
                    {/* 添加调试信息显示 */}
                    <div style={{ position: 'fixed', bottom: '20px', right: '20px', background: 'rgba(0,0,0,0.7)', color: 'white', padding: '10px', borderRadius: '8px', fontSize: '12px', zIndex: 1000 }}>
                      <div>🔗 连接状态: {isConnected ? '已连接' : '未连接'}</div>
                      <div>🤖 Agent: {agentParticipant ? agentParticipant.identity : '未找到'}</div>
                      <div>📺 字幕: {subtitle ? '有内容' : '无内容'}</div>
                    </div>
                </LiveKitRoom>
              )}
            </div>
          )}
        </main>

        {/* Footer */}
        <footer style={{
          padding: '24px',
          textAlign: 'center',
          fontSize: '14px',
          position: 'relative',
          zIndex: 10
        }}>
          <p style={{ color: 'rgba(255, 255, 255, 0.8)', fontWeight: '500', margin: 0 }}>
            © 2025 Pryme+ | 实时语音翻译系统
          </p>
        </footer>
      </div>
    </>
  );
}
