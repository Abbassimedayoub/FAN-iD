import '../../../../core/errors/failure.dart';

const String genericRegisterErrorMessage =
    'Impossible de créer votre compte. Vérifiez vos informations et réessayez.';

String? mapRegisterFailureMessage(Object? error) {
  if (error == null) {
    return null;
  }

  if (error is BusinessFailure) {
    switch (error.code) {
      case 'EMAIL_ALREADY_EXISTS':
        return 'Un compte existe déjà pour cette adresse.';
      case 'UNDERAGE':
        return 'Vous devez avoir au moins 16 ans pour créer un compte.';
      case 'TERMS_NOT_ACCEPTED':
        return 'Vous devez accepter les conditions générales pour créer un compte.';
    }
  }

  if (error is NetworkFailure) {
    return 'Connexion indisponible. Vérifiez votre connexion et réessayez.';
  }

  if (error is PermissionFailure) {
    return 'Inscription refusée.';
  }

  if (error is NotFoundFailure) {
    return 'Service d’inscription indisponible.';
  }

  if (error is ServerFailure) {
    return 'Un problème est survenu. Réessayez plus tard.';
  }

  return genericRegisterErrorMessage;
}
