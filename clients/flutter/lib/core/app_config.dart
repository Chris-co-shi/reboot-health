class AppConfig {
  const AppConfig({required this.apiBaseUrl});

  factory AppConfig.fromEnvironment() {
    return const AppConfig(
      apiBaseUrl: String.fromEnvironment(
        'REBOOT_HEALTH_API_BASE_URL',
        defaultValue: 'http://127.0.0.1:8080',
      ),
    );
  }

  final String apiBaseUrl;
}
