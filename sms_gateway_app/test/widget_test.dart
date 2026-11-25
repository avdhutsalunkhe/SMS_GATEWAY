import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:sms_gateway_app/main.dart';
import 'package:sms_gateway_app/models/sms_models.dart';
import 'package:sms_gateway_app/services/gateway_controller.dart';
import 'package:sms_gateway_app/services/native_sms_bridge.dart';

class FakeNativeSmsBridge extends NativeSmsBridge {
  @override
  Future<bool> hasRequiredPermissions() async => true;

  @override
  Future<bool> requestRequiredPermissions() async => true;

  @override
  Future<void> sendSms({required String to, required String message}) async {}

  @override
  Future<void> startForegroundService(String statusText) async {}

  @override
  Future<void> updateNotification(String statusText) async {}

  @override
  Future<void> stopForegroundService() async {}
}

void main() {
  test('buildDeviceWebSocketUri normalizes http/https/ws/wss and appends token', () {
    final fromHttps = GatewayController.buildDeviceWebSocketUri(
      'https://sms.example.ts.net',
      'sec 123',
    );
    expect(fromHttps.scheme, 'wss');
    expect(fromHttps.path, '/ws/device');
    expect(fromHttps.queryParameters['token'], 'sec 123');

    final fromWs = GatewayController.buildDeviceWebSocketUri(
      'ws://192.168.1.5:8000/ws/device',
      'mysecret',
    );
    expect(fromWs.toString(), 'ws://192.168.1.5:8000/ws/device?token=mysecret');
  });

  test('SmsActivityItem round-trips JSON cleanly', () {
    final item = SmsActivityItem(
      messageId: 'abc123',
      to: '+919876543210',
      message: 'Hello gateway',
      status: 'sent',
      timestamp: DateTime(2026, 11, 25, 16, 30, 0),
    );
    final decoded = SmsActivityItem.fromJson(item.toJson());
    expect(decoded.messageId, 'abc123');
    expect(decoded.to, '+919876543210');
    expect(decoded.isSent, isTrue);
  });

  testWidgets('GatewayHomeScreen renders status card, stats, and settings modal',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    final controller = GatewayController(bridge: FakeNativeSmsBridge());

    await tester.pumpWidget(SmsGatewayApp(controller: controller));
    await tester.pumpAndSettle();

    expect(find.text('SMS Gateway'), findsOneWidget);
    expect(find.text("Today's Sent"), findsOneWidget);
    expect(find.text("Today's Failed"), findsOneWidget);
    expect(find.text('Paused'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();

    expect(find.text('Gateway Settings'), findsOneWidget);
    expect(find.text('Save Settings'), findsOneWidget);
  });
}
