import '../../../../core/errors/failure.dart';

const String invalidCredentialsMessage = 'Adresse ou mot de passe incorrect.';

const String genericLoginErrorMessage =
    'Impossible de vous connecter. Réessayez.';

bool isDeviceLockedFailure(Object? error) =>
    error is BusinessFailure && error.code == 'DEVICE_LOCKED';

String? mapLoginFailureMessage(Object? error) {
  if (error == null || isDeviceLockedFailure(error)) {
    return null;
  }

  if (error is BusinessFailure && error.code == 'INVALID_CREDENTIALS') {
    return invalidCredentialsMessage;
  }

  if (error is AuthFailure) {
    return invalidCredentialsMessage;
  }

  if (error is NetworkFailure) {
    return 'Connexion indisponible. Vérifiez votre connexion et réessayez.';
  }

  if (error is PermissionFailure) {
    return 'Accès refusé.';
  }

  if (error is NotFoundFailure) {
    return 'Service de connexion indisponible.';
  }

  if (error is ServerFailure) {
    return 'Un problème est survenu. Réessayez plus tard.';
  }

  return genericLoginErrorMessage;
}
