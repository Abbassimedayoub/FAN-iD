import '../../../../core/errors/failure.dart';

String mapPasswordResetFailure(Object? error) {
  if (error is BusinessFailure) {
    switch (error.code) {
      case 'PASSWORD_RESET_INVALID':
        return 'Le code est invalide ou a expiré. Demandez un nouveau code.';
      case 'OTP_MAX_ATTEMPTS':
        return 'Trop de codes incorrects. Demandez un nouveau code.';
      case 'RATE_LIMIT_EXCEEDED':
        return 'Trop de tentatives. Réessayez un peu plus tard.';
      case 'PASSWORD_UNCHANGED':
        return 'Choisissez un mot de passe différent de l’ancien.';
      case 'VALIDATION_ERROR':
        return 'Le nouveau mot de passe ne respecte pas les règles de sécurité.';
    }
  }

  if (error is NetworkFailure) {
    return 'Connexion indisponible. Vérifiez votre connexion et réessayez.';
  }

  if (error is ServerFailure) {
    return 'Le service est momentanément indisponible. Réessayez plus tard.';
  }

  return 'Impossible de réinitialiser le mot de passe. Réessayez.';
}
