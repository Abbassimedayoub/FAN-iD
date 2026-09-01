import 'package:fanid_mobile/features/auth/domain/entities/scanner_leave_challenge.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('challenge suppression scanner conserve id et expiration', () {
    const challenge = ScannerLeaveChallenge(
      challengeId: '00000000-0000-4000-8000-000000000101',
      expiresInSeconds: 300,
    );

    expect(
      challenge.challengeId,
      '00000000-0000-4000-8000-000000000101',
    );
    expect(challenge.expiresInSeconds, 300);
  });
}
