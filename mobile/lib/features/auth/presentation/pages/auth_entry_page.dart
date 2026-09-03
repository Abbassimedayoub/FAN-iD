import 'dart:async';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../../domain/entities/login_session.dart';
import '../controllers/auth_controller.dart';
import '../providers/auth_providers.dart';
import '../views/login_view.dart';
import '../views/splash_view.dart';
import 'device_locked_page.dart';
import 'fan_home_page.dart';
import '../../../events/presentation/pages/organizer_home_page.dart';
import 'device_reset_confirm_page.dart';
import 'device_reset_request_page.dart';
import 'forgot_password_confirm_page.dart';
import 'forgot_password_request_page.dart';
import 'change_password_page.dart';
import 'login_page.dart';
import 'register_page.dart';
import 'scanner_required_phone_page.dart';
import '../../../scanner/presentation/pages/scanner_portal_page.dart';

Widget authenticatedNonScannerHome(
  AuthUser user,
) {
  if (user.role.toUpperCase() == 'ORGANIZER') {
    return OrganizerHomePage(user: user);
  }

  return FanHomePage(user: user);
}

bool scannerRequiresPhone(
  AuthUser user,
) {
  if (user.role.toUpperCase() != 'SCANNER' || user.mustChangePassword) {
    return false;
  }

  return (user.phone?.trim().isEmpty ?? true);
}

enum _AuthScreen {
  login,
  register,
  forgotPasswordRequest,
  forgotPasswordConfirm,
  deviceLocked,
  resetRequest,
  resetConfirm,
}

class AuthEntryPage extends ConsumerStatefulWidget {
  const AuthEntryPage({
    this.inactivityTimeout = const Duration(minutes: 15),
    this.now,
    super.key,
  });

  final Duration inactivityTimeout;
  final DateTime Function()? now;

  @override
  ConsumerState<AuthEntryPage> createState() => _AuthEntryPageState();
}

