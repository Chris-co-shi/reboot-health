import '../../core/api_client.dart';
import 'agent_run_models.dart';

class AgentApi {
  const AgentApi(this._client);

  final ApiClient _client;

  Future<AgentRun> createSmokeTestRun({required String idempotencyKey}) async {
    final Map<String, Object?> json = await _client.postJson(
      '/api/v1/agent-runs',
      authorized: true,
      idempotencyKey: idempotencyKey,
      body: const <String, Object?>{
        'triggerType': 'TECHNICAL_SMOKE_TEST',
        'inputSummary': 'Flutter 教练页发起的技术链路检查',
        'mockMode': 'success',
      },
    );
    return AgentRun.fromJson(json);
  }

  Future<AgentRun> getRun(String runId) async {
    final Map<String, Object?> json = await _client.getJson(
      '/api/v1/agent-runs/$runId',
      authorized: true,
    );
    return AgentRun.fromJson(json);
  }
}
