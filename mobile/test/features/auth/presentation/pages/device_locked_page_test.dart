import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_locked_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget app(Widget child) => MaterialApp(
      theme: FanTheme.light,
      home: child,
    );

void main() {
  testWidgets('maps device lock details to the view', (tester) async {
    var resetCalls = 0;

    await tester.pumpWidget(
      app(
        DeviceLockedPage(
          failure: const BusinessFailure(
            'DEVICE_LOCKED',
            'backend message',
            details: {
              'active_device_label': 'Pixel 8',
              'bound_at': '2026-08-24T18:00:00Z',
              'reset_available': true,
            },
          ),
          onReset: () => resetCalls++,
        ),
      ),
    );

    expect(find.text('Pixel 8'), findsOneWidget);
    expect(
      find.text('Associé le 2026-08-24T18:00:00Z'),
      findsOneWidget,
    );

    await tester.tap(find.byType(FanIdPrimaryButton));
    expect(resetCalls, 1);
  });

  testWidgets('ignores invalid optional details', (tester) async {
    await tester.pumpWidget(
      app(
        const DeviceLockedPage(
          failure: BusinessFailure(
            'DEVICE_LOCKED',
            'backend message',
            details: {
              'active_device_label': 123,
              'bound_at': false,
              'reset_available': 'true',
            },
          ),
        ),
      ),
    );

    expect(find.text('123'), findsNothing);
    expect(find.textContaining('Associé le'), findsNothing);
    expect(
      find.text('La réinitialisation de l’appareil n’est pas disponible.'),
      findsOneWidget,
    );
  });
}
