import 'package:fanid_mobile/features/auth/presentation/views/login_view.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests de `LoginView`.
///
/// Aucun `ProviderScope`, aucun routeur, aucun controleur : la vue est
/// pilotee par ses props, donc testable en isolation. C est precisement ce
/// qui permet de couvrir tous ses etats sans monter l architecture auth.
void main() {
  late TextEditingController email;
  late TextEditingController password;

  setUp(() {
    email = TextEditingController(text: 'ayoub@fanid.app');
    password = TextEditingController(text: 'motdepasse');
  });

  tearDown(() {
    email.dispose();
    password.dispose();
  });

  Widget wrap({
    required VoidCallback onSubmit,
    bool isLoading = false,
    String? errorText,
    String? noticeText,
    TextScaler scaler = TextScaler.noScaling,
  }) {
    return MaterialApp(
      theme: FanTheme.light,
      home: MediaQuery(
        data: MediaQueryData(textScaler: scaler),
        child: LoginView(
          emailController: email,
          passwordController: password,
          isLoading: isLoading,
          errorText: errorText,
          noticeText: noticeText,
          onSubmit: onSubmit,
        ),
      ),
    );
  }

  testWidgets('affiche le contenu de la maquette FAN-04',
      (WidgetTester tester) async {
    await tester.pumpWidget(wrap(onSubmit: () {}));

    expect(find.text('Bon retour !'), findsOneWidget);
    expect(find.text('Se connecter'), findsOneWidget);
    expect(find.text('Mot de passe oublié ?'), findsOneWidget);
    expect(find.text('Créer un compte'), findsOneWidget);
    expect(find.text(LoginView.deviceBindingNotice), findsOneWidget);
  });

  testWidgets('un appui sur « Se connecter » appelle onSubmit une fois',
      (WidgetTester tester) async {
    int submits = 0;
    await tester.pumpWidget(wrap(onSubmit: () => submits++));

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pump();

    expect(submits, 1);
  });

  testWidgets('isLoading = true : le bouton n appelle PAS onSubmit',
      (WidgetTester tester) async {
    int submits = 0;
    await tester.pumpWidget(wrap(onSubmit: () => submits++, isLoading: true));

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pump();

    expect(submits, 0);
    expect(find.byType(CircularProgressIndicator), findsWidgets);
  });

  testWidgets('isLoading = true : la touche Entree n appelle PAS onSubmit',
      (WidgetTester tester) async {
    // Le piege classique de cet ecran : le bouton est grise mais le clavier
    // continue de soumettre, et le backend recoit deux tentatives.
    int submits = 0;
    await tester.pumpWidget(wrap(onSubmit: () => submits++, isLoading: true));

    final Finder passwordField = find.byType(TextField).last;
    await tester.tap(passwordField);
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    expect(submits, 0);
  });

  testWidgets('isLoading = false : la touche Entree appelle onSubmit',
      (WidgetTester tester) async {
    int submits = 0;
    await tester.pumpWidget(wrap(onSubmit: () => submits++));

    await tester.tap(find.byType(TextField).last);
    await tester.pump();
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pump();

    expect(submits, 1);
  });

  testWidgets('errorText s affiche en toutes lettres sous le champ',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      wrap(
        onSubmit: () {},
        errorText: 'Mot de passe incorrect. Réessayez.',
      ),
    );

    expect(find.text('Mot de passe incorrect. Réessayez.'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('aucun code machine ne peut apparaitre a l ecran',
      (WidgetTester tester) async {
    // La vue affiche ce qu on lui donne. Ce test garde la CONVENTION : si un
    // jour quelqu un branche `failure.code` directement sur `errorText`, la
    // chaine « DEVICE_LOCKED » apparaitrait — et ce test le dirait.
    await tester.pumpWidget(
      wrap(
        onSubmit: () {},
        errorText: 'Cet appareil est verrouillé.',
        noticeText: LoginView.sessionExpiredNotice,
      ),
    );

    for (final String code in <String>[
      'DEVICE_LOCKED',
      'INVALID_CREDENTIALS',
      'AUTH_FAILURE',
      'BusinessFailure',
    ]) {
      expect(
        find.textContaining(code),
        findsNothing,
        reason: 'Un code machine ne doit jamais atteindre l ecran : $code',
      );
    }
  });

  testWidgets(
      'noticeText affiche le bandeau de session expiree SANS effacer '
      'l avertissement de liaison d appareil', (WidgetTester tester) async {
    await tester.pumpWidget(
      wrap(onSubmit: () {}, noticeText: LoginView.sessionExpiredNotice),
    );

    expect(find.text(LoginView.sessionExpiredNotice), findsOneWidget);
    expect(find.text(LoginView.deviceBindingNotice), findsOneWidget);
  });

  testWidgets('sans noticeText, aucun bandeau de session n est affiche',
      (WidgetTester tester) async {
    await tester.pumpWidget(wrap(onSubmit: () {}));
    expect(find.text(LoginView.sessionExpiredNotice), findsNothing);
  });

  testWidgets('supporte une echelle de texte de 2.0 sans debordement',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      wrap(
        onSubmit: () {},
        errorText: 'Mot de passe incorrect. Réessayez.',
        noticeText: LoginView.sessionExpiredNotice,
        scaler: const TextScaler.linear(2),
      ),
    );
    await tester.pump();

    expect(tester.takeException(), isNull);
  });
}
