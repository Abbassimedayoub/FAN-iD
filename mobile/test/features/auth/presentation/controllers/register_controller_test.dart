import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/register_use_case.dart';
import 'package:fanid_mobile/features/auth/presentation/controllers/register_controller.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  Object? failure;
  String? email;
  String? firstName;
  DateTime? dateOfBirth;
  bool? termsAccepted;

  final user = AuthUser(
    id: 'user-id',
    email: 'fan@example.test',
    firstName: 'Ines',
    lastName: 'Bouzid',
    role: 'FAN',
    createdAt: DateTime.utc(2026),
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
    this.email = email;
    this.firstName = firstName;
    this.dateOfBirth = dateOfBirth;
    this.termsAccepted = termsAccepted;
    if (failure != null) throw failure!;
    return user;
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

ProviderContainer makeContainer(FakeAuthRepository repository) {
  final container = ProviderContainer(
    overrides: [
      registerUseCaseProvider.overrideWithValue(RegisterUseCase(repository)),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('registers and exposes the created user', () async {
    final repository = FakeAuthRepository();
    final container = makeContainer(repository);
    final birthDate = DateTime.utc(1996, 5, 4);

    await container.read(registerControllerProvider.future);
    await container.read(registerControllerProvider.notifier).register(
          email: 'fan@example.test',
          password: 'Strong-Password-2026',
          firstName: 'Ines',
          lastName: 'Bouzid',
          dateOfBirth: birthDate,
          termsAccepted: true,
        );

    expect(container.read(registerControllerProvider).value,
        same(repository.user));
    expect(repository.email, 'fan@example.test');
    expect(repository.firstName, 'Ines');
    expect(repository.dateOfBirth, birthDate);
    expect(repository.termsAccepted, isTrue);
  });

  test('exposes registration failure', () async {
    final repository = FakeAuthRepository()..failure = const ServerFailure();
    final container = makeContainer(repository);

    await container.read(registerControllerProvider.future);
    await container.read(registerControllerProvider.notifier).register(
          email: 'fan@example.test',
          password: 'Strong-Password-2026',
          firstName: 'Ines',
          lastName: 'Bouzid',
          dateOfBirth: DateTime.utc(1996, 5, 4),
          termsAccepted: true,
        );

    expect(
      container.read(registerControllerProvider).error,
      isA<ServerFailure>(),
    );
  });
}
