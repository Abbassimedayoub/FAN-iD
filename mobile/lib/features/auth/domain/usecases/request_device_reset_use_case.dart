import '../entities/device_reset_challenge.dart';
import '../repositories/auth_repository.dart';

class RequestDeviceResetUseCase {
  const RequestDeviceResetUseCase(this.repository);

  final AuthRepository repository;

  Future<DeviceResetChallenge> call({
    required String email,
    required String password,
  }) {
    return repository.requestDeviceReset(
      email: email,
      password: password,
    );
  }
}
