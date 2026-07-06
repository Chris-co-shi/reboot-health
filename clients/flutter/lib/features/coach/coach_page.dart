import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/design_tokens.dart';
import '../auth/secure_credential_store.dart';
import 'agent_api.dart';
import 'agent_run_models.dart';
import 'coach_presenter.dart';

class CoachPage extends StatefulWidget {
  const CoachPage({
    required this.agentApi,
    required this.apiClient,
    required this.credentialStore,
    super.key,
  });

  final AgentApi agentApi;
  final ApiClient apiClient;
  final CredentialStore credentialStore;

  @override
  State<CoachPage> createState() => _CoachPageState();
}

class _CoachPageState extends State<CoachPage> {
  AgentRun? _run;
  bool _loading = false;
  String? _message;
  String? _debugRunId;
  Timer? _poller;

  @override
  void dispose() {
    _poller?.cancel();
    super.dispose();
  }

  Future<void> _checkCoach() async {
    final DeviceCredentials? credentials = await widget.credentialStore.read();
    if (!mounted) {
      return;
    }
    if (credentials == null) {
      setState(() {
        _message = '请先在“我的”完成设备初始化或配对';
      });
      return;
    }
    setState(() {
      _loading = true;
      _message = '正在连接AI教练服务';
      _run = null;
      _debugRunId = null;
    });
    try {
      final AgentRun created = await widget.agentApi.createSmokeTestRun(
        idempotencyKey: widget.apiClient.createIdempotencyKey(),
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _run = created;
        _debugRunId = created.id;
        _message = agentRunStatusLabel(created.status);
      });
      _startPolling(created.id);
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _message = coachFailureMessage(error);
      });
    }
  }

  void _startPolling(String runId) {
    _poller?.cancel();
    _poller = Timer.periodic(const Duration(seconds: 1), (Timer timer) async {
      try {
        final AgentRun latest = await widget.agentApi.getRun(runId);
        if (!mounted) {
          return;
        }
        setState(() {
          _run = latest;
          _message = agentRunStatusLabel(latest.status);
          _loading = !agentRunIsTerminal(latest.status);
        });
        if (agentRunIsTerminal(latest.status)) {
          timer.cancel();
        }
      } catch (_) {
        if (!mounted) {
          return;
        }
        timer.cancel();
        setState(() {
          _loading = false;
          _message = 'AI教练状态读取失败，请稍后重试';
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: <Widget>[
        Text('教练', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: AppSpacing.sm),
        Text(
          '检查 Java 与 Python Agent Runtime 的连接状态。',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: scheme.onSurfaceVariant),
        ),
        const SizedBox(height: AppSpacing.lg),
        FilledButton.icon(
          onPressed: _loading ? null : _checkCoach,
          icon: _loading
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.health_and_safety_outlined),
          label: Text(_loading ? '检查中' : '检查AI教练连接'),
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
        if (_run != null && _run!.cards.isNotEmpty) ...<Widget>[
          const SizedBox(height: AppSpacing.md),
          for (final AgentCard card in _run!.cards)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(card.title, style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: AppSpacing.sm),
                      Text(card.content),
                    ],
                  ),
                ),
              ),
            ),
        ],
        if (_debugRunId != null) ...<Widget>[
          const SizedBox(height: AppSpacing.xl),
          ExpansionTile(
            title: const Text('开发调试信息'),
            children: <Widget>[
              ListTile(title: const Text('AgentRun'), subtitle: Text(_debugRunId!)),
            ],
          ),
        ],
      ],
    );
  }
}
