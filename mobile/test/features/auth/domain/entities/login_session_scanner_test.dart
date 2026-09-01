import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  AuthUser scanner({
    bool mustChangePassword = false,
    String? phone,
  }) {
    return AuthUser(
      id: 'scanner-user',
      email: 'scanner@example.test',
      firstName: 'Amine',
      lastName: 'Scanner',
      role: 'SCANNER',
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
    'scanner can require a password change',
    () {
      final user = scanner(
        mustChangePassword: true,
      );

      expect(
        user.mustChangePassword,
        isTrue,
      );
    },
  );

  test(
    'scanner phone is stored on auth user',
    () {
      final user = scanner(
        phone: '+216 20 000 000',
      );

      expect(
        user.phone,
        '+216 20 000 000',
      );
    },
  );

  test(
    'scanner phone defaults to null',
    () {
      final user = scanner();

      expect(
        user.phone,
        isNull,
      );
    },
  );
}
