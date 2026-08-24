import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/presentation/views/device_reset_request_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget app(Widget child) => MaterialApp(
      theme: FanTheme.light,
      home: child,
    );

void main() {
  testWidgets('forwards submit and back actions', (tester) async {
    final email = TextEditingController();
    final password = TextEditingController();
    addTearDown(email.dispose);
    addTearDown(password.dispose);

    var submitCalls = 0;
    var backCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetRequestView(
          emailController: email,
          passwordController: password,
          onSubmit: () => submitCalls++,
          onBack: () => backCalls++,
        ),
      ),
    );

    await tester.enterText(find.byType(TextField).first, 'fan@example.test');
    await tester.enterText(find.byType(TextField).last, 'secret');

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.tap(find.byType(FanIdSecondaryButton));

    expect(email.text, 'fan@example.test');
    expect(password.text, 'secret');
    expect(submitCalls, 1);
    expect(backCalls, 1);
  });

  testWidgets('shows error and disables actions while loading', (tester) async {
    final email = TextEditingController();
    final password = TextEditingController();
    addTearDown(email.dispose);
    addTearDown(password.dispose);

    var submitCalls = 0;
    var backCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetRequestView(
          emailController: email,
          passwordController: password,
          isLoading: true,
          errorText: 'Connexion indisponible.',
          onSubmit: () => submitCalls++,
          onBack: () => backCalls++,
        ),
      ),
    );

    expect(find.text('Connexion indisponible.'), findsOneWidget);

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

  testWidgets('submits from password keyboard action', (tester) async {
    final email = TextEditingController();
    final password = TextEditingController();
    addTearDown(email.dispose);
    addTearDown(password.dispose);

    var submitCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceResetRequestView(
          emailController: email,
          passwordController: password,
          onSubmit: () => submitCalls++,
        ),
      ),
    );

    final passwordField = find.byType(TextField).last;
    await tester.tap(passwordField);
    await tester.enterText(passwordField, 'secret');
    await tester.testTextInput.receiveAction(TextInputAction.done);

    expect(submitCalls, 1);
  });
}
