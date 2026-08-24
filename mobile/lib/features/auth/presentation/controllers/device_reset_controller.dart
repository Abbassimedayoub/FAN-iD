import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/entities/device_reset_challenge.dart';
import '../providers/auth_providers.dart';

final deviceResetControllerProvider =
    AsyncNotifierProvider<DeviceResetController, DeviceResetChallenge?>(
  DeviceResetController.new,
);

class DeviceResetController extends AsyncNotifier<DeviceResetChallenge?> {
  @override
  Future<DeviceResetChallenge?> build() async => null;

  Future<void> request({
    required String email,
    required String password,
  }) async {
    state = const AsyncLoading();

    state = await AsyncValue.guard(
      () => ref.read(requestDeviceResetUseCaseProvider)(
        email: email,
        password: password,
      ),
    );
  }

  Future<void> confirm({
    required String challengeId,
    required String code,
  }) async {
    state = const AsyncLoading();

    state = await AsyncValue.guard(() async {
      await ref.read(confirmDeviceResetUseCaseProvider)(
        challengeId: challengeId,
        code: code,
      );
      return null;
    });
  }
}
