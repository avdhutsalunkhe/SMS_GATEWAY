import 'dart:async';
import 'dart:collection';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/sms_models.dart';
import 'native_sms_bridge.dart';

class GatewayController extends ChangeNotifier {
  GatewayController({NativeSmsBridge? bridge})
      : _bridge = bridge ?? NativeSmsBridge();

  static const _prefServerUrl = 'gateway_server_url';
  static const _prefDeviceToken = 'gateway_device_token';
  static const _prefIsActive = 'gateway_is_active';
  static const _prefStatsDate = 'gateway_stats_date';
  static const _prefSentToday = 'gateway_sent_today';
  static const _prefFailedToday = 'gateway_failed_today';
  static const _prefRecentLogs = 'gateway_recent_logs';
  static const _maxActivityItems = 20;
  static const _reconnectDelay = Duration(seconds: 5);

  final NativeSmsBridge _bridge;

  String _serverUrl = '';
  String _token = '';
  bool _isActive = false;
  bool _hasSmsPermission = false;
  GatewayConnectionStatus _connectionStatus = GatewayConnectionStatus.paused;
  String? _lastError;

  int _sentToday = 0;
  int _failedToday = 0;
  String _statsDate = _todayKey();
  final List<SmsActivityItem> _activity = [];

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _wsSubscription;
  Timer? _reconnectTimer;
  bool _disposed = false;
  int _connectionGeneration = 0;

  final Queue<Map<String, dynamic>> _pendingJobs = Queue();
  bool _isProcessingJobs = false;

  String get serverUrl => _serverUrl;
  String get token => _token;
  bool get isActive => _isActive;
  bool get hasSmsPermission => _hasSmsPermission;
  GatewayConnectionStatus get connectionStatus => _connectionStatus;
  String? get lastError => _lastError;
  int get sentToday => _sentToday;
  int get failedToday => _failedToday;
  List<SmsActivityItem> get activity => List.unmodifiable(_activity);
  bool get isConfigured => _serverUrl.trim().isNotEmpty && _token.trim().isNotEmpty;

  static String _todayKey() {
    final now = DateTime.now();
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    return '${now.year}-$m-$d';
  }

  /// Normalizes user-entered HTTP/HTTPS/WS/WSS URLs into `ws(s)://.../ws/device?token=...`.
  static Uri buildDeviceWebSocketUri(String rawUrl, String token) {
    var trimmed = rawUrl.trim();
    if (!trimmed.contains('://')) {
      trimmed = 'wss://$trimmed';
    }
    var parsed = Uri.parse(trimmed);
    var scheme = parsed.scheme.toLowerCase();
    if (scheme == 'https') {
      scheme = 'wss';
    } else if (scheme == 'http') {
      scheme = 'ws';
    }

    var path = parsed.path;
    if (path.isEmpty || path == '/') {
      path = '/ws/device';
    }

    final queryParams = Map<String, String>.from(parsed.queryParameters);
    queryParams['token'] = token.trim();

    return parsed.replace(
      scheme: scheme,
      path: path,
      queryParameters: queryParams,
    );
  }

  Future<void> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    _serverUrl = prefs.getString(_prefServerUrl) ?? '';
    _token = prefs.getString(_prefDeviceToken) ?? '';
    _isActive = prefs.getBool(_prefIsActive) ?? false;

    final savedDate = prefs.getString(_prefStatsDate);
    final today = _todayKey();
    if (savedDate == today) {
      _statsDate = today;
      _sentToday = prefs.getInt(_prefSentToday) ?? 0;
      _failedToday = prefs.getInt(_prefFailedToday) ?? 0;
    } else {
      _statsDate = today;
      _sentToday = 0;
      _failedToday = 0;
      await prefs.setString(_prefStatsDate, today);
      await prefs.setInt(_prefSentToday, 0);
      await prefs.setInt(_prefFailedToday, 0);
    }

    final rawLogs = prefs.getString(_prefRecentLogs);
    if (rawLogs != null && rawLogs.isNotEmpty) {
      try {
        final decoded = jsonDecode(rawLogs) as List<dynamic>;
        _activity
          ..clear()
          ..addAll(
            decoded
                .whereType<Map<String, dynamic>>()
                .map(SmsActivityItem.fromJson)
                .take(_maxActivityItems),
          );
      } catch (_) {}
    }

