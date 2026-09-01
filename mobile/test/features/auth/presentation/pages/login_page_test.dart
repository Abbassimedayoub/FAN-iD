import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/data/storage/device_fingerprint_store.dart';
import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/login_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/login_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
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

  FakeAuthRepository({this.loginFailure});

  final Failure? loginFailure;
  String? email;
  String? password;
  String? fingerprint;

  final session = LoginSession(
    access: 'access',
    refresh: 'refresh',
    user: AuthUser(
      id: 'user-id',
      email: 'fan@example.test',
      firstName: 'Ines',
      lastName: 'Bouzid',
      role: 'FAN',
      createdAt: DateTime.utc(2026),
    ),
    device: null,
  );

  @override
  Future<LoginSession> login({
    required String email,
    required String password,
    String? fingerprint,
    String? platform,
    String label = '',
  }) async {
    if (loginFailure case final failure?) {
      throw failure;
    }
    this.email = email;
    this.password = password;
    this.fingerprint = fingerprint;
    return session;
  }

  @override
  Future<LoginSession> refresh({String? fingerprint}) async => session;

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    return const DeviceResetChallenge(
      challengeId: 'challenge-id',
      expiresInSeconds: 600,
    );
  }

  @override
  Future<void> confirmDeviceReset({
    required String challengeId,
    required String code,
  }) async {}
}

void main() {
  testWidgets('submits LoginView through AuthController',
      (WidgetTester tester) async {
    FlutterSecureStorage.setMockInitialValues({
      DeviceFingerprintStore.fingerprintKey: 'b' * 64,
    });

    final repository = FakeAuthRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          tokenStoreProvider.overrideWithValue(TokenStore()),
          deviceFingerprintStoreProvider
              .overrideWithValue(DeviceFingerprintStore()),
          authRepositoryProvider.overrideWithValue(repository),
          loginUseCaseProvider.overrideWithValue(LoginUseCase(repository)),
        ],
        child: MaterialApp(
          theme: FanTheme.light,
          home: const LoginPage(),
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
    expect(repository.fingerprint, 'b' * 64);
  });

  testWidgets('calls onDeviceLocked for DEVICE_LOCKED',
      (WidgetTester tester) async {
    FlutterSecureStorage.setMockInitialValues({
      DeviceFingerprintStore.fingerprintKey: 'c' * 64,
    });

    final repository = FakeAuthRepository(
      loginFailure: const BusinessFailure(
        'DEVICE_LOCKED',
        'backend text must not be displayed',
        details: {
          'active_device_label': 'Pixel 8',
          'bound_at': '2026-08-24T18:00:00Z',
          'reset_available': true,
        },
      ),
    );
    var lockedCalls = 0;
    BusinessFailure? lockedFailure;

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          tokenStoreProvider.overrideWithValue(TokenStore()),
          deviceFingerprintStoreProvider
              .overrideWithValue(DeviceFingerprintStore()),
          authRepositoryProvider.overrideWithValue(repository),
          loginUseCaseProvider.overrideWithValue(LoginUseCase(repository)),
        ],
        child: MaterialApp(
          theme: FanTheme.light,
          home: LoginPage(
            onDeviceLocked: (failure) {
              lockedCalls++;
              lockedFailure = failure;
            },
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'fan@example.test');
    await tester.enterText(find.byType(TextField).last, 'secret');
    await tester.tap(find.byType(FanIdPrimaryButton));
    await tester.pumpAndSettle();

    expect(lockedCalls, 1);
    expect(lockedFailure?.code, 'DEVICE_LOCKED');
    expect(lockedFailure?.details['active_device_label'], 'Pixel 8');
    expect(lockedFailure?.details['reset_available'], isTrue);
    expect(find.textContaining('DEVICE_LOCKED'), findsNothing);
  });
}
