import 'package:flutter_test/flutter_test.dart';
import 'package:reboot_health/main.dart';

void main() {
  testWidgets('展示正式客户端空壳', (tester) async {
    await tester.pumpWidget(const RebootHealthApp());

    expect(find.text('Flutter 客户端骨架'), findsOneWidget);
    expect(find.textContaining('Health Platform'), findsOneWidget);
  });
}
