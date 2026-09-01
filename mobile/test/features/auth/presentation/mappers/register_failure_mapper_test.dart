import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/presentation/mappers/register_failure_mapper.dart';

void main() {
  test('maps registration business failures safely', () {
    expect(
      mapRegisterFailureMessage(
        const BusinessFailure('EMAIL_ALREADY_EXISTS', 'backend text'),
      ),
      'Un compte existe déjà pour cette adresse.',
    );

    expect(
      mapRegisterFailureMessage(
        const BusinessFailure('UNDERAGE', 'backend text'),
      ),
      'Vous devez avoir au moins 16 ans pour créer un compte.',
    );

    expect(
      mapRegisterFailureMessage(
        const BusinessFailure('TERMS_NOT_ACCEPTED', 'backend text'),
      ),
      'Vous devez accepter les conditions générales pour créer un compte.',
    );
  });

  test('maps infrastructure failures', () {
    expect(
      mapRegisterFailureMessage(const NetworkFailure()),
      'Connexion indisponible. Vérifiez votre connexion et réessayez.',
    );

    expect(
      mapRegisterFailureMessage(const PermissionFailure()),
      'Inscription refusée.',
    );

    expect(
      mapRegisterFailureMessage(const NotFoundFailure()),
      'Service d’inscription indisponible.',
    );

    expect(
      mapRegisterFailureMessage(const ServerFailure()),
      'Un problème est survenu. Réessayez plus tard.',
    );
  });

  test('does not expose backend text for unknown failures', () {
    expect(
      mapRegisterFailureMessage(
        const BusinessFailure('OTHER', 'backend text'),
      ),
      genericRegisterErrorMessage,
    );

    expect(
      mapRegisterFailureMessage(Exception('unexpected backend text')),
      genericRegisterErrorMessage,
    );
  });

  test('returns null when there is no error', () {
    expect(mapRegisterFailureMessage(null), isNull);
  });
}
