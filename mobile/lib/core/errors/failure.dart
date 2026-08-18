/// Taxonomie d'échecs (§4.4 Source B) — `Failure` scellée, mappée sur les
/// cinq états d'écran (§4.2 Source B) au niveau présentation via `AsyncValue`.
sealed class Failure {
  const Failure(this.message);

  final String message;
}

final class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'Connexion indisponible']);
}

final class AuthFailure extends Failure {
  const AuthFailure([super.message = 'Session expirée']);
}

final class PermissionFailure extends Failure {
  const PermissionFailure([super.message = 'Accès interdit']);
}

final class NotFoundFailure extends Failure {
  const NotFoundFailure([super.message = 'Introuvable']);
}

/// Erreur métier — `code` est le contrat machine stable (§17 master prompt),
/// jamais utilisé pour construire le message affiché directement.
final class BusinessFailure extends Failure {
  const BusinessFailure(this.code, super.message, {this.details = const {}});

  final String code;
  final Map<String, dynamic> details;
}

final class ServerFailure extends Failure {
  const ServerFailure(
      [super.message = 'Un problème est survenu de notre côté']);
}
