import 'package:flutter_test/flutter_test.dart';
import 'package:reboot_health/core/api_client.dart';
import 'package:reboot_health/features/coach/agent_run_models.dart';
import 'package:reboot_health/features/coach/coach_presenter.dart';

void main() {
  test('AgentRun 状态映射为中文显示', () {
    expect(agentRunStatusLabel('RUNNING'), '运行中');
    expect(agentRunStatusLabel('VALIDATING'), '校验中');
    expect(agentRunStatusLabel('READY_FOR_USER_REVIEW'), '可查看');
    expect(agentRunStatusLabel('FAILED'), '运行失败');
  });

  test('技术错误不会透出堆栈', () {
    expect(coachFailureMessage(Exception('stack trace at internal')), 'AI教练暂时不可用，请稍后重试');
    expect(coachFailureMessage(const ApiException(400, '设备未初始化')), '设备未初始化');
  });

  test('AgentRun 结构化卡片可解析', () {
    final AgentRun run = AgentRun.fromJson(<String, Object?>{
      'id': 'run-1',
      'status': 'READY_FOR_USER_REVIEW',
      'structuredOutput': <String, Object?>{
        'cards': <Object?>[
          <String, Object?>{
            'type': 'SYSTEM_STATUS',
            'title': 'AI教练服务已连接',
            'content': 'Java与Python运行链路正常',
          },
        ],
      },
    });

    expect(run.cards, hasLength(1));
    expect(run.cards.first.title, 'AI教练服务已连接');
  });
}
