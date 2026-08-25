import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/request_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_reset_request_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
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
  String? email;
  String? password;

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    this.email = email;
    this.password = password;

    if (failure != null) {
      throw failure!;
    }

    return const DeviceResetChallenge(
      challengeId: 'challenge-id',
      expiresInSeconds: 600,
    );
  }

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
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

Widget app(FakeAuthRepository repository, Widget child) {
  return ProviderScope(
    overrides: [
      requestDeviceResetUseCaseProvider.overrideWithValue(
        RequestDeviceResetUseCase(repository),
      ),
    ],
    child: MaterialApp(
      theme: FanTheme.light,
      home: child,
    ),
  );
}

void main() {
  testWidgets('submits credentials and exposes the challenge', (tester) async {
    final repository = FakeAuthRepository();
    DeviceResetChallenge? challenge;

    await tester.pumpWidget(
      app(
        repository,
        DeviceResetRequestPage(
          onChallenge: (value) => challenge = value,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, ' fan@example.test ');
    await tester.enterText(find.byType(TextField).last, 'secret');
    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pumpAndSettle();

    expect(repository.email, 'fan@example.test');
    expect(repository.password, 'secret');
    expect(challenge?.challengeId, 'challenge-id');
    expect(challenge?.expiresInSeconds, 600);
  });

  testWidgets('shows the network error message', (tester) async {
    final repository = FakeAuthRepository()..failure = const NetworkFailure();

    await tester.pumpWidget(
      app(
        repository,
        DeviceResetRequestPage(onChallenge: (_) {}),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Connexion indisponible. Vérifiez votre connexion et réessayez.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('shows the generic reset request error', (tester) async {
    final repository = FakeAuthRepository()..failure = const ServerFailure();

    await tester.pumpWidget(
      app(
        repository,
        DeviceResetRequestPage(onChallenge: (_) {}),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pumpAndSettle();

    expect(
      find.text('Impossible d’envoyer le code. Réessayez.'),
      findsOneWidget,
    );
  });
}
