import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class DeviceFingerprintStore {
  DeviceFingerprintStore({
    FlutterSecureStorage? secureStorage,
    List<int> Function(int length)? randomBytes,
  })  : _secureStorage = secureStorage ?? const FlutterSecureStorage(),
        _randomBytes = randomBytes ?? _secureRandomBytes;

  static const fingerprintKey = 'device_fingerprint';

  final FlutterSecureStorage _secureStorage;
  final List<int> Function(int length) _randomBytes;

  Future<String> getOrCreate() async {
    final existing = await _secureStorage.read(key: fingerprintKey);
    if (existing != null) {
      return existing;
    }

    final bytes = _randomBytes(32);
    if (bytes.length != 32) {
      throw StateError('Fingerprint generator must return 32 bytes');
    }

    final fingerprint =
        bytes.map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();

    await _secureStorage.write(
      key: fingerprintKey,
      value: fingerprint,
    );

    return fingerprint;
  }

  static List<int> _secureRandomBytes(int length) {
    final random = Random.secure();
    return List.generate(length, (_) => random.nextInt(256));
  }
}
