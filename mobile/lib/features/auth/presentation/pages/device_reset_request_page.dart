import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../controllers/device_reset_controller.dart';
import '../views/device_reset_request_view.dart';

class DeviceResetRequestPage extends ConsumerStatefulWidget {
  const DeviceResetRequestPage({
    required this.onChallenge,
    this.onBack,
    super.key,
  });

  final ValueChanged<DeviceResetChallenge> onChallenge;
  final VoidCallback? onBack;

  @override
  ConsumerState<DeviceResetRequestPage> createState() =>
      _DeviceResetRequestPageState();
}

class _DeviceResetRequestPageState
    extends ConsumerState<DeviceResetRequestPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _submit() {
    ref.read(deviceResetControllerProvider.notifier).request(
          email: _emailController.text.trim(),
          password: _passwordController.text,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(deviceResetControllerProvider);

    ref.listen(deviceResetControllerProvider, (previous, next) {
      final challenge = next.value;
      if (challenge != null) {
        widget.onChallenge(challenge);
      }
    });

    return DeviceResetRequestView(
      emailController: _emailController,
      passwordController: _passwordController,
      isLoading: state.isLoading,
      errorText: state.hasError ? _mapError(state.error) : null,
      onSubmit: _submit,
      onBack: widget.onBack,
    );
  }

  String _mapError(Object? error) {
    if (error is NetworkFailure) {
      return 'Connexion indisponible. Vérifiez votre connexion et réessayez.';
    }
    return 'Impossible d’envoyer le code. Réessayez.';
  }
}
