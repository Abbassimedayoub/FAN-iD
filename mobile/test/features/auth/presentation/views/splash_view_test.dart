// Porting note: replace `fanid_mobile` with the repository's actual package name.
import 'package:fanid_mobile/features/auth/presentation/views/splash_view.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests de `SplashView`.
///
/// The central test is not merely that the logo renders; it verifies that the
/// splash view triggers no navigation by itself and cannot race the router redirect.
/// un reseau lent, en production.
void main() {
  Widget wrap(Widget child, {TextScaler scaler = TextScaler.noScaling}) {
    return MaterialApp(
      theme: FanTheme.light,
      home: MediaQuery(
        data: MediaQueryData(textScaler: scaler),
        child: child,
      ),
    );
  }

  testWidgets('affiche le contenu de la maquette FAN-01',
      (WidgetTester tester) async {
    await tester.pumpWidget(wrap(const SplashView()));

    expect(find.text(SplashView.tagline), findsOneWidget);
    expect(find.text('v1.0.0'), findsOneWidget);
    expect(find.byType(FanIdWordmark), findsOneWidget);
    expect(find.byType(FanIdLogo), findsOneWidget);
    expect(find.byType(LoadingView), findsOneWidget);
  });

  testWidgets('AUCUNE navigation temporelle : la vue est stable dans le temps',
      (WidgetTester tester) async {
    await tester.pumpWidget(wrap(const SplashView()));

    // On avance largement au-dela du `Timer` de 1,6 s du prototype d origine.
    // `pump` explicite plutot que `pumpAndSettle` : `pumpAndSettle` boucle
    // Avoid waiting indefinitely on the CircularProgressIndicator animation.
    // prouverait rien.
    await tester.pump(const Duration(seconds: 5));

    // The view is still present; nothing has replaced it.
    expect(find.byType(SplashView), findsOneWidget);
    expect(find.text(SplashView.tagline), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('le libelle de statut est annonce et personnalisable',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      wrap(const SplashView(statusLabel: 'Reconnexion sécurisée…')),
    );
    expect(find.text('Reconnexion sécurisée…'), findsOneWidget);
  });

  testWidgets('supporte une echelle de texte de 2.0 sans debordement',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      wrap(const SplashView(), scaler: const TextScaler.linear(2)),
    );
    await tester.pump();

    // Layout overflow raises a FlutterError captured by takeException; null
    // therefore means the deliberately short screen did not overflow.
    expect(tester.takeException(), isNull);
  });
}
