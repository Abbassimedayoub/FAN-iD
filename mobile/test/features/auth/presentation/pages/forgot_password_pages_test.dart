import 'package:fanid_mobile/design_system/design_system.dart';
import 'package:fanid_mobile/features/auth/domain/repositories/password_reset_repository.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/forgot_password_confirm_page.dart';
import 'package:fanid_mobile/features/auth/presentation/pages/forgot_password_request_page.dart';
import 'package:fanid_mobile/features/auth/presentation/providers/auth_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class FakePasswordResetRepository implements PasswordResetRepository {
  String? requestedEmail;
  String? confirmedEmail;
  String? confirmedCode;
  String? confirmedPassword;

  @override
  Future<int> requestPasswordReset({
    required String email,
  }) async {
    requestedEmail = email;
    return 900;
  }

  @override
  Future<void> confirmPasswordReset({
    required String email,
    required String code,
    required String newPassword,
  }) async {
    confirmedEmail = email;
    confirmedCode = code;
    confirmedPassword = newPassword;
  }
}

Widget wrap(
  Widget child,
  PasswordResetRepository repository,
) {
  return ProviderScope(
    overrides: [
      passwordResetRepositoryProvider.overrideWithValue(repository),
    ],
    child: MaterialApp(
      theme: FanTheme.light,
      home: child,
    ),
  );
}

void main() {
  testWidgets(
    'la page email envoie la demande puis ouvre la confirmation',
    (tester) async {
      final repository = FakePasswordResetRepository();
      String? requested;

      await tester.pumpWidget(
        wrap(
          ForgotPasswordRequestPage(
            onRequested: (email) {
              requested = email;
            },
          ),
          repository,
        ),
      );

      await tester.enterText(
        find.byType(TextField),
        ' fan@example.test ',
      );

      await tester.tap(
        find.widgetWithText(
          FanIdPrimaryButton,
          'Recevoir le lien et le code',
        ),
      );

      await tester.pumpAndSettle();

      expect(repository.requestedEmail, 'fan@example.test');
      expect(requested, 'fan@example.test');
    },
  );

  testWidgets(
    'la page confirmation envoie code et nouveau mot de passe',
    (tester) async {
      final repository = FakePasswordResetRepository();
      var completed = 0;

      await tester.pumpWidget(
        wrap(
          ForgotPasswordConfirmPage(
            email: 'fan@example.test',
            onCompleted: () {
              completed++;
            },
          ),
          repository,
        ),
      );

      final fields = find.byType(TextField);

      await tester.enterText(
        fields.at(0),
        '123456',
      );

      await tester.enterText(
        fields.at(1),
        'Grenadine-Tumultueuse-2027',
      );

      await tester.enterText(
        fields.at(2),
        'Grenadine-Tumultueuse-2027',
      );

      final submitButton = find.widgetWithText(
        FanIdPrimaryButton,
        'Enregistrer le nouveau mot de passe',
      );

      await tester.ensureVisible(submitButton);
      await tester.pumpAndSettle();
      await tester.tap(submitButton);
      await tester.pumpAndSettle();

      expect(repository.confirmedEmail, 'fan@example.test');
      expect(repository.confirmedCode, '123456');
      expect(
        repository.confirmedPassword,
        'Grenadine-Tumultueuse-2027',
      );
      expect(completed, 1);
    },
  );

  testWidgets(
    'deux mots de passe différents sont bloqués avant le réseau',
    (tester) async {
      final repository = FakePasswordResetRepository();

      await tester.pumpWidget(
        wrap(
          ForgotPasswordConfirmPage(
            email: 'fan@example.test',
            onCompleted: () {},
          ),
          repository,
        ),
      );

      final fields = find.byType(TextField);

      await tester.enterText(fields.at(0), '123456');
      await tester.enterText(
        fields.at(1),
        'Grenadine-Tumultueuse-2027',
      );
      await tester.enterText(
        fields.at(2),
        'Different-Password-2027',
      );

      final submitButton = find.widgetWithText(
        FanIdPrimaryButton,
        'Enregistrer le nouveau mot de passe',
      );

      await tester.ensureVisible(submitButton);
      await tester.pumpAndSettle();
      await tester.tap(submitButton);
      await tester.pump();

      expect(
        find.text(
          'Les deux mots de passe ne correspondent pas.',
        ),
        findsOneWidget,
      );

      expect(repository.confirmedCode, isNull);
    },
  );

  testWidgets(
    'les deux champs mot de passe utilisent FanIdTextField en mode protégé',
    (tester) async {
      final repository = FakePasswordResetRepository();

      await tester.pumpWidget(
        wrap(
          ForgotPasswordConfirmPage(
            email: 'fan@example.test',
            onCompleted: () {},
          ),
          repository,
        ),
      );

      final passwordFields = tester
          .widgetList<FanIdTextField>(
            find.byType(FanIdTextField),
          )
          .where(
            (field) => field.obscure,
          )
          .toList();

      expect(
        passwordFields,
        hasLength(2),
      );

      final nativePasswordFields = tester
          .widgetList<TextField>(
            find.byType(TextField),
          )
          .where(
            (field) => field.obscureText,
          )
          .toList();

      expect(
        nativePasswordFields,
        hasLength(2),
      );
    },
  );
}
