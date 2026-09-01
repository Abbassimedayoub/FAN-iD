import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/confirm_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_reset_confirm_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  @override
  Future<void> requestScannerLeave() async {}

  @override
  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) {
    throw UnimplementedError();
  }

  Object? failure;
  String? challengeId;
  String? code;

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {
    this.challengeId = challengeId;
    this.code = code;
    if (failure != null) throw failure!;
  }

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) =>
      throw UnimplementedError();

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
}

Widget app(FakeAuthRepository repository, Widget child) => ProviderScope(
      overrides: [
        confirmDeviceResetUseCaseProvider.overrideWithValue(
          ConfirmDeviceResetUseCase(repository),
        ),
      ],
      child: MaterialApp(
        theme: FanTheme.light,
        home: child,
      ),
    );

const challenge = DeviceResetChallenge(
  challengeId: 'challenge-id',
  expiresInSeconds: 600,
);

void main() {
  testWidgets('confirms challenge and calls onConfirmed once', (tester) async {
    final repository = FakeAuthRepository();
    var confirmedCalls = 0;

    await tester.pumpWidget(
      app(
        repository,
        DeviceResetConfirmPage(
          challenge: challenge,
          onConfirmed: () => confirmedCalls++,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(confirmedCalls, 0);

    await tester.enterText(find.byType(TextField), ' 123456 ');
    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pumpAndSettle();

    expect(repository.challengeId, 'challenge-id');
    expect(repository.code, '123456');
    expect(confirmedCalls, 1);
  });

  final errorCases = <(Object, String)>[
    (
      const BusinessFailure('OTP_INVALID', 'backend'),
      'Code incorrect.',
    ),
    (
      const BusinessFailure('OTP_MAX_ATTEMPTS', 'backend'),
      'Trop de tentatives. Demandez un nouveau code.',
    ),
    (
      const NetworkFailure(),
      'Connexion indisponible. Vérifiez votre connexion et réessayez.',
    ),
    (
      const ServerFailure(),
      'Impossible de confirmer la réinitialisation. Réessayez.',
    ),
  ];

  for (final errorCase in errorCases) {
    testWidgets('maps confirm error ${errorCase.$2}', (tester) async {
      final repository = FakeAuthRepository()..failure = errorCase.$1;

      await tester.pumpWidget(
        app(
          repository,
          const DeviceResetConfirmPage(
            challenge: challenge,
            onConfirmed: _noop,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byType(FanIdPrimaryButton));
      await tester.pumpAndSettle();

      expect(find.text(errorCase.$2), findsOneWidget);
    });
  }
}

void _noop() {}
