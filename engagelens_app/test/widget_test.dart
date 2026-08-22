import 'package:flutter_test/flutter_test.dart';
import 'package:engagelens_app/main.dart';

void main() {
  testWidgets('EngageLens smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const EngageLensApp());
    // App should render without throwing
    expect(find.byType(EngageLensApp), findsOneWidget);
  });
}
