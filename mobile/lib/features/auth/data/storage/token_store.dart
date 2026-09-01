import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStore {
  TokenStore({FlutterSecureStorage? secureStorage})
      : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  static const refreshTokenKey = 'auth_refresh_token';

  final FlutterSecureStorage _secureStorage;

  String? _accessToken;

  String? get accessToken => _accessToken;

  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _secureStorage.write(
      key: refreshTokenKey,
      value: refreshToken,
    );
    _accessToken = accessToken;
  }

  Future<String?> readRefreshToken() {
    return _secureStorage.read(key: refreshTokenKey);
  }

  Future<void> clear() async {
    _accessToken = null;
    await _secureStorage.delete(key: refreshTokenKey);
  }
}
