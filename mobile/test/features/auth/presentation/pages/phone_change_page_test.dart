import 'package:fanid_mobile/core/errors/failure.dart';
import 'package:fanid_mobile/features/auth/domain/entities/login_session.dart';
import 'package:fanid_mobile/features/auth/domain/entities/phone_change_challenge.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/phone_change_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

AuthUser userWithPhone(String? phone) {
  return AuthUser(
    id: 'user-1',
    email: 'fan@example.test',
    firstName: 'Ines',
    lastName: 'Bouzid',
    role: 'FAN',
    createdAt: DateTime.utc(
      2026,
      9,
      3,
    ),
    phone: phone,
  );
}

class Launcher extends StatefulWidget {
  const Launcher({
    required this.page,
    required this.onResult,
    super.key,
  });

  final Widget page;
  final ValueChanged<bool?> onResult;

  @override
  State<Launcher> createState() => _LauncherState();
}

class _LauncherState extends State<Launcher> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: FilledButton(
          onPressed: () async {
            final result = await Navigator.of(context).push<bool>(
              MaterialPageRoute<bool>(
                builder: (_) => widget.page,
              ),
            );

            widget.onResult(result);
          },
          child: const Text('Ouvrir'),
        ),
      ),
    );
  }
}

Widget app({
  required Widget page,
  required ValueChanged<bool?> onResult,
}) {
  return ProviderScope(
    child: MaterialApp(
      home: Launcher(
        page: page,
        onResult: onResult,
      ),
    ),
  );
}

Finder phoneEditable() {
  return find.descendant(
    of: find.byKey(
      const Key('phone-change-input'),
    ),
    matching: find.byType(
      EditableText,
    ),
  );
}

void main() {
  testWidgets(
    'first phone is saved directly without OTP',
    (tester) async {
      String? registeredPhone;
      bool? result;

      await tester.pumpWidget(
        app(
          onResult: (value) {
            result = value;
          },
          page: PhoneChangePage(
            user: userWithPhone(null),
            registerPhone: ({
              required String phone,
            }) async {
              registeredPhone = phone;
              return userWithPhone(phone);
            },
          ),
        ),
      );

      await tester.tap(
        find.text('Ouvrir'),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        phoneEditable(),
        '699999999',
      );
      await tester.pump();

      await tester.tap(
        find.text('Enregistrer le numéro'),
      );
      await tester.pumpAndSettle();

      expect(
        registeredPhone,
        '+33699999999',
      );
      expect(
        result,
        isTrue,
      );
      expect(
        find.text('Ouvrir'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'existing phone is replaced only after OTP confirmation',
    (tester) async {
      String? requestedPhone;
      String? confirmedPhone;
      String? confirmedCode;
      bool? result;

      await tester.pumpWidget(
        app(
          onResult: (value) {
            result = value;
          },
          page: PhoneChangePage(
            user: userWithPhone(
              '+33601020304',
            ),
            requestPhoneChange: ({
              required String phone,
            }) async {
              requestedPhone = phone;

              return const PhoneChangeChallenge(
                challengeId: 'challenge-phone',
                expiresInSeconds: 300,
              );
            },
            confirmPhoneChange: ({
              required String challengeId,
              required String phone,
              required String code,
            }) async {
              expect(
                challengeId,
                'challenge-phone',
              );

              confirmedPhone = phone;
              confirmedCode = code;

              return userWithPhone(
                phone,
              );
            },
          ),
        ),
      );

      await tester.tap(
        find.text('Ouvrir'),
      );
      await tester.pumpAndSettle();

      expect(
        find.textContaining(
          '+33601020304',
        ),
        findsOneWidget,
      );

      await tester.enterText(
        phoneEditable(),
        '699999999',
      );
      await tester.pump();

      await tester.tap(
        find.text('Recevoir le code'),
      );
      await tester.pumpAndSettle();

      expect(
        requestedPhone,
        '+33699999999',
      );

      expect(
        find.textContaining(
          'ancien numéro +33601020304 reste actif',
        ),
        findsOneWidget,
      );

      await tester.enterText(
        find.byKey(
          const Key('phone-change-otp'),
        ),
        '123456',
      );

      await tester.tap(
        find.text('Confirmer le code'),
      );
      await tester.pumpAndSettle();

      expect(
        confirmedPhone,
        '+33699999999',
      );
      expect(
        confirmedCode,
        '123456',
      );
      expect(
        result,
        isTrue,
      );
    },
  );

  testWidgets(
    'invalid OTP keeps old-phone flow open with safe error',
    (tester) async {
      await tester.pumpWidget(
        app(
          onResult: (_) {},
          page: PhoneChangePage(
            user: userWithPhone(
              '+33601020304',
            ),
            requestPhoneChange: ({
              required String phone,
            }) async {
              return const PhoneChangeChallenge(
                challengeId: 'challenge-phone',
                expiresInSeconds: 300,
              );
            },
            confirmPhoneChange: ({
              required String challengeId,
              required String phone,
              required String code,
            }) async {
              throw const BusinessFailure(
                'OTP_INVALID',
                'invalid',
              );
            },
          ),
        ),
      );

      await tester.tap(
        find.text('Ouvrir'),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        phoneEditable(),
        '699999999',
      );
      await tester.pump();

      await tester.tap(
        find.text('Recevoir le code'),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(
          const Key('phone-change-otp'),
        ),
        '000000',
      );

      await tester.tap(
        find.text('Confirmer le code'),
      );
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Code incorrect ou expiré.',
        ),
        findsOneWidget,
      );

      expect(
        find.textContaining(
          'ancien numéro +33601020304 reste actif',
        ),
        findsOneWidget,
      );
    },
  );
}
