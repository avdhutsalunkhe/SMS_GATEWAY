import 'package:flutter/material.dart';

import 'models/sms_models.dart';
import 'services/gateway_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SmsGatewayApp());
}

class SmsGatewayApp extends StatelessWidget {
  const SmsGatewayApp({super.key, this.controller});

  final GatewayController? controller;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SMS Gateway',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0F766E),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: GatewayHomeScreen(controller: controller),
    );
  }
}

class GatewayHomeScreen extends StatefulWidget {
  const GatewayHomeScreen({super.key, this.controller});

  final GatewayController? controller;

  @override
  State<GatewayHomeScreen> createState() => _GatewayHomeScreenState();
}

class _GatewayHomeScreenState extends State<GatewayHomeScreen> {
  late final GatewayController _controller;
  late final bool _ownsController;

  @override
  void initState() {
    super.initState();
    _ownsController = widget.controller == null;
    _controller = widget.controller ?? GatewayController();
    _controller.initialize();
  }

  @override
  void dispose() {
    if (_ownsController) {
      _controller.dispose();
    }
    super.dispose();
  }

  Future<void> _openSettingsModal() async {
    final urlController = TextEditingController(text: _controller.serverUrl);
    final tokenController = TextEditingController(text: _controller.token);
    bool obscureToken = true;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 8,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Gateway Settings',
                    style: Theme.of(ctx).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: urlController,
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    decoration: const InputDecoration(
                      labelText: 'Server URL',
                      hintText: 'ws://115.244.240.22:8072/ws/device',
                      helperText: 'Public IP: ws://115.244.240.22:8072/ws/device',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: tokenController,
                    obscureText: obscureToken,
                    autocorrect: false,
                    decoration: InputDecoration(
                      labelText: 'Device Secret Token',
                      hintText: 'Matches DEVICE_SECRET on your FastAPI server',
                      border: const OutlineInputBorder(),
                      suffixIcon: IconButton(
                        icon: Icon(
                          obscureToken
                              ? Icons.visibility_outlined
                              : Icons.visibility_off_outlined,
                        ),
                        onPressed: () {
                          setModalState(() => obscureToken = !obscureToken);
                        },
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: () async {
                      await _controller.saveSettings(
                        serverUrl: urlController.text,
                        token: tokenController.text,
                      );
                      if (ctx.mounted) {
                        Navigator.of(ctx).pop();
                      }
                    },
                    icon: const Icon(Icons.save_outlined),
                    label: const Text('Save Settings'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    urlController.dispose();
    tokenController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _controller,
      builder: (context, _) {
        final status = _controller.connectionStatus;
        final (statusColor, statusLabel) = switch (status) {
          GatewayConnectionStatus.connected => (Colors.green.shade600, 'Connected'),
          GatewayConnectionStatus.connecting => (Colors.amber.shade700, 'Connecting...'),
          GatewayConnectionStatus.disconnected => (
              Colors.red.shade600,
              'Disconnected • Retrying (5s)'
            ),
          GatewayConnectionStatus.paused => (Colors.grey.shade600, 'Paused'),
        };

        return Scaffold(
          appBar: AppBar(
            title: const Text('SMS Gateway'),
            actions: [
              IconButton(
                tooltip: 'Server & Token Settings',
                icon: const Icon(Icons.settings_outlined),
                onPressed: _openSettingsModal,
              ),
            ],
          ),
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!_controller.hasSmsPermission) ...[
                    Card(
                      color: Theme.of(context).colorScheme.errorContainer,
                      child: ListTile(
                        leading: Icon(
                          Icons.sms_failed_outlined,
                          color: Theme.of(context).colorScheme.onErrorContainer,
                        ),
                        title: const Text('SMS Permission Needed'),
                        subtitle: const Text(
                          'Grant SEND_SMS so the gateway can dispatch messages silently.',
                        ),
                        trailing: TextButton(
                          onPressed: _controller.requestPermissions,
                          child: const Text('Grant'),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  _StatusCard(
                    statusColor: statusColor,
                    statusLabel: statusLabel,
                    serverUrl: _controller.serverUrl,
                    lastError: _controller.lastError,
                    isActive: _controller.isActive,
                    onToggle: _controller.setGatewayActive,
                    onConfigure: _openSettingsModal,
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: _StatCard(
                          label: "Today's Sent",
                          count: _controller.sentToday,
                          color: Colors.green.shade700,
                          icon: Icons.check_circle_outline,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _StatCard(
                          label: "Today's Failed",
                          count: _controller.failedToday,
                          color: Colors.red.shade700,
                          icon: Icons.error_outline,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Live Activity (Last 20)',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        '${_controller.activity.length} items',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Expanded(
                    child: _controller.activity.isEmpty
                        ? Center(
                            child: Text(
                              'No SMS processed yet.\nIncoming jobs will appear here.',
                              textAlign: TextAlign.center,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(color: Colors.grey.shade600),
                            ),
                          )
                        : ListView.separated(
                            itemCount: _controller.activity.length,
                            separatorBuilder: (_, _) => const SizedBox(height: 8),
                            itemBuilder: (context, index) {
                              return _ActivityTile(
                                item: _controller.activity[index],
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.statusColor,
    required this.statusLabel,
    required this.serverUrl,
    required this.lastError,
    required this.isActive,
    required this.onToggle,
    required this.onConfigure,
  });

  final Color statusColor;
  final String statusLabel;
  final String serverUrl;
  final String? lastError;
  final bool isActive;
  final ValueChanged<bool> onToggle;
  final VoidCallback onConfigure;

  @override
  Widget build(BuildContext context) {
    final hasServer = serverUrl.trim().isNotEmpty;
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: statusColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        statusLabel,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 2),
                      GestureDetector(
                        onTap: hasServer ? null : onConfigure,
                        child: Text(
                          hasServer
                              ? serverUrl
                              : 'Tap settings to configure server URL & token',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: hasServer
                                    ? Colors.grey.shade700
                                    : Theme.of(context).colorScheme.primary,
                              ),
                        ),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: isActive,
                  onChanged: onToggle,
                ),
              ],
            ),
            if (lastError != null && lastError!.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                lastError!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Colors.red.shade700),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.label,
    required this.count,
    required this.color,
    required this.icon,
  });

  final String label;
  final int count;
  final Color color;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$count',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                ),
                Text(
                  label,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({required this.item});

  final SmsActivityItem item;

  String _formatTime(DateTime dt) {
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    final s = dt.second.toString().padLeft(2, '0');
    return '$h:$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final badgeBg = item.isSent ? Colors.green.shade50 : Colors.red.shade50;
    final badgeFg = item.isSent ? Colors.green.shade800 : Colors.red.shade800;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    item.to,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                ),
                Text(
                  _formatTime(item.timestamp),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey.shade600,
                      ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: badgeBg,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    item.isSent ? 'Sent' : 'Failed',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: badgeFg,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              item.message,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (!item.isSent && item.error != null && item.error!.isNotEmpty) ...[
              const SizedBox(height: 4),
              Text(
                item.error!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Colors.red.shade700),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
