enum GatewayConnectionStatus {
  paused,
  disconnected,
  connecting,
  connected,
}

class SmsActivityItem {
  const SmsActivityItem({
    required this.messageId,
    required this.to,
    required this.message,
    required this.status,
    required this.timestamp,
    this.error,
  });

  final String messageId;
  final String to;
  final String message;
  final String status; // "sent" | "failed"
  final DateTime timestamp;
  final String? error;

  bool get isSent => status == 'sent';

  Map<String, dynamic> toJson() => {
        'message_id': messageId,
        'to': to,
        'message': message,
        'status': status,
        'timestamp': timestamp.toIso8601String(),
        'error': error,
      };

  factory SmsActivityItem.fromJson(Map<String, dynamic> json) {
    return SmsActivityItem(
      messageId: (json['message_id'] ?? '') as String,
      to: (json['to'] ?? '') as String,
      message: (json['message'] ?? '') as String,
      status: (json['status'] ?? 'failed') as String,
      timestamp: DateTime.tryParse((json['timestamp'] ?? '') as String) ??
          DateTime.now(),
      error: json['error'] as String?,
    );
  }
}
