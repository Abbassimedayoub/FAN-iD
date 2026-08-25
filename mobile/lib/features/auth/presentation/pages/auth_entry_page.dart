import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../controllers/auth_controller.dart';
import '../providers/auth_providers.dart';
import '../views/login_view.dart';
import '../views/splash_view.dart';
import 'device_locked_page.dart';
import 'device_reset_confirm_page.dart';
import 'device_reset_request_page.dart';
import 'login_page.dart';
import 'register_page.dart';

enum _AuthScreen {
  login,
  register,
  deviceLocked,
  resetRequest,
  resetConfirm,
}

class AuthEntryPage extends ConsumerStatefulWidget {
  const AuthEntryPage({super.key});

  @override
  ConsumerState<AuthEntryPage> createState() => _AuthEntryPageState();
}

class _AuthEntryPageState extends ConsumerState<AuthEntryPage> {
  static const _deviceResetSuccessNotice =
      'Votre appareil a été réinitialisé. Reconnectez-vous.';

  _AuthScreen _screen = _AuthScreen.login;
  BusinessFailure? _deviceLockedFailure;
  DeviceResetChallenge? _challenge;
  String? _loginNotice;

  void _showLogin() {
    setState(() {
      _screen = _AuthScreen.login;
      _deviceLockedFailure = null;
      _challenge = null;
      _loginNotice = null;
    });
  }

  void _showLoginWithNotice(String notice) {
    setState(() {
      _screen = _AuthScreen.login;
      _deviceLockedFailure = null;
      _challenge = null;
      _loginNotice = notice;
    });
  }

  void _showRegister() {
    setState(() {
      _screen = _AuthScreen.register;
      _loginNotice = null;
    });
  }

  void _showDeviceLocked(BusinessFailure failure) {
    setState(() {
      _deviceLockedFailure = failure;
      _challenge = null;
      _loginNotice = null;
      _screen = _AuthScreen.deviceLocked;
    });
  }

  void _showResetRequest() {
    setState(() {
      _challenge = null;
      _screen = _AuthScreen.resetRequest;
    });
  }

  void _showResetConfirm(DeviceResetChallenge challenge) {
    setState(() {
      _challenge = challenge;
      _screen = _AuthScreen.resetConfirm;
    });
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    ref.listen<int>(authExpiryGenerationProvider, (previous, next) {
      if (previous != null && next > previous) {
        _showLoginWithNotice(LoginView.sessionExpiredNotice);
      }
    });

    if (authState.isLoading) {
      return const SplashView();
    }

    if (authState.hasValue && authState.value != null) {
      return const SplashView(
        statusLabel: 'Session active.',
      );
    }

    switch (_screen) {
      case _AuthScreen.login:
        return LoginPage(
          noticeText: _loginNotice,
          onRegister: _showRegister,
          onDeviceLocked: _showDeviceLocked,
        );

      case _AuthScreen.register:
        return RegisterPage(
          onBackToLogin: _showLogin,
          onRegistered: _showLogin,
        );

      case _AuthScreen.deviceLocked:
        final failure = _deviceLockedFailure!;

        return DeviceLockedPage(
          failure: failure,
          onReset: _showResetRequest,
          onBackToLogin: _showLogin,
        );

      case _AuthScreen.resetRequest:
        return DeviceResetRequestPage(
          onChallenge: _showResetConfirm,
          onBack: () {
            setState(() {
              _screen = _AuthScreen.deviceLocked;
            });
          },
        );

      case _AuthScreen.resetConfirm:
        final challenge = _challenge!;

        return DeviceResetConfirmPage(
          challenge: challenge,
          onConfirmed: () => _showLoginWithNotice(_deviceResetSuccessNotice),
          onBack: _showResetRequest,
        );
    }
  }
}
