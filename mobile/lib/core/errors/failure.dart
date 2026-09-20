/// Failure taxonomy. Presentation maps these sealed failures to screen states
/// through `AsyncValue`.
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

/// Business error: `code` is the stable machine contract and is never used
/// directly to build the user-facing message.
final class BusinessFailure extends Failure {
  const BusinessFailure(this.code, super.message, {this.details = const {}});

  final String code;
  final Map<String, dynamic> details;
}

final class ServerFailure extends Failure {
  const ServerFailure(
      [super.message = 'Un problème est survenu de notre côté']);
}
