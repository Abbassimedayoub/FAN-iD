// PORTAGE : remplacer `fanid_mobile` par le nom de paquet reel du depot.
import 'package:fanid_mobile/features/auth/presentation/views/splash_view.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests de `SplashView`.
///
/// Le test central n est pas « le logo s affiche » — c est « rien ne se
/// declenche tout seul ». Une vue de splash qui navigue par elle-meme entre en
/// concurrence avec le `redirect` du routeur, et le conflit ne se voit que sur
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
    // indefiniment sur l animation du `CircularProgressIndicator` et ne
    // prouverait rien.
    await tester.pump(const Duration(seconds: 5));

    // La vue est toujours la : rien ne l a remplacee.
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

    // Un debordement de mise en page leve une `FlutterError` que
    // `takeException` recupere. `isNull` signifie donc : aucune bande jaune et
    // noire, sur un ecran volontairement court.
    expect(tester.takeException(), isNull);
  });
}
