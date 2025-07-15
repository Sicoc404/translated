import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:http/http.dart' as http;

void main() async {
  // 确保Flutter初始化
  WidgetsFlutterBinding.ensureInitialized();
  
  // 加载环境变量（可选，如果有.env文件）
  try {
    await dotenv.load();
  } catch (e) {
    print('未找到.env文件，将使用硬编码URL');
  }
  
  runApp(const PrymeTranslationApp());
}

class PrymeTranslationApp extends StatelessWidget {
  const PrymeTranslationApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pryme+ 实时翻译',
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
        brightness: Brightness.light,
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      darkTheme: ThemeData(
        primarySwatch: Colors.deepPurple,
        brightness: Brightness.dark,
        useMaterial3: true,
        fontFamily: 'Roboto',
      ),
      themeMode: ThemeMode.system,
      home: const LanguageSelectionPage(),
    );
  }
}

class LanguageSelectionPage extends StatelessWidget {
  const LanguageSelectionPage({Key? key}) : super(key: key);

  // 支持的语言列表
  final List<Map<String, dynamic>> languages = const [
    {'name': '韩语', 'flag': '🇰🇷', 'id': 'korean', 'roomName': 'Pryme-Korean'},
    {'name': '日语', 'flag': '🇯🇵', 'id': 'japanese', 'roomName': 'Pryme-Japanese'},
    {'name': '越南语', 'flag': '🇻🇳', 'id': 'vietnamese', 'roomName': 'Pryme-Vietnamese'},
    {'name': '马来语', 'flag': '🇲🇾', 'id': 'malay', 'roomName': 'Pryme-Malay'},
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('选择语言'),
        centerTitle: true,
        elevation: 0,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF4A148C), Color(0xFF7B1FA2)],
          ),
        ),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 20),
              const Text(
                'Pryme+ 实时翻译',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                '请选择您需要的翻译语言',
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.white70,
                ),
              ),
              const SizedBox(height: 40),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: GridView.builder(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      crossAxisSpacing: 16,
                      mainAxisSpacing: 16,
                      childAspectRatio: 1.2,
                    ),
                    itemCount: languages.length,
                    itemBuilder: (context, index) {
                      final language = languages[index];
                      return _buildLanguageCard(context, language);
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageCard(BuildContext context, Map<String, dynamic> language) {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: InkWell(
        onTap: () => _selectLanguage(context, language),
        borderRadius: BorderRadius.circular(16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              language['flag'],
              style: const TextStyle(fontSize: 40),
            ),
            const SizedBox(height: 8),
            Text(
              language['name'],
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _selectLanguage(BuildContext context, Map<String, dynamic> language) async {
    // 显示加载对话框
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(
        child: CircularProgressIndicator(
          color: Colors.white,
        ),
      ),
    );

    try {
      // 获取LiveKit Token
      final token = await _getToken(language['roomName']);
      
      // 关闭加载对话框
      Navigator.pop(context);
      
      // 导航到翻译页面
      if (context.mounted) {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (context) => TranslationPage(
              language: language,
              token: token,
            ),
          ),
        );
      }
    } catch (e) {
      // 关闭加载对话框
      Navigator.pop(context);
      
      // 显示错误信息
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('连接失败: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<String> _getToken(String roomName) async {
    // 在实际应用中，应该从您的服务器获取token
    // 这里使用示例URL，您需要替换为实际的API端点
    final apiUrl = dotenv.get('API_URL', fallback: 'http://localhost:5000');
    final response = await http.get(
      Uri.parse('$apiUrl/api/get-token?room=$roomName&participant_name=flutter-listener-${DateTime.now().millisecondsSinceEpoch}'),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['token'];
    } else {
      throw Exception('获取Token失败: ${response.statusCode}');
    }
  }
}

class TranslationPage extends StatefulWidget {
  final Map<String, dynamic> language;
  final String token;

  const TranslationPage({
    Key? key,
    required this.language,
    required this.token,
  }) : super(key: key);

  @override
  State<TranslationPage> createState() => _TranslationPageState();
}

class _TranslationPageState extends State<TranslationPage> {
  Room? _room;
  RemoteParticipant? _agent;
  String _subtitle = '';
  String _agentState = '等待连接...';
  bool _isConnected = false;
  double _audioLevel = 0.0;
  
  // 用于音频可视化的计时器
  late Stream<double> _audioLevelStream;

  @override
  void initState() {
    super.initState();
    _connectToRoom();
    
    // 创建音频电平模拟流
    _audioLevelStream = Stream.periodic(
      const Duration(milliseconds: 100),
      (count) => _isConnected && _agentState == 'speaking' 
          ? (0.3 + 0.7 * (count % 10) / 10) 
          : 0.0,
    );
  }

  @override
  void dispose() {
    _disconnectFromRoom();
    super.dispose();
  }

  Future<void> _connectToRoom() async {
    try {
      // 连接到LiveKit房间
      final roomOptions = RoomOptions(
        adaptiveStream: true,
        dynacast: true,
        audioEnabled: true,
      );
      
      final connectOptions = ConnectOptions(
        autoSubscribe: true,
      );

      final room = await Room.connect(
        dotenv.get('LIVEKIT_URL', fallback: 'wss://your-livekit-server.livekit.cloud'),
        widget.token,
        roomOptions: roomOptions,
        connectOptions: connectOptions,
      );
      
      setState(() {
        _room = room;
        _isConnected = true;
        _agentState = '已连接，等待翻译代理...';
      });

      // 监听参与者事件
      room.participants.forEach(_handleParticipant);
      room.on<ParticipantConnectedEvent>().listen((event) {
        _handleParticipant(event.participant);
      });
      
      // 监听连接状态变化
      room.on<RoomDisconnectedEvent>().listen((event) {
        setState(() {
          _isConnected = false;
          _agentState = '已断开连接';
        });
      });
      
      print('已连接到房间: ${widget.language['roomName']}');
    } catch (e) {
      print('连接房间失败: $e');
      setState(() {
        _agentState = '连接失败: $e';
      });
    }
  }

  void _handleParticipant(RemoteParticipant participant) {
    print('参与者加入: ${participant.identity}');
    
    // 检查是否是翻译代理
    if (participant.identity.contains('translator')) {
      print('找到翻译代理: ${participant.identity}');
      setState(() {
        _agent = participant;
        _agentState = '已找到翻译代理';
      });
      
      // 监听轨道发布
      participant.on<TrackPublishedEvent>().listen((event) {
        _handleTrackPublication(event.publication);
      });
      
      // 监听轨道订阅
      participant.on<TrackSubscribedEvent>().listen((event) {
        _handleTrackSubscribed(event.track);
      });
      
      // 检查已有轨道
      participant.trackPublications.values.forEach(_handleTrackPublication);
    }
  }

  void _handleTrackPublication(TrackPublication publication) {
    if (publication.subscribed) {
      _handleTrackSubscribed(publication.track!);
    }
  }

  void _handleTrackSubscribed(Track track) {
    print('订阅轨道: ${track.kind}');
    
    if (track is AudioTrack) {
      // 处理音频轨道
      track.onAudioLevelChanged = (level) {
        setState(() {
          _audioLevel = level;
        });
      };
    } else if (track is DataTrack) {
      // 处理数据轨道
      track.onMessage = (message) {
        _handleDataMessage(message);
      };
    }
  }

  void _handleDataMessage(dynamic message) {
    if (message is! Uint8List) return;
    
    try {
      // 尝试解析JSON
      final data = jsonDecode(utf8.decode(message));
      print('收到数据消息: $data');
      
      setState(() {
        // 处理字幕
        if (data['type'] == 'transcript' || data['type'] == 'translation') {
          _subtitle = data['text'] ?? '';
        }
        
        // 处理代理状态
        if (data['state'] != null) {
          switch (data['state']) {
            case 'listening':
              _agentState = '正在倾听...';
              break;
            case 'thinking':
              _agentState = '正在翻译...';
              break;
            case 'speaking':
              _agentState = '正在播放...';
              break;
            default:
              _agentState = data['state'];
          }
        }
      });
    } catch (e) {
      // 如果不是JSON，直接使用文本
      final text = utf8.decode(message);
      print('收到文本消息: $text');
      setState(() {
        _subtitle = text;
      });
    }
  }

  void _disconnectFromRoom() {
    _room?.disconnect();
    _room = null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.language['name']} 翻译'),
        centerTitle: true,
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            child: _isConnected
                ? const Icon(Icons.wifi, color: Colors.green)
                : const Icon(Icons.wifi_off, color: Colors.red),
          ),
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF673AB7), Color(0xFF4A148C)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              // 状态指示器
              Container(
                padding: const EdgeInsets.all(12),
                margin: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      _getStateIcon(),
                      color: _getStateColor(),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      _agentState,
                      style: TextStyle(
                        color: _getStateColor(),
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
              
              // 字幕区域
              Expanded(
                child: Container(
                  margin: const EdgeInsets.symmetric(horizontal: 16),
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 10,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                  child: Center(
                    child: _subtitle.isEmpty
                        ? Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(
                                Icons.subtitles_off,
                                size: 48,
                                color: Colors.grey,
                              ),
                              const SizedBox(height: 16),
                              Text(
                                '等待字幕...',
                                style: TextStyle(
                                  fontSize: 18,
                                  color: Colors.grey[600],
                                ),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                widget.language['flag'],
                                style: const TextStyle(fontSize: 32),
                              ),
                            ],
                          )
                        : SingleChildScrollView(
                            child: Text(
                              _subtitle,
                              style: const TextStyle(
                                fontSize: 22,
                                height: 1.5,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ),
                  ),
                ),
              ),
              
              // 音频可视化
              Container(
                height: 100,
                margin: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: StreamBuilder<double>(
                  stream: _audioLevelStream,
                  builder: (context, snapshot) {
                    final level = snapshot.data ?? 0.0;
                    return AudioVisualizer(audioLevel: level);
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _getStateIcon() {
    switch (_agentState) {
      case '正在倾听...':
        return Icons.mic;
      case '正在翻译...':
        return Icons.psychology;
      case '正在播放...':
        return Icons.volume_up;
      case '已连接，等待翻译代理...':
        return Icons.search;
      case '已找到翻译代理':
        return Icons.person_found;
      case '已断开连接':
        return Icons.link_off;
      default:
        return Icons.info_outline;
    }
  }

  Color _getStateColor() {
    switch (_agentState) {
      case '正在倾听...':
        return Colors.blue;
      case '正在翻译...':
        return Colors.orange;
      case '正在播放...':
        return Colors.green;
      case '已连接，等待翻译代理...':
        return Colors.amber;
      case '已找到翻译代理':
        return Colors.green;
      case '已断开连接':
        return Colors.red;
      default:
        return Colors.white;
    }
  }
}

class AudioVisualizer extends StatelessWidget {
  final double audioLevel;

  const AudioVisualizer({
    Key? key,
    required this.audioLevel,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final barCount = 20;
        final barWidth = constraints.maxWidth / (barCount * 2 - 1);
        
        return Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: List.generate(barCount, (index) {
            // 计算每个条的高度，创建波浪效果
            double height;
            if (audioLevel < 0.05) {
              // 静音状态，显示低电平
              height = 0.1;
            } else {
              // 基于索引和音频电平计算高度
              final position = index / barCount;
              final sinValue = sin((position * 3.14 * 2) + (DateTime.now().millisecondsSinceEpoch / 200));
              height = 0.2 + audioLevel * 0.6 + sinValue * audioLevel * 0.2;
            }
            
            return AnimatedContainer(
              duration: const Duration(milliseconds: 50),
              width: barWidth,
              height: constraints.maxHeight * height,
              decoration: BoxDecoration(
                color: _getBarColor(height),
                borderRadius: BorderRadius.circular(barWidth / 2),
              ),
            );
          }),
        );
      },
    );
  }

  Color _getBarColor(double height) {
    if (height < 0.3) {
      return Colors.white.withOpacity(0.3);
    } else if (height < 0.6) {
      return Colors.white.withOpacity(0.6);
    } else {
      return Colors.white.withOpacity(0.9);
    }
  }
} 