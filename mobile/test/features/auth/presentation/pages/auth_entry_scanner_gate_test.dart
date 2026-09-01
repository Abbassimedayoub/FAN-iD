import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/auth_entry_page.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  AuthUser user({
    required String role,
    bool mustChangePassword = false,
    String? phone,
  }) {
    return AuthUser(
      id: 'user-1',
      email: 'user@example.test',
      firstName: 'Amine',
      lastName: 'Scanner',
      role: role,
      createdAt: DateTime.utc(
        2026,
        8,
        29,
      ),
      mustChangePassword: mustChangePassword,
      phone: phone,
    );
  }

  test(
    'scanner without phone is blocked after password change',
    () {
      expect(
        scannerRequiresPhone(
          user(
            role: 'SCANNER',
          ),
        ),
        isTrue,
      );
    },
  );

  test(
    'scanner with phone can leave phone gate',
    () {
      expect(
        scannerRequiresPhone(
          user(
            role: 'SCANNER',
            phone: '+216 20 000 000',
          ),
        ),
        isFalse,
      );
    },
  );

  test(
    'temporary password gate has priority',
    () {
      expect(
        scannerRequiresPhone(
          user(
            role: 'SCANNER',
            mustChangePassword: true,
          ),
        ),
        isFalse,
      );
    },
  );

  test(
    'fan is never sent to scanner phone gate',
    () {
      expect(
        scannerRequiresPhone(
          user(
            role: 'FAN',
          ),
        ),
        isFalse,
      );
    },
  );
}
