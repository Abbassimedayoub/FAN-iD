import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';

import '../controllers/auth_controller.dart';
import '../mappers/login_failure_mapper.dart';
import '../views/login_view.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({
    this.noticeText,
    this.onDeviceLocked,
    this.onRegister,
    super.key,
  });

  final String? noticeText;
  final ValueChanged<BusinessFailure>? onDeviceLocked;
  final VoidCallback? onRegister;

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    ref.read(authControllerProvider.notifier).login(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    ref.listen(authControllerProvider, (previous, next) {
      final error = next.error;
      if (error is BusinessFailure && error.code == 'DEVICE_LOCKED') {
        widget.onDeviceLocked?.call(error);
      }
    });

    return LoginView(
      emailController: _emailController,
      passwordController: _passwordController,
      isLoading: authState.isLoading,
      errorText:
          authState.hasError ? mapLoginFailureMessage(authState.error) : null,
      noticeText: widget.noticeText,
      onSubmit: _submit,
      onRegister: widget.onRegister,
    );
  }
}
