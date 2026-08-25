import 'package:fanid_mobile/features/auth/domain/entities/device_reset_challenge.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/auth_repository.dart';
import 'package:fanid_mobile/features/auth/domain/usecases/register_use_case.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeAuthRepository implements AuthRepository {
  String? email;
  String? password;
  String? firstName;
  String? lastName;
  DateTime? dateOfBirth;
  bool? termsAccepted;
  String? phone;

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
    this.password = password;
    this.firstName = firstName;
    this.lastName = lastName;
    this.dateOfBirth = dateOfBirth;
    this.termsAccepted = termsAccepted;
    this.phone = phone;
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

void main() {
  test('delegates the registration contract to the repository', () async {
    final repository = FakeAuthRepository();
    final useCase = RegisterUseCase(repository);
    final birthDate = DateTime.utc(1996, 5, 4);

    final result = await useCase(
      email: 'fan@example.test',
      password: 'Strong-Password-2026',
      firstName: 'Ines',
      lastName: 'Bouzid',
      dateOfBirth: birthDate,
      termsAccepted: true,
      phone: '+33600000000',
    );

    expect(result, same(repository.user));
    expect(repository.email, 'fan@example.test');
    expect(repository.password, 'Strong-Password-2026');
    expect(repository.firstName, 'Ines');
    expect(repository.lastName, 'Bouzid');
    expect(repository.dateOfBirth, birthDate);
    expect(repository.termsAccepted, isTrue);
    expect(repository.phone, '+33600000000');
  });
}
