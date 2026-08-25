import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/presentation/views/register_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late TextEditingController firstName;
  late TextEditingController lastName;
  late TextEditingController email;
  late TextEditingController password;
  late TextEditingController phone;

  setUp(() {
    firstName = TextEditingController();
    lastName = TextEditingController();
    email = TextEditingController();
    password = TextEditingController();
    phone = TextEditingController();
  });

  tearDown(() {
    firstName.dispose();
    lastName.dispose();
    email.dispose();
    password.dispose();
    phone.dispose();
  });

  Widget wrap({
    DateTime? dateOfBirth,
    bool termsAccepted = false,
    bool isLoading = false,
    String? errorText,
    TextEditingController? phoneController,
    VoidCallback? onPickDate,
    ValueChanged<bool>? onTermsChanged,
    VoidCallback? onSubmit,
    VoidCallback? onBackToLogin,
  }) {
    return MaterialApp(
      theme: FanTheme.light,
      home: RegisterView(
        firstNameController: firstName,
        lastNameController: lastName,
        emailController: email,
        passwordController: password,
        phoneController: phoneController,
        dateOfBirth: dateOfBirth,
        termsAccepted: termsAccepted,
        isLoading: isLoading,
        errorText: errorText,
        onPickDate: onPickDate ?? () {},
        onTermsChanged: onTermsChanged ?? (_) {},
        onSubmit: onSubmit ?? () {},
        onBackToLogin: onBackToLogin,
      ),
    );
  }

  testWidgets('affiche le formulaire d inscription', (tester) async {
    await tester.pumpWidget(wrap(phoneController: phone));

    expect(find.text('Créer votre compte'), findsOneWidget);
    expect(find.text('Prénom'), findsOneWidget);
    expect(find.text('Nom'), findsOneWidget);
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Mot de passe'), findsOneWidget);
    expect(find.text('Téléphone (facultatif)'), findsOneWidget);
    expect(find.text('Sélectionner une date'), findsOneWidget);
    expect(find.text('Créer mon compte'), findsOneWidget);
  });

  testWidgets('affiche la date sélectionnée', (tester) async {
    await tester.pumpWidget(
      wrap(dateOfBirth: DateTime(1996, 5, 4)),
    );

    expect(find.text('04/05/1996'), findsOneWidget);
  });

  testWidgets('remonte les actions utilisateur', (tester) async {
    var picked = false;
    var accepted = false;
    var submitted = false;

    await tester.pumpWidget(
      wrap(
        onPickDate: () => picked = true,
        onTermsChanged: (value) => accepted = value,
        onSubmit: () => submitted = true,
      ),
    );

    final dateButton = find.text('Sélectionner une date');
    await tester.ensureVisible(dateButton);
    await tester.tap(dateButton);

    final checkbox = find.byType(Checkbox);
    await tester.ensureVisible(checkbox);
    await tester.tap(checkbox);

    final submitButton = find.byType(FanIdPrimaryButton);
    await tester.ensureVisible(submitButton);
    await tester.tap(submitButton);
    await tester.pump();

    expect(picked, isTrue);
    expect(accepted, isTrue);
    expect(submitted, isTrue);
  });

  testWidgets('affiche une erreur traduite', (tester) async {
    await tester.pumpWidget(
      wrap(
        errorText: 'Vous devez avoir au moins 16 ans pour créer un compte.',
      ),
    );

    expect(
      find.text('Vous devez avoir au moins 16 ans pour créer un compte.'),
      findsOneWidget,
    );
    expect(find.textContaining('UNDERAGE'), findsNothing);
  });

  testWidgets('loading neutralise les actions', (tester) async {
    var submitted = false;
    var picked = false;
    var changed = false;

    await tester.pumpWidget(
      wrap(
        isLoading: true,
        onSubmit: () => submitted = true,
        onPickDate: () => picked = true,
        onTermsChanged: (_) => changed = true,
      ),
    );

    final submitButton = find.byType(FanIdPrimaryButton);
    await tester.ensureVisible(submitButton);
    await tester.tap(submitButton);

    final dateButton = find.text('Sélectionner une date');
    await tester.ensureVisible(dateButton);
    await tester.tap(dateButton);

    final checkbox = find.byType(Checkbox);
    await tester.ensureVisible(checkbox);
    await tester.tap(checkbox);
    await tester.pump();

    expect(submitted, isFalse);
    expect(picked, isFalse);
    expect(changed, isFalse);
    expect(find.byType(CircularProgressIndicator), findsWidgets);
  });

  testWidgets('permet de revenir à la connexion', (tester) async {
    var back = false;

    await tester.pumpWidget(
      wrap(onBackToLogin: () => back = true),
    );

    final backButton = find.text('J’ai déjà un compte');
    await tester.ensureVisible(backButton);
    await tester.tap(backButton);
    await tester.pump();

    expect(back, isTrue);
  });
}
