import '../repositories/auth_repository.dart';

class ConfirmDeviceResetUseCase {
  const ConfirmDeviceResetUseCase(this.repository);

  final AuthRepository repository;

  Future<void> call({
    required String challengeId,
    required String code,
  }) {
    return repository.confirmDeviceReset(
      challengeId: challengeId,
      code: code,
    );
  }
}
