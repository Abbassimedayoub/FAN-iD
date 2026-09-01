import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/presentation/views/device_reset_confirm_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget app(Widget child) => MaterialApp(
      theme: FanTheme.light,
      home: child,
    );

void main() {
  testWidgets('shows expiry and forwards actions', (tester) async {
    final code = TextEditingController();
    addTearDown(code.dispose);

    var submitCalls = 0;
    var backCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetConfirmView(
          codeController: code,
          expiresInSeconds: 600,
          onSubmit: () => submitCalls++,
          onBack: () => backCalls++,
        ),
      ),
    );

    expect(
      find.text('Le code expire dans 600 secondes.'),
      findsOneWidget,
    );

    await tester.enterText(find.byType(TextField), '123456');
    await tester.tap(find.byType(FanIdPrimaryButton));

    await tester.ensureVisible(find.byType(FanIdSecondaryButton));
    await tester.tap(find.byType(FanIdSecondaryButton));

    expect(code.text, '123456');
    expect(submitCalls, 1);
    expect(backCalls, 1);
  });

  testWidgets('shows error and disables actions while loading', (tester) async {
    final code = TextEditingController();
    addTearDown(code.dispose);

    var submitCalls = 0;
    var backCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetConfirmView(
          codeController: code,
          isLoading: true,
          errorText: 'Code incorrect.',
          onSubmit: () => submitCalls++,
          onBack: () => backCalls++,
        ),
      ),
    );

    expect(find.text('Code incorrect.'), findsOneWidget);

    final primary = tester.widget<FanIdPrimaryButton>(
      find.byType(FanIdPrimaryButton),
    );
    final secondary = tester.widget<FanIdSecondaryButton>(
      find.byType(FanIdSecondaryButton),
    );

    expect(primary.loading, isTrue);
    expect(primary.onPressed, isNull);
    expect(secondary.onPressed, isNull);
    expect(submitCalls, 0);
    expect(backCalls, 0);
  });

  testWidgets('submits from code keyboard action', (tester) async {
    final code = TextEditingController();
    addTearDown(code.dispose);

    var submitCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetConfirmView(
          codeController: code,
          onSubmit: () => submitCalls++,
        ),
      ),
    );

    final codeField = find.byType(TextField);
    await tester.tap(codeField);
    await tester.enterText(codeField, '123456');
    await tester.testTextInput.receiveAction(TextInputAction.done);

    expect(submitCalls, 1);
  });
}