    _hasSmsPermission = await _bridge.hasRequiredPermissions();
    notifyListeners();

    if (_isActive && isConfigured) {
      await resumeGateway();
    } else {
      _connectionStatus = GatewayConnectionStatus.paused;
      notifyListeners();
    }
  }

  Future<void> requestPermissions() async {
    _hasSmsPermission = await _bridge.requestRequiredPermissions();
    if (!_hasSmsPermission) {
      _lastError = 'SEND_SMS permission is required to send messages.';
    } else {
      _lastError = null;
    }
    notifyListeners();
  }

  Future<void> saveSettings({
    required String serverUrl,
    required String token,
  }) async {
    _serverUrl = serverUrl.trim();
    _token = token.trim();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefServerUrl, _serverUrl);
    await prefs.setString(_prefDeviceToken, _token);

    _lastError = null;
    notifyListeners();

    if (_isActive) {
      await _disconnectSocketOnly();
      if (isConfigured) {
        _connectWebSocket();
      } else {
        await pauseGateway();
      }
    }
  }

  Future<void> setGatewayActive(bool active) async {
    if (active) {
      await resumeGateway();
    } else {
      await pauseGateway();
    }
  }

  Future<void> resumeGateway() async {
    if (!isConfigured) {
      _isActive = false;
      _connectionStatus = GatewayConnectionStatus.paused;
      _lastError = 'Configure Server URL and Device Token first.';
      notifyListeners();
      return;
    }

    _hasSmsPermission = await _bridge.hasRequiredPermissions();
    if (!_hasSmsPermission) {
      _hasSmsPermission = await _bridge.requestRequiredPermissions();
      if (!_hasSmsPermission) {
        _isActive = false;
        _connectionStatus = GatewayConnectionStatus.paused;
        _lastError = 'Grant SMS permission to start the gateway.';
        notifyListeners();
        return;
      }
    }

    _isActive = true;
    _lastError = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefIsActive, true);

    try {
      await _bridge.startForegroundService(
        'Connecting to ${_safeHostLabel()}...',
      );
    } catch (_) {}

    notifyListeners();
    _connectWebSocket();
  }

  Future<void> pauseGateway() async {
    _isActive = false;
    _lastError = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_prefIsActive, false);

    await _disconnectSocketOnly();
    _connectionStatus = GatewayConnectionStatus.paused;

    try {
      await _bridge.stopForegroundService();
    } catch (_) {}

    notifyListeners();
  }

  String _safeHostLabel() {
    try {
      return buildDeviceWebSocketUri(_serverUrl, _token).host;
    } catch (_) {
      return 'server';
    }
  }

  Future<void> _disconnectSocketOnly() async {
    _connectionGeneration++;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;

    await _wsSubscription?.cancel();
    _wsSubscription = null;

    final ch = _channel;
    _channel = null;
    if (ch != null) {
      try {
        await ch.sink.close();
      } catch (_) {}
    }
  }

  Future<void> _connectWebSocket() async {
    if (_disposed || !_isActive || !isConfigured) return;

    await _disconnectSocketOnly();
    final gen = _connectionGeneration;

    Uri uri;
    try {
      uri = buildDeviceWebSocketUri(_serverUrl, _token);
      if (uri.host.isEmpty) {
        throw const FormatException('Missing server host');
      }
    } catch (e) {
      _connectionStatus = GatewayConnectionStatus.disconnected;
      _lastError = 'Invalid Server URL: $e';
      notifyListeners();
      return;
    }

    _connectionStatus = GatewayConnectionStatus.connecting;
    notifyListeners();

    try {
      final channel = IOWebSocketChannel.connect(
        uri,
        pingInterval: const Duration(seconds: 20),
      );
      _channel = channel;
      await channel.ready;

      if (_disposed || !_isActive || gen != _connectionGeneration) {
        try {
          await channel.sink.close();
        } catch (_) {}
        return;
      }

      _connectionStatus = GatewayConnectionStatus.connected;
      _lastError = null;
      notifyListeners();
      _syncForegroundNotification();

      _wsSubscription = channel.stream.listen(
        (dynamic data) {
          if (gen != _connectionGeneration) return;
          _onSocketData(data);
        },
        onError: (Object error) {
          if (gen != _connectionGeneration) return;
          _handleConnectionLoss('WebSocket error: $error');
        },
        onDone: () {
          if (gen != _connectionGeneration) return;
          _handleConnectionLoss('Disconnected from server');
        },
        cancelOnError: true,
      );
    } catch (e) {
      if (gen != _connectionGeneration) return;
      _handleConnectionLoss('Connection failed: $e');
    }
  }

  void _handleConnectionLoss(String reason) {
    _wsSubscription = null;
    _channel = null;

    if (!_isActive || _disposed) {
      _connectionStatus = GatewayConnectionStatus.paused;
      notifyListeners();
      return;
    }

    _connectionStatus = GatewayConnectionStatus.disconnected;
    _lastError = reason;
    notifyListeners();
    _syncForegroundNotification();

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(_reconnectDelay, () {
      if (_isActive && !_disposed) {
        _connectWebSocket();
      }
    });
  }

  void _onSocketData(dynamic raw) {
    if (raw is! String) return;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return;
      if (!decoded.containsKey('message_id') ||
          !decoded.containsKey('to') ||
          !decoded.containsKey('message')) {
        return;
      }
      _pendingJobs.add(decoded);
      if (!_isProcessingJobs) {
        _drainJobQueue();
      }
    } catch (_) {}
  }

  Future<void> _drainJobQueue() async {
    if (_isProcessingJobs) return;
    _isProcessingJobs = true;

    try {
      while (_pendingJobs.isNotEmpty && !_disposed) {
        final job = _pendingJobs.removeFirst();
        final messageId = (job['message_id'] ?? '').toString();
        final to = (job['to'] ?? '').toString();
        final message = (job['message'] ?? '').toString();

        if (messageId.isEmpty || to.isEmpty || message.isEmpty) {
          continue;
        }

        String status = 'sent';
        String? error;

        try {
          await _bridge.sendSms(to: to, message: message);
        } on PlatformException catch (e) {
          status = 'failed';
          error = e.message ?? e.code;
        } catch (e) {
          status = 'failed';
          error = e.toString();
        }

        _sendAck(messageId: messageId, status: status, error: error);
        await _recordActivity(
          SmsActivityItem(
            messageId: messageId,
            to: to,
            message: message,
            status: status,
            timestamp: DateTime.now(),
            error: error,
          ),
        );
      }
    } finally {
      _isProcessingJobs = false;
    }
  }

  void _sendAck({
    required String messageId,
    required String status,
    String? error,
  }) {
    final ch = _channel;
    if (ch == null) return;
    final payload = <String, dynamic>{
      'message_id': messageId,
      'status': status,
      'error': error,
    };
    try {
      ch.sink.add(jsonEncode(payload));
    } catch (_) {}
  }

  Future<void> _recordActivity(SmsActivityItem item) async {
    final today = _todayKey();
    if (_statsDate != today) {
      _statsDate = today;
      _sentToday = 0;
      _failedToday = 0;
    }

    if (item.isSent) {
      _sentToday++;
    } else {
      _failedToday++;
    }

    _activity.insert(0, item);
    if (_activity.length > _maxActivityItems) {
      _activity.removeRange(_maxActivityItems, _activity.length);
    }

    notifyListeners();
    _syncForegroundNotification();

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefStatsDate, _statsDate);
    await prefs.setInt(_prefSentToday, _sentToday);
    await prefs.setInt(_prefFailedToday, _failedToday);
    await prefs.setString(
      _prefRecentLogs,
      jsonEncode(_activity.map((e) => e.toJson()).toList()),
    );
  }

  void _syncForegroundNotification() {
    if (!_isActive) return;
    final text = switch (_connectionStatus) {
      GatewayConnectionStatus.connected =>
        'Connected • Sent $_sentToday | Failed $_failedToday',
      GatewayConnectionStatus.connecting => 'Connecting to ${_safeHostLabel()}...',
      GatewayConnectionStatus.disconnected => 'Disconnected • Retrying every 5s',
      GatewayConnectionStatus.paused => 'Paused',
    };
    _bridge.updateNotification(text).catchError((_) {});
  }

  @override
  void dispose() {
    _disposed = true;
    _disconnectSocketOnly();
    super.dispose();
  }
}
