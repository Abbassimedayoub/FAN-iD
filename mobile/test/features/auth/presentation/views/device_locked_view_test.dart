import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/presentation/views/device_locked_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget app(Widget child) => MaterialApp(
      theme: FanTheme.light,
      home: child,
    );

void main() {
  testWidgets('shows device details and forwards actions', (tester) async {
    var resetCalls = 0;
    var backCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceLockedView(
          activeDeviceLabel: 'Pixel 8',
          boundAtText: '24 août 2026',
          resetAvailable: true,
          onReset: () => resetCalls++,
          onBackToLogin: () => backCalls++,
        ),
      ),
    );

    expect(find.text('Pixel 8'), findsOneWidget);
    expect(find.text('Associé le 24 août 2026'), findsOneWidget);

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.tap(find.byType(FanIdSecondaryButton));

    expect(resetCalls, 1);
    expect(backCalls, 1);
  });

  testWidgets('disables reset when unavailable', (tester) async {
    var resetCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceLockedView(
          resetAvailable: false,
          onReset: () => resetCalls++,
        ),
      ),
    );

    expect(
      find.text('La réinitialisation de l’appareil n’est pas disponible.'),
      findsOneWidget,
    );

    await tester.tap(find.byType(FanIdPrimaryButton));

    expect(resetCalls, 0);
  });
}
