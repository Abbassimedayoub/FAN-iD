import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/device_reset_challenge.dart';
import '../controllers/device_reset_controller.dart';
import '../views/device_reset_confirm_view.dart';

class DeviceResetConfirmPage extends ConsumerStatefulWidget {
  const DeviceResetConfirmPage({
    required this.challenge,
    required this.onConfirmed,
    this.onBack,
    super.key,
  });

  final DeviceResetChallenge challenge;
  final VoidCallback onConfirmed;
  final VoidCallback? onBack;

  @override
  ConsumerState<DeviceResetConfirmPage> createState() =>
      _DeviceResetConfirmPageState();
}

class _DeviceResetConfirmPageState
    extends ConsumerState<DeviceResetConfirmPage> {
  final _codeController = TextEditingController();
  bool _confirmationPending = false;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  void _submit() {
    _confirmationPending = true;

    ref.read(deviceResetControllerProvider.notifier).confirm(
          challengeId: widget.challenge.challengeId,
          code: _codeController.text.trim(),
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(deviceResetControllerProvider);

    ref.listen(deviceResetControllerProvider, (previous, next) {
      if (!_confirmationPending) {
        return;
      }

      if (next.hasError) {
        _confirmationPending = false;
        return;
      }

      if (previous?.isLoading == true && next.hasValue && next.value == null) {
        _confirmationPending = false;
        widget.onConfirmed();
      }
    });

    return DeviceResetConfirmView(
      codeController: _codeController,
      expiresInSeconds: widget.challenge.expiresInSeconds,
      isLoading: state.isLoading,
      errorText: state.hasError ? _mapError(state.error) : null,
      onSubmit: _submit,
      onBack: widget.onBack,
    );
  }

  String _mapError(Object? error) {
    if (error is BusinessFailure) {
      if (error.code == 'OTP_INVALID') {
        return 'Code incorrect.';
      }
      if (error.code == 'OTP_MAX_ATTEMPTS') {
        return 'Trop de tentatives. Demandez un nouveau code.';
      }
    }

    if (error is NetworkFailure) {
      return 'Connexion indisponible. Vérifiez votre connexion et réessayez.';
    }

    return 'Impossible de confirmer la réinitialisation. Réessayez.';
  }
}
