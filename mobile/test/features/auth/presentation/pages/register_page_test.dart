import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/register_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/register_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  @override
  Future<void> requestScannerLeave() async {}

  int registerCalls = 0;

  @override
  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) async {
    registerCalls++;

    return AuthUser(
      id: 'user-id',
      email: email,
      firstName: firstName,
      lastName: lastName,
      role: 'FAN',
      createdAt: DateTime.utc(2026),
    );
  }

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) =>
      throw UnimplementedError();

  @override
  Future<LoginSession> refresh({String? fingerprint}) =>
      throw UnimplementedError();

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) =>
      throw UnimplementedError();

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) =>
      throw UnimplementedError();
}

Future<void> pumpPage(
  WidgetTester tester,
  FakeAuthRepository repository, {
  VoidCallback? onRegistered,
}) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        registerUseCaseProvider.overrideWithValue(
          RegisterUseCase(repository),
        ),
      ],
      child: MaterialApp(
        theme: FanTheme.light,
        home: RegisterPage(
          today: DateTime(2026, 8, 25),
          onRegistered: onRegistered,
        ),
      ),
    ),
  );

  await tester.pumpAndSettle();
}

Future<void> chooseBirthDay(
  WidgetTester tester,
  String day,
) async {
  final button = find.text('Sélectionner une date');
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();

  await tester.tap(find.text(day).last);
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}

Future<void> submit(WidgetTester tester) async {
  final button = find.byType(FanIdPrimaryButton);
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('refuse une date de naissance absente', (tester) async {
    final repository = FakeAuthRepository();

    await pumpPage(tester, repository);
    await submit(tester);

    expect(
      find.text('Sélectionnez votre date de naissance.'),
      findsOneWidget,
    );
    expect(repository.registerCalls, 0);
  });

  testWidgets('refuse un utilisateur de moins de 16 ans', (tester) async {
    final repository = FakeAuthRepository();

    await pumpPage(tester, repository);
    await chooseBirthDay(tester, '26');
    await submit(tester);

    expect(
      find.text(
        'Vous devez avoir au moins 16 ans pour créer un compte.',
      ),
      findsOneWidget,
    );
    expect(repository.registerCalls, 0);
  });

  testWidgets(
    'refuse les CGU non acceptées à exactement 16 ans',
    (tester) async {
      final repository = FakeAuthRepository();

      await pumpPage(tester, repository);
      await chooseBirthDay(tester, '25');
      await submit(tester);

      expect(
        find.text(
          'Vous devez accepter les conditions générales '
          'pour créer un compte.',
        ),
        findsOneWidget,
      );
      expect(repository.registerCalls, 0);
    },
  );

  testWidgets(
    'accepte exactement 16 ans et déclenche le succès',
    (tester) async {
      final repository = FakeAuthRepository();
      var registeredCalls = 0;

      await pumpPage(
        tester,
        repository,
        onRegistered: () => registeredCalls++,
      );

      final fields = find.byType(TextField);

      await tester.enterText(fields.at(0), 'Ines');
      await tester.enterText(fields.at(1), 'Bouzid');
      await tester.enterText(fields.at(2), 'fan@example.test');
      await tester.enterText(
        fields.at(3),
        'Strong-Password-2026',
      );

      await chooseBirthDay(tester, '25');

      final checkbox = find.byType(Checkbox);
      await tester.ensureVisible(checkbox);
      await tester.tap(checkbox);
      await tester.pump();

      await submit(tester);

      expect(repository.registerCalls, 1);
      expect(registeredCalls, 1);
      expect(find.textContaining('UNDERAGE'), findsNothing);
      expect(
        find.textContaining('TERMS_NOT_ACCEPTED'),
        findsNothing,
      );
    },
  );
}
