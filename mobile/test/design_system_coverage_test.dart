import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('covers remaining design system variants',
      (WidgetTester tester) async {
    int actions = 0;

    await tester.pumpWidget(
      MaterialApp(
        theme: FanTheme.light,
        home: Scaffold(
          body: SingleChildScrollView(
            child: Column(
              children: <Widget>[
                FanIdPrimaryButton(
                  label: 'Avec icône',
                  icon: Icons.login,
                  onPressed: () {},
                ),
                const FanIdTextField(
                  label: 'Mot de passe',
                  obscure: true,
                ),
                const FanIdLogo(size: 48),
                const FanIdWordmark(),
                const FanIdBrandRow(),
                const NavyBackdrop(
                  child: SizedBox(width: 16, height: 16),
                ),
                const NavyNoticeBanner(
                  icon: Icons.info_outline,
                  message: 'Information',
                  onLight: true,
                ),
                const LoadingView(
                  message: 'Chargement',
                  onDark: true,
                ),
                EmptyView(
                  title: 'Vide',
                  message: 'Aucun contenu',
                  actionLabel: 'Action',
                  onAction: () => actions++,
                ),
                ErrorView(
                  title: 'Erreur',
                  message: 'Réessayez plus tard',
                  onRetry: () => actions++,
                ),
              ],
            ),
          ),
        ),
      ),
    );

    await tester.pump();

    expect(
      find.byIcon(Icons.confirmation_number_outlined),
      findsNWidgets(2),
    );

    await tester.tap(find.text('Afficher'));
    await tester.pump();
    expect(find.text('Masquer'), findsOneWidget);

    await tester.ensureVisible(find.text('Action'));
    await tester.pump();
    await tester.tap(find.text('Action'));

    await tester.ensureVisible(find.text('Réessayer'));
    await tester.pump();
    await tester.tap(find.text('Réessayer'));

    expect(actions, 2);
  });
}
