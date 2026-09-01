import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/auth_entry_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/fan_home_page.dart';
import 'package:fanid_mobile/features/events/presentation/pages/organizer_home_page.dart';

AuthUser userWithRole(String role) {
  return AuthUser(
    id: 'user-$role',
    email: '$role@example.test',
    firstName: 'Test',
    lastName: 'FANID',
    role: role,
    createdAt: DateTime.utc(2026, 1, 1),
  );
}

void main() {
  test(
    'un ORGANIZER ouvre la home organisateur',
    () {
      expect(
        authenticatedNonScannerHome(
          userWithRole('ORGANIZER'),
        ),
        isA<OrganizerHomePage>(),
      );
    },
  );

  test(
    'un FAN conserve la home fan',
    () {
      expect(
        authenticatedNonScannerHome(
          userWithRole('FAN'),
        ),
        isA<FanHomePage>(),
      );
    },
  );
}
