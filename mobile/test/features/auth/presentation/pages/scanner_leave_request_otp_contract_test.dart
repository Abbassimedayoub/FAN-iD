import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test(
    'suppression scanner utilise challenge puis confirmation OTP',
    () async {
      final datasource = await File(
        'lib/features/auth/data/datasources/'
        'auth_remote_data_source.dart',
      ).readAsString();

      final controller = await File(
        'lib/features/auth/presentation/controllers/'
        'auth_controller.dart',
      ).readAsString();

      final page = await File(
        'lib/features/auth/presentation/pages/'
        'scanner_leave_request_page.dart',
      ).readAsString();

      expect(
        datasource,
        contains(
          '/api/v1/organizers/scanner-leave/security-code',
        ),
      );

      expect(
        datasource,
        contains(
          '/api/v1/organizers/scanner-leave/request',
        ),
      );

      expect(
        datasource,
        contains("'challenge_id': challengeId"),
      );

      expect(
        datasource,
        contains("'code': code.trim()"),
      );

      expect(
        controller,
        contains('requestScannerLeaveCode()'),
      );

      expect(
        controller,
        contains('confirmScannerLeave('),
      );

      expect(page, contains('Recevoir le code'));
      expect(page, contains('Code de vérification'));
      expect(page, contains('Confirmer le code'));
      expect(page, contains('Demande déjà envoyée'));

      expect(
        page,
        contains(
          'en attente de validation de ',
        ),
      );
    },
  );
}
