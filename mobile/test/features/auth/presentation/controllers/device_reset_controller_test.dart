import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/confirm_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/request_device_reset_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/controllers/device_reset_controller.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
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

  Object? requestFailure;
  Object? confirmFailure;

  String? email;
  String? password;
  String? challengeId;
  String? code;

  @override
  Future<DeviceResetChallenge> requestDeviceReset({
    required String email,
    required String password,
  }) async {
    this.email = email;
    this.password = password;

    final failure = requestFailure;
    if (failure != null) {
      throw failure;
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
  }) async {
    this.challengeId = challengeId;
    this.code = code;

    final failure = confirmFailure;
    if (failure != null) {
      throw failure;
    }
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
}

ProviderContainer makeContainer(FakeAuthRepository repository) {
  final container = ProviderContainer(
    overrides: [
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

void main() {
  test('requests a reset challenge', () async {
    final repository = FakeAuthRepository();
    final container = makeContainer(repository);

    await container.read(deviceResetControllerProvider.future);
    await container.read(deviceResetControllerProvider.notifier).request(
          email: 'fan@example.test',
          password: 'secret',
        );

    final state = container.read(deviceResetControllerProvider);

    expect(state.value?.challengeId, 'challenge-id');
    expect(state.value?.expiresInSeconds, 600);
    expect(repository.email, 'fan@example.test');
    expect(repository.password, 'secret');
  });

  test('exposes reset request failure', () async {
    final repository = FakeAuthRepository()
      ..requestFailure = const ServerFailure();
    final container = makeContainer(repository);

    await container.read(deviceResetControllerProvider.future);
    await container.read(deviceResetControllerProvider.notifier).request(
          email: 'fan@example.test',
          password: 'secret',
        );

    expect(
      container.read(deviceResetControllerProvider).error,
      isA<ServerFailure>(),
    );
  });

  test('confirms a reset challenge and returns to idle', () async {
    final repository = FakeAuthRepository();
    final container = makeContainer(repository);

    await container.read(deviceResetControllerProvider.future);
    await container.read(deviceResetControllerProvider.notifier).confirm(
          challengeId: 'challenge-id',
          code: '123456',
        );

    final state = container.read(deviceResetControllerProvider);

    expect(state.hasValue, isTrue);
    expect(state.value, isNull);
    expect(repository.challengeId, 'challenge-id');
    expect(repository.code, '123456');
  });

  test('exposes reset confirmation failure', () async {
    final repository = FakeAuthRepository()
      ..confirmFailure = const ServerFailure();
    final container = makeContainer(repository);

    await container.read(deviceResetControllerProvider.future);
    await container.read(deviceResetControllerProvider.notifier).confirm(
          challengeId: 'challenge-id',
          code: '123456',
        );

    expect(
      container.read(deviceResetControllerProvider).error,
      isA<ServerFailure>(),
    );
  });
}
