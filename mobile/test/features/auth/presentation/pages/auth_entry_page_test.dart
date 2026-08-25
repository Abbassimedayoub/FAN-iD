import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/data/storage/device_fingerprint_store.dart';
import 'package:fanid_mobile/features/auth/data/storage/token_store.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/confirm_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/login_use_case.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/register_use_case.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/request_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/auth_entry_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_locked_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_reset_confirm_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/device_reset_request_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/login_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/register_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:fanid_mobile/features/auth/presentation/views/login_view.dart';
import 'package:fanid_mobile/features/auth/presentation/views/splash_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  Object? loginFailure;
  int confirmCalls = 0;

  final session = LoginSession(
    access: 'access-token',
    refresh: 'refresh-token',
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
  Future<AuthUser> register({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    required DateTime dateOfBirth,
    required bool termsAccepted,
    String? phone,
  }) async {
    return AuthUser(
      id: 'registered-user',
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
  }) async {
    final failure = loginFailure;
    if (failure != null) {
      throw failure;
    }

    return session;
  }

  @override
  Future<LoginSession> refresh({String? fingerprint}) async {
    return session;
  }

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
  }) async {
    confirmCalls++;
  }
}

ProviderContainer makeContainer(FakeAuthRepository repository) {
  final tokenStore = TokenStore();
  final fingerprintStore = DeviceFingerprintStore(
    randomBytes: (length) => List<int>.filled(length, 1),
  );

  final container = ProviderContainer(
    overrides: [
      tokenStoreProvider.overrideWithValue(tokenStore),
      deviceFingerprintStoreProvider.overrideWithValue(fingerprintStore),
      authRepositoryProvider.overrideWithValue(repository),
      loginUseCaseProvider.overrideWithValue(LoginUseCase(repository)),
      registerUseCaseProvider.overrideWithValue(RegisterUseCase(repository)),
      requestDeviceResetUseCaseProvider.overrideWithValue(
        RequestDeviceResetUseCase(repository),
      ),
      confirmDeviceResetUseCaseProvider.overrideWithValue(
        ConfirmDeviceResetUseCase(repository),
      ),
    ],
  );

  addTearDown(container.dispose);
  return container;
}

Future<void> pumpShell(
  WidgetTester tester,
  ProviderContainer container, {
  bool settle = true,
}) async {
  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: FanTheme.light,
        home: const AuthEntryPage(),
      ),
    ),
  );

  if (settle) {
    await tester.pumpAndSettle();
  }
}

Future<void> tapPrimaryButton(WidgetTester tester) async {
  final button = find.byType(FanIdPrimaryButton);
  await tester.ensureVisible(button);
  await tester.tap(button);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    FlutterSecureStorage.setMockInitialValues({});
  });

  testWidgets('affiche Splash puis Login sans refresh token', (tester) async {
    final container = makeContainer(FakeAuthRepository());

    await pumpShell(tester, container, settle: false);

    expect(find.byType(SplashView), findsOneWidget);

    await tester.pumpAndSettle();

    expect(find.byType(SplashView), findsNothing);
    expect(find.byType(LoginPage), findsOneWidget);
  });

  testWidgets('navigue de Login vers Register puis revient à Login',
      (tester) async {
    final container = makeContainer(FakeAuthRepository());

    await pumpShell(tester, container);

    expect(find.byType(LoginPage), findsOneWidget);

    final registerLink = find.text('Créer un compte');
    await tester.ensureVisible(registerLink);
    await tester.tap(registerLink);
    await tester.pumpAndSettle();

    expect(find.byType(RegisterPage), findsOneWidget);

    final loginLink = find.text('J’ai déjà un compte');
    await tester.ensureVisible(loginLink);
    await tester.tap(loginLink);
    await tester.pumpAndSettle();

    expect(find.byType(LoginPage), findsOneWidget);
    expect(find.byType(RegisterPage), findsNothing);
  });

  testWidgets(
    'enchaîne DEVICE_LOCKED puis reset appareil et revient au Login',
    (tester) async {
      final repository = FakeAuthRepository()
        ..loginFailure = const BusinessFailure(
          'DEVICE_LOCKED',
          'backend text must not be displayed',
          details: {
            'active_device_label': 'Pixel 8',
            'bound_at': '2026-08-24T18:00:00Z',
            'reset_available': true,
          },
        );

      final container = makeContainer(repository);

      await pumpShell(tester, container);

      await tester.enterText(
        find.byType(TextField).first,
        'fan@example.test',
      );
      await tester.enterText(
        find.byType(TextField).last,
        'secret',
      );
      await tapPrimaryButton(tester);

      expect(find.byType(DeviceLockedPage), findsOneWidget);
      expect(find.textContaining('DEVICE_LOCKED'), findsNothing);

      await tapPrimaryButton(tester);

      expect(find.byType(DeviceResetRequestPage), findsOneWidget);

      await tester.enterText(
        find.byType(TextField).first,
        'fan@example.test',
      );
      await tester.enterText(
        find.byType(TextField).last,
        'secret',
      );
      await tapPrimaryButton(tester);

      expect(find.byType(DeviceResetConfirmPage), findsOneWidget);

      await tester.enterText(find.byType(TextField), '123456');
      await tapPrimaryButton(tester);

      expect(repository.confirmCalls, 1);
      expect(find.byType(LoginPage), findsOneWidget);
      expect(
        find.text(
          'Votre appareil a été réinitialisé. Reconnectez-vous.',
        ),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'les retours ResetConfirm puis ResetRequest reviennent aux écrans précédents',
    (tester) async {
      final repository = FakeAuthRepository()
        ..loginFailure = const BusinessFailure(
          'DEVICE_LOCKED',
          'backend text must not be displayed',
          details: {
            'active_device_label': 'Pixel 8',
            'bound_at': '2026-08-24T18:00:00Z',
            'reset_available': true,
          },
        );

      final container = makeContainer(repository);

      await pumpShell(tester, container);

      await tester.enterText(
        find.byType(TextField).first,
        'fan@example.test',
      );
      await tester.enterText(
        find.byType(TextField).last,
        'secret',
      );
      await tapPrimaryButton(tester);

      expect(find.byType(DeviceLockedPage), findsOneWidget);

      await tapPrimaryButton(tester);

      expect(find.byType(DeviceResetRequestPage), findsOneWidget);

      await tester.enterText(
        find.byType(TextField).first,
        'fan@example.test',
      );
      await tester.enterText(
        find.byType(TextField).last,
        'secret',
      );
      await tapPrimaryButton(tester);

      expect(find.byType(DeviceResetConfirmPage), findsOneWidget);

      await tester.tap(find.text('Retour'));
      await tester.pumpAndSettle();

      expect(find.byType(DeviceResetRequestPage), findsOneWidget);

      await tester.tap(find.text('Retour'));
      await tester.pumpAndSettle();

      expect(find.byType(DeviceLockedPage), findsOneWidget);
    },
  );

  testWidgets('affiche la notice après expiration de session', (tester) async {
    final container = makeContainer(FakeAuthRepository());

    await pumpShell(tester, container);

    expect(find.byType(LoginPage), findsOneWidget);
    expect(
      find.text(LoginView.sessionExpiredNotice),
      findsNothing,
    );

    container.read(authExpiryGenerationProvider.notifier).state++;

    await tester.pumpAndSettle();

    expect(find.byType(LoginPage), findsOneWidget);
    expect(
      find.text(LoginView.sessionExpiredNotice),
      findsOneWidget,
    );
  });
}