class _AuthEntryPageState extends ConsumerState<AuthEntryPage>
    with WidgetsBindingObserver {
  static const _deviceResetSuccessNotice =
      'Votre appareil a été réinitialisé. Reconnectez-vous.';

  static const _passwordResetSuccessNotice =
      'Votre mot de passe a été réinitialisé. Connectez-vous avec le nouveau.';

  _AuthScreen _screen = _AuthScreen.login;
  BusinessFailure? _deviceLockedFailure;
  DeviceResetChallenge? _challenge;
  String? _loginNotice;
  String? _passwordResetEmail;
  bool _scannerSessionValidationRunning = false;
  bool _inactivityLogoutRunning = false;
  Timer? _scannerSessionValidationTimer;
  Timer? _inactivityTimer;
  DateTime? _backgroundedAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    GestureBinding.instance.pointerRouter.addGlobalRoute(_handlePointerEvent);

    _scannerSessionValidationTimer = Timer.periodic(
      const Duration(seconds: 8),
      (_) {
        unawaited(_revalidateScannerSession());
      },
    );
  }

  @override
  void dispose() {
    _scannerSessionValidationTimer?.cancel();
    _inactivityTimer?.cancel();
    GestureBinding.instance.pointerRouter
        .removeGlobalRoute(_handlePointerEvent);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_handleResume());
      return;
    }

    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      _recordBackgroundStart();
    }
  }

  DateTime _now() => widget.now?.call() ?? DateTime.now();

  void _handlePointerEvent(PointerEvent event) {
    if (event is PointerDownEvent) {
      _resetInactivityTimer();
    }
  }

  void _recordBackgroundStart() {
    final session = ref.read(authControllerProvider).valueOrNull;
    if (session == null) {
      return;
    }

    _backgroundedAt ??= _now();
    _inactivityTimer?.cancel();
  }

  void _resetInactivityTimer() {
    final session = ref.read(authControllerProvider).valueOrNull;

    if (!mounted ||
        session == null ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }

    _inactivityTimer?.cancel();
    _inactivityTimer = Timer(
      widget.inactivityTimeout,
      () => unawaited(_expireForInactivity()),
    );
  }

  Future<void> _handleResume() async {
    final session = ref.read(authControllerProvider).valueOrNull;
    final backgroundedAt = _backgroundedAt;
    _backgroundedAt = null;

    if (session != null &&
        backgroundedAt != null &&
        _now().difference(backgroundedAt) >= widget.inactivityTimeout) {
      await _expireForInactivity();
      return;
    }

    _resetInactivityTimer();
    await _revalidateScannerSession();
  }

  Future<void> _expireForInactivity() async {
    if (!mounted ||
        _inactivityLogoutRunning ||
        ref.read(authControllerProvider).valueOrNull == null) {
      return;
    }

    _inactivityLogoutRunning = true;
    _inactivityTimer?.cancel();

    try {
      await ref.read(authControllerProvider.notifier).signOutLocal();

      if (mounted) {
        _showLoginWithNotice(LoginView.sessionExpiredNotice);
      }
    } finally {
      _inactivityLogoutRunning = false;
    }
  }

  Future<void> _revalidateScannerSession() async {
    if (!mounted ||
        _scannerSessionValidationRunning ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return;
    }

    final authState = ref.read(authControllerProvider);
    final session = authState.valueOrNull;

    if (session == null || session.user.role.toUpperCase() != 'SCANNER') {
      return;
    }

    _scannerSessionValidationRunning = true;

    try {
      final remainsActive = await ref
          .read(authControllerProvider.notifier)
          .revalidateScannerSession();

      if (!remainsActive && mounted) {
        _showLoginWithNotice(LoginView.sessionExpiredNotice);
      }
    } finally {
      _scannerSessionValidationRunning = false;
    }
  }

  void _showLogin() {
    setState(() {
      _screen = _AuthScreen.login;
      _deviceLockedFailure = null;
      _challenge = null;
      _loginNotice = null;
      _passwordResetEmail = null;
    });
  }

  void _showLoginWithNotice(String notice) {
    setState(() {
      _screen = _AuthScreen.login;
      _deviceLockedFailure = null;
      _challenge = null;
      _loginNotice = notice;
    });

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        Navigator.of(context).popUntil((route) => route.isFirst);
      }
    });
  }

  void _showRegister() {
    setState(() {
      _screen = _AuthScreen.register;
      _loginNotice = null;
    });
  }

  void _showForgotPasswordRequest() {
    setState(() {
      _passwordResetEmail = null;
      _loginNotice = null;
      _screen = _AuthScreen.forgotPasswordRequest;
    });
  }

  void _showForgotPasswordConfirm(String email) {
    setState(() {
      _passwordResetEmail = email;
      _loginNotice = null;
      _screen = _AuthScreen.forgotPasswordConfirm;
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

    ref.listen<AsyncValue<LoginSession?>>(authControllerProvider,
        (previous, next) {
      final previousSession = previous?.valueOrNull;
      final nextSession = next.valueOrNull;

      if (previousSession == null && nextSession != null) {
        _backgroundedAt = null;
        _resetInactivityTimer();
      } else if (nextSession == null) {
        _inactivityTimer?.cancel();
        _backgroundedAt = null;
      }
    });

    ref.listen<int>(authExpiryGenerationProvider, (previous, next) {
      if (previous != null && next > previous) {
        _showLoginWithNotice(LoginView.sessionExpiredNotice);
      }
    });

    if (authState.isLoading) {
      return const SplashView();
    }

    if (authState.hasValue && authState.value != null) {
      final session = authState.value!;

      if (session.user.role.toUpperCase() == 'SCANNER') {
        if (session.user.mustChangePassword) {
          return const ChangePasswordPage();
        }

        if (scannerRequiresPhone(
          session.user,
        )) {
          return const ScannerRequiredPhonePage();
        }

        return ScannerPortalPage(user: session.user);
      }

      return authenticatedNonScannerHome(
        session.user,
      );
    }

    switch (_screen) {
      case _AuthScreen.login:
        return LoginPage(
          noticeText: _loginNotice,
          onForgotPassword: _showForgotPasswordRequest,
          onRegister: _showRegister,
          onDeviceLocked: _showDeviceLocked,
        );

      case _AuthScreen.forgotPasswordRequest:
        return ForgotPasswordRequestPage(
          onRequested: _showForgotPasswordConfirm,
          onBack: _showLogin,
        );

      case _AuthScreen.forgotPasswordConfirm:
        final email = _passwordResetEmail!;

        return ForgotPasswordConfirmPage(
          email: email,
          onCompleted: () => _showLoginWithNotice(_passwordResetSuccessNotice),
          onBack: _showForgotPasswordRequest,
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
