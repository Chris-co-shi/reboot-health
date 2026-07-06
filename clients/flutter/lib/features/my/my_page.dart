import 'package:flutter/material.dart';

import '../../core/design_tokens.dart';
import '../../core/idempotent_action.dart';
import '../auth/device_auth_api.dart';
import '../auth/secure_credential_store.dart';

class MyPage extends StatefulWidget {
  const MyPage({
    required this.authApi,
    required this.credentialStore,
    super.key,
  });

  final DeviceAuthApi authApi;
  final CredentialStore credentialStore;

  @override
  State<MyPage> createState() => _MyPageState();
}

class _MyPageState extends State<MyPage> {
  final TextEditingController _bootstrapCodeController = TextEditingController();
  final TextEditingController _pairingCodeController = TextEditingController();
  bool _loading = false;
  String? _message;
  PairingSessionView? _pairingSession;
  List<DeviceView> _devices = const <DeviceView>[];
  late final IdempotentAction _bootstrapAction;
  late final IdempotentAction _pairAction;

  @override
  void initState() {
    super.initState();
    _bootstrapAction = IdempotentAction(widget.authApi.createIdempotencyKey);
    _pairAction = IdempotentAction(widget.authApi.createIdempotencyKey);
  }

  @override
  void dispose() {
    _bootstrapCodeController.dispose();
    _pairingCodeController.dispose();
    super.dispose();
  }

  Future<void> _consumeBootstrap() async {
    await _run(() async {
      await _bootstrapAction.run((String key) => widget.authApi.consumeBootstrap(
            bootstrapCode: _bootstrapCodeController.text.trim(),
            deviceName: 'Flutter 设备',
            platform: _platformName(),
            idempotencyKey: key,
          )
      );
      _bootstrapCodeController.clear();
      _message = '首台设备初始化完成';
      await _refreshDevices();
    });
  }

  Future<void> _createPairing() async {
    await _run(() async {
      _pairingSession = await widget.authApi.createPairingSession();
      _message = '配对码已生成';
    });
  }

  Future<void> _consumePairing() async {
    await _run(() async {
      await _pairAction.run((String key) => widget.authApi.consumePairing(
            pairingCode: _pairingCodeController.text.trim(),
            deviceName: 'Flutter 设备',
            platform: _platformName(),
            idempotencyKey: key,
          )
      );
      _pairingCodeController.clear();
      _message = '设备配对完成';
      await _refreshDevices();
    });
  }

  Future<void> _refreshDevices() async {
    _devices = await widget.authApi.listDevices();
  }

  Future<void> _revokeDevice(DeviceView device) async {
    await _run(() async {
      await widget.authApi.revokeDevice(device.id);
      await _refreshDevices();
      _message = '设备已撤销';
    });
  }

  Future<void> _makePrimary(DeviceView device) async {
    await _run(() async {
      await widget.authApi.makePrimary(device.id);
      await _refreshDevices();
      _message = '主设备已更新';
    });
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _loading = true;
      _message = null;
    });
    try {
      await action();
    } catch (_) {
      _message = '设备操作失败，请检查输入或稍后重试';
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  String _platformName() {
    final TargetPlatform platform = Theme.of(context).platform;
    return switch (platform) {
      TargetPlatform.iOS => 'IOS',
      TargetPlatform.android => 'ANDROID',
      TargetPlatform.macOS => 'MACOS',
      TargetPlatform.windows => 'WINDOWS',
      _ => 'UNKNOWN',
    };
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: <Widget>[
        Text('我的', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: AppSpacing.lg),
        _section(
          title: '首台设备初始化',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              TextField(
                controller: _bootstrapCodeController,
                decoration: const InputDecoration(labelText: 'Bootstrap Code'),
                obscureText: true,
              ),
              const SizedBox(height: AppSpacing.sm),
              FilledButton(
                onPressed: _loading ? null : _consumeBootstrap,
                child: const Text('初始化此设备'),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        _section(
          title: '添加新设备',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              FilledButton.tonal(
                onPressed: _loading ? null : _createPairing,
                child: const Text('生成配对码'),
              ),
              if (_pairingSession != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                SelectableText('配对码：${_pairingSession!.pairingCode}'),
                SelectableText('二维码负载：${_pairingSession!.qrPayload}'),
              ],
              const SizedBox(height: AppSpacing.sm),
              TextField(
                controller: _pairingCodeController,
                decoration: const InputDecoration(labelText: '输入配对码'),
                obscureText: true,
              ),
              const SizedBox(height: AppSpacing.sm),
              OutlinedButton(
                onPressed: _loading ? null : _consumePairing,
                child: const Text('配对此设备'),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        _section(
          title: '设备',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              OutlinedButton(
                onPressed: _loading
                    ? null
                    : () => _run(() async {
                          await _refreshDevices();
                          _message = '设备列表已刷新';
                        }),
                child: const Text('刷新设备列表'),
              ),
              for (final DeviceView device in _devices)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(device.deviceName),
                  subtitle: Text(_deviceSubtitle(device)),
                  trailing: Wrap(
                    spacing: AppSpacing.xs,
                    children: <Widget>[
                      if (device.status == 'ACTIVE' && device.trustLevel != 'TRUSTED_PRIMARY')
                        TextButton(
                          onPressed: _loading ? null : () => _makePrimary(device),
                          child: const Text('设为主设备'),
                        ),
                      if (device.status == 'ACTIVE')
                        TextButton(
                          onPressed: _loading ? null : () => _revokeDevice(device),
                          child: Text(device.currentDevice ? '撤销当前' : '撤销'),
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        if (_message != null) ...<Widget>[
          const SizedBox(height: AppSpacing.md),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Text(_message!),
            ),
          ),
        ],
      ],
    );
  }

  Widget _section({required String title, required Widget child}) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpacing.md),
            child,
          ],
        ),
      ),
    );
  }

  String _deviceSubtitle(DeviceView device) {
    final String current = device.currentDevice ? '当前设备 · ' : '';
    final String primary = device.trustLevel == 'TRUSTED_PRIMARY' ? '主设备' : '可信设备';
    final String status = device.status == 'ACTIVE' ? '可用' : '已撤销';
    return '$current${device.platform} · $primary · $status';
  }
}
