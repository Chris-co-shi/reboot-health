class AgentRun {
  const AgentRun({
    required this.id,
    required this.status,
    required this.cards,
    this.failureMessage,
  });

  factory AgentRun.fromJson(Map<String, Object?> json) {
    final Object? structuredOutput = json['structuredOutput'];
    final List<AgentCard> cards = <AgentCard>[];
    if (structuredOutput is Map<String, Object?>) {
      final Object? rawCards = structuredOutput['cards'];
      if (rawCards is List<Object?>) {
        cards.addAll(rawCards.whereType<Map<String, Object?>>().map(AgentCard.fromJson));
      }
    }
    return AgentRun(
      id: json['id'] as String,
      status: json['status'] as String,
      cards: cards,
      failureMessage: json['failureMessage'] as String?,
    );
  }

  final String id;
  final String status;
  final List<AgentCard> cards;
  final String? failureMessage;
}

class AgentCard {
  const AgentCard({
    required this.type,
    required this.title,
    required this.content,
  });

  factory AgentCard.fromJson(Map<String, Object?> json) {
    return AgentCard(
      type: json['type'] as String,
      title: json['title'] as String,
      content: json['content'] as String,
    );
  }

  final String type;
  final String title;
  final String content;
}

String agentRunStatusLabel(String status) {
  return switch (status) {
    'CREATED' => '已创建',
    'RUNNING' => '运行中',
    'VALIDATING' => '校验中',
    'READY_FOR_USER_REVIEW' => '可查看',
    'FAILED' => '运行失败',
    'CANCELLED' => '已取消',
    'EXPIRED' => '已过期',
    _ => '未知状态',
  };
}

bool agentRunIsTerminal(String status) {
  return status == 'READY_FOR_USER_REVIEW'
      || status == 'FAILED'
      || status == 'CANCELLED'
      || status == 'EXPIRED';
}
