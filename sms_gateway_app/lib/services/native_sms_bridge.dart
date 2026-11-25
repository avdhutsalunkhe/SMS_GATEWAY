import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

class NativeSmsBridge {
  static const MethodChannel _channel =
      MethodChannel('com.rbpssk.smsgateway/sms');

  Future<bool> hasRequiredPermissions() async {
    final smsGranted = await Permission.sms.isGranted;
    final notifStatus = await Permission.notification.status;
    final notifOk = notifStatus.isGranted || notifStatus.isLimited;
    return smsGranted && notifOk;
  }

  Future<bool> requestRequiredPermissions() async {
    final statuses = await [
      Permission.sms,
      Permission.notification,
    ].request();

    final smsGranted = statuses[Permission.sms]?.isGranted ?? false;
    return smsGranted;
  }

  Future<void> sendSms({
    required String to,
    required String message,
  }) async {
    await _channel.invokeMethod<dynamic>('sendSms', {
      'to': to,
      'message': message,
    });
  }

  Future<void> startForegroundService(String statusText) async {
    await _channel.invokeMethod<dynamic>('startService', {
      'statusText': statusText,
    });
  }

  Future<void> updateNotification(String statusText) async {
    await _channel.invokeMethod<dynamic>('updateNotification', {
      'statusText': statusText,
    });
  }

  Future<void> stopForegroundService() async {
    await _channel.invokeMethod<dynamic>('stopService');
  }
}
