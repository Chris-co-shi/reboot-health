import 'package:flutter/material.dart';

import 'core/api_client.dart';
import 'core/app_config.dart';
import 'core/design_tokens.dart';
import 'features/auth/device_auth_api.dart';
import 'features/auth/secure_credential_store.dart';
import 'features/coach/agent_api.dart';
import 'features/coach/coach_page.dart';
import 'features/home/placeholder_page.dart';
import 'features/my/my_page.dart';

void main() {
  final CredentialStore credentialStore = SecureCredentialStore();
  final ApiClient apiClient = ApiClient(
    config: AppConfig.fromEnvironment(),
    credentialStore: credentialStore,
  );
  runApp(RebootHealthApp(
    apiClient: apiClient,
    credentialStore: credentialStore,
  ));
}

class RebootHealthApp extends StatelessWidget {
  const RebootHealthApp({
    required this.apiClient,
    required this.credentialStore,
    super.key,
  });

  final ApiClient apiClient;
  final CredentialStore credentialStore;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Reboot Health',
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      home: AppShell(
        apiClient: apiClient,
        credentialStore: credentialStore,
      ),
    );
  }
}

class AppShell extends StatefulWidget {
  const AppShell({
    required this.apiClient,
    required this.credentialStore,
    super.key,
  });

  final ApiClient apiClient;
  final CredentialStore credentialStore;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 1;

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = <Widget>[
      const PlaceholderFeaturePage(title: '今日', message: '今日行动卡将在 M2.5-C 实现'),
      CoachPage(
        agentApi: AgentApi(widget.apiClient),
        apiClient: widget.apiClient,
        credentialStore: widget.credentialStore,
      ),
      const PlaceholderFeaturePage(title: '计划', message: '计划编辑仍由现有后端能力承接，本轮不新增 Flutter 计划编辑'),
      const PlaceholderFeaturePage(title: '数据', message: '每日数据和 Observation 将在后续阶段实现'),
      MyPage(
        authApi: DeviceAuthApi(widget.apiClient, widget.credentialStore),
        credentialStore: widget.credentialStore,
      ),
    ];
    final List<NavigationDestination> destinations = <NavigationDestination>[
      const NavigationDestination(icon: Icon(Icons.today_outlined), label: '今日'),
      const NavigationDestination(icon: Icon(Icons.psychology_outlined), label: '教练'),
      const NavigationDestination(icon: Icon(Icons.calendar_month_outlined), label: '计划'),
      const NavigationDestination(icon: Icon(Icons.insights_outlined), label: '数据'),
      const NavigationDestination(icon: Icon(Icons.person_outline), label: '我的'),
    ];

    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        if (constraints.maxWidth >= 720) {
          return Scaffold(
            body: Row(
              children: <Widget>[
                NavigationRail(
                  selectedIndex: _index,
                  onDestinationSelected: (int value) => setState(() => _index = value),
                  labelType: NavigationRailLabelType.all,
                  destinations: destinations
                      .map((NavigationDestination destination) => NavigationRailDestination(
                            icon: destination.icon,
                            label: Text(destination.label),
                          ))
                      .toList(),
                ),
                const VerticalDivider(width: 1),
                Expanded(
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 980),
                      child: pages[_index],
                    ),
                  ),
                ),
              ],
            ),
          );
        }
        return Scaffold(
          body: SafeArea(child: pages[_index]),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _index,
            destinations: destinations,
            onDestinationSelected: (int value) => setState(() => _index = value),
          ),
        );
      },
    );
  }
}
