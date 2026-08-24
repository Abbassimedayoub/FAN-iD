import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/presentation/mappers/login_failure_mapper.dart';

void main() {
  test('maps credential failures safely', () {
    expect(
      mapLoginFailureMessage(
        const BusinessFailure('INVALID_CREDENTIALS', 'backend text'),
      ),
      invalidCredentialsMessage,
    );
    expect(
      mapLoginFailureMessage(const AuthFailure()),
      invalidCredentialsMessage,
    );
  });

  test('detects DEVICE_LOCKED without displaying backend text', () {
    const failure = BusinessFailure('DEVICE_LOCKED', 'backend text');

    expect(isDeviceLockedFailure(failure), isTrue);
    expect(mapLoginFailureMessage(failure), isNull);
    expect(mapLoginFailureMessage(null), isNull);
  });

  test('maps infrastructure failures', () {
    expect(
      mapLoginFailureMessage(const NetworkFailure()),
      'Connexion indisponible. Vérifiez votre connexion et réessayez.',
    );
    expect(mapLoginFailureMessage(const PermissionFailure()), 'Accès refusé.');
    expect(
      mapLoginFailureMessage(const NotFoundFailure()),
      'Service de connexion indisponible.',
    );
    expect(
      mapLoginFailureMessage(const ServerFailure()),
      'Un problème est survenu. Réessayez plus tard.',
    );
  });

  test('does not expose unknown errors', () {
    expect(
      mapLoginFailureMessage(const BusinessFailure('OTHER', 'backend text')),
      genericLoginErrorMessage,
    );
    expect(
      mapLoginFailureMessage(Exception('unexpected')),
      genericLoginErrorMessage,
    );
  });
}
