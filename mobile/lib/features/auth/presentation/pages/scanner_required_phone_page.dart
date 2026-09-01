import 'package:flutter/material.dart';
import 'package:intl_phone_field/intl_phone_field.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

import '../controllers/auth_controller.dart';

class ScannerRequiredPhonePage extends ConsumerStatefulWidget {
  const ScannerRequiredPhonePage({
    super.key,
  });

  @override
  ConsumerState<ScannerRequiredPhonePage> createState() =>
      _ScannerRequiredPhonePageState();
}

class _ScannerRequiredPhonePageState
    extends ConsumerState<ScannerRequiredPhonePage> {
  final _formKey = GlobalKey<FormState>();
  final _phone = TextEditingController();

  bool _submitting = false;
  bool _phoneIsValid = false;
  String? _error;
  String _completePhone = '';

  @override
  void dispose() {
    _phone.dispose();
    super.dispose();
  }

  bool get _canSubmit =>
      !_submitting && _phoneIsValid && _completePhone.trim().isNotEmpty;

  Future<void> _submit() async {
    final formValid = _formKey.currentState?.validate() ?? false;

    if (!_canSubmit || !formValid) {
      setState(() {
        _error = 'Saisissez un numéro valide pour le pays sélectionné.';
      });
      return;
    }

    final value = _completePhone.trim();

    if (value.isEmpty) {
      setState(() {
        _error = 'Saisissez un numéro de téléphone valide.';
      });
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      await ref
          .read(
            authControllerProvider.notifier,
          )
          .updateScannerPhone(
            phone: value,
          );

      if (!mounted) {
        return;
      }

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Téléphone enregistré. Votre compte scanner est maintenant prêt.',
          ),
        ),
      );
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error =
            'Impossible d’enregistrer le téléphone. Vérifiez le numéro et réessayez.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  @override
  Widget build(
    BuildContext context,
  ) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: FanColors.background,
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
              horizontal: FanSpacing.screenH,
              vertical: FanSpacing.xxl,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const FanIdLogo(
                  size: 64,
                ),
                const SizedBox(
                  height: FanSpacing.xxl,
                ),
                const Icon(
                  Icons.phone_android_outlined,
                  size: 48,
                  color: FanColors.primary,
                ),
                const SizedBox(
                  height: FanSpacing.lg,
                ),
                Text(
                  'Ajoutez votre téléphone',
                  style: FanType.h1,
                ),
                const SizedBox(
                  height: FanSpacing.sm,
                ),
                Text(
                  'Votre mot de passe personnel est configuré. '
                  'Pour finaliser votre compte scanner FANID, '
                  'vous devez maintenant renseigner votre numéro '
                  'de téléphone.',
                  style: FanType.body.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
                const SizedBox(
                  height: FanSpacing.lg,
                ),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(
                    FanSpacing.lg,
                  ),
                  decoration: BoxDecoration(
                    color: FanColors.surface,
                    borderRadius: BorderRadius.circular(
                      16,
                    ),
                  ),
                  child: Text(
                    'Ce numéro sera visible sur votre compte '
                    'scanner ainsi que dans l’espace de votre '
                    'organisateur.',
                    style: FanType.body,
                  ),
                ),
                const SizedBox(
                  height: FanSpacing.xl,
                ),
                Form(
                  key: _formKey,
                  child: IntlPhoneField(
                    controller: _phone,
                    initialCountryCode: 'FR',
                    languageCode: 'fr',
                    keyboardType: TextInputType.phone,
                    autovalidateMode: AutovalidateMode.onUserInteraction,
                    disableLengthCheck: false,
                    decoration: const InputDecoration(
                      labelText: 'Numéro de téléphone',
                      hintText: '6 12 34 56 78',
                      border: OutlineInputBorder(),
                    ),
                    validator: (phone) {
                      if (phone == null ||
                          phone.number.trim().isEmpty ||
                          !phone.isValidNumber()) {
                        return 'Numéro invalide pour le pays sélectionné.';
                      }

                      return null;
                    },
                    onChanged: (phone) {
                      final valid = phone.isValidNumber();

                      setState(() {
                        _completePhone = phone.completeNumber;
                        _phoneIsValid = valid;
                        _error = null;
                      });
                    },
                    onCountryChanged: (_) {
                      _phone.clear();

                      setState(() {
                        _completePhone = '';
                        _phoneIsValid = false;
                        _error = null;
                      });
                    },
                  ),
                ),
                const SizedBox(
                  height: FanSpacing.sm,
                ),
                Text(
                  'Exemple France : +33 612345678. '
                  'Le numéro doit être valide pour le pays sélectionné.',
                  style: FanType.caption.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(
                    height: FanSpacing.md,
                  ),
                  Semantics(
                    liveRegion: true,
                    child: Text(
                      _error!,
                      style: FanType.body.copyWith(
                        color: FanColors.danger,
                      ),
                    ),
                  ),
                ],
                const SizedBox(
                  height: FanSpacing.xl,
                ),
                FanIdPrimaryButton(
                  label: _submitting ? 'Validation…' : 'Valider mon téléphone',
                  loading: _submitting,
                  onPressed: _canSubmit ? _submit : null,
                ),
                const SizedBox(
                  height: FanSpacing.lg,
                ),
                Text(
                  'Le scanner QR reste inaccessible tant que cette étape n’est pas terminée.',
                  style: FanType.caption.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
