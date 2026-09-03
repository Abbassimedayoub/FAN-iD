import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl_phone_field/intl_phone_field.dart';

import 'package:fanid_mobile/design_system/design_system.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/login_session.dart';
import '../../domain/entities/phone_change_challenge.dart';
import '../controllers/auth_controller.dart';

typedef RegisterPhoneCallback = Future<AuthUser> Function({
  required String phone,
});

typedef RequestPhoneChangeCallback = Future<PhoneChangeChallenge> Function({
  required String phone,
});

typedef ConfirmPhoneChangeCallback = Future<AuthUser> Function({
  required String challengeId,
  required String phone,
  required String code,
});

class PhoneChangePage extends ConsumerStatefulWidget {
  const PhoneChangePage({
    required this.user,
    this.registerPhone,
    this.requestPhoneChange,
    this.confirmPhoneChange,
    super.key,
  });

  final AuthUser user;
  final RegisterPhoneCallback? registerPhone;
  final RequestPhoneChangeCallback? requestPhoneChange;
  final ConfirmPhoneChangeCallback? confirmPhoneChange;

  @override
  ConsumerState<PhoneChangePage> createState() => _PhoneChangePageState();
}

class _PhoneChangePageState extends ConsumerState<PhoneChangePage> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController();

  bool _submitting = false;
  bool _phoneIsValid = false;
  String _completePhone = '';
  String? _error;

  String get _currentPhone => (widget.user.phone ?? '').trim();

  bool get _hasCurrentPhone => _currentPhone.isNotEmpty;

  bool get _canSubmit =>
      !_submitting && _phoneIsValid && _completePhone.trim().isNotEmpty;

  @override
  void dispose() {
    _phoneController.dispose();
    super.dispose();
  }

  Future<AuthUser> _registerPhone(String phone) {
    final injected = widget.registerPhone;

    if (injected != null) {
      return injected(
        phone: phone,
      );
    }

    return ref.read(authControllerProvider.notifier).registerFirstPhone(
          phone: phone,
        );
  }

  Future<PhoneChangeChallenge> _requestPhoneChange(String phone) {
    final injected = widget.requestPhoneChange;

    if (injected != null) {
      return injected(
        phone: phone,
      );
    }

    return ref.read(authControllerProvider.notifier).requestPhoneChange(
          phone: phone,
        );
  }

  Future<AuthUser> _confirmPhoneChange({
    required String challengeId,
    required String phone,
    required String code,
  }) {
    final injected = widget.confirmPhoneChange;

    if (injected != null) {
      return injected(
        challengeId: challengeId,
        phone: phone,
        code: code,
      );
    }

    return ref.read(authControllerProvider.notifier).confirmPhoneChange(
          challengeId: challengeId,
          phone: phone,
          code: code,
        );
  }

  String _requestErrorMessage(Object error) {
    if (error is BusinessFailure) {
      switch (error.code) {
        case 'RATE_LIMIT_EXCEEDED':
          return 'Trop de demandes. Réessayez un peu plus tard.';
        case 'PHONE_NOT_REGISTERED':
          return 'Aucun ancien numéro n’est enregistré sur ce compte.';
      }
    }

    if (error is AuthFailure) {
      return 'Votre session a expiré. Reconnectez-vous.';
    }

    if (error is NetworkFailure) {
      return 'Connexion indisponible. Vérifiez votre connexion.';
    }

    return 'Impossible de préparer le changement de numéro. Réessayez.';
  }

  String _otpErrorMessage(Object error) {
    if (error is BusinessFailure) {
      switch (error.code) {
        case 'OTP_INVALID':
          return 'Code incorrect ou expiré.';
        case 'OTP_MAX_ATTEMPTS':
          return 'Trop de tentatives. Demandez un nouveau code.';
        case 'RATE_LIMIT_EXCEEDED':
          return 'Trop de tentatives. Réessayez un peu plus tard.';
      }
    }

    if (error is AuthFailure) {
      return 'Votre session a expiré. Reconnectez-vous.';
    }

    if (error is NetworkFailure) {
      return 'Connexion indisponible. Vérifiez votre connexion.';
    }

    return 'Impossible de confirmer ce code pour le moment.';
  }

  Future<bool> _showOtpDialog({
    required PhoneChangeChallenge challenge,
    required String phone,
  }) async {
    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) {
        return _PhoneChangeOtpDialog(
          challenge: challenge,
          phone: phone,
          currentPhone: _currentPhone,
          onConfirm: (code) async {
            await _confirmPhoneChange(
              challengeId: challenge.challengeId,
              phone: phone,
              code: code,
            );
          },
          mapError: _otpErrorMessage,
        );
      },
    );

    return confirmed == true;
  }

  Future<void> _submit() async {
    final formValid = _formKey.currentState?.validate() ?? false;

    if (!_canSubmit || !formValid) {
      setState(() {
        _error = 'Saisissez un numéro valide pour le pays sélectionné.';
      });
      return;
    }

    final phone = _completePhone.trim();

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      if (!_hasCurrentPhone) {
        await _registerPhone(phone);

        if (!mounted) {
          return;
        }

        Navigator.of(context).pop(true);
        return;
      }

      final challenge = await _requestPhoneChange(
        phone,
      );

      if (!mounted) {
        return;
      }

      // Le chargement de la page couvre uniquement la demande du challenge.
      // Pendant le dialogue OTP, celui-ci gère son propre état de chargement.
      // Cela évite aussi de laisser un indicateur animé derrière le dialogue.
      setState(() {
        _submitting = false;
      });

      final confirmed = await _showOtpDialog(
        challenge: challenge,
        phone: phone,
      );

      if (!mounted) {
        return;
      }

      if (confirmed) {
        Navigator.of(context).pop(true);
      }
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error = _requestErrorMessage(error);
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
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: FanColors.background,
      appBar: AppBar(
        title: Text(
          _hasCurrentPhone ? 'Modifier mon téléphone' : 'Ajouter mon téléphone',
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(
            horizontal: FanSpacing.screenH,
            vertical: FanSpacing.xl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.phone_android_outlined,
                size: 48,
                color: FanColors.primary,
              ),
              const SizedBox(height: FanSpacing.lg),
              Text(
                _hasCurrentPhone
                    ? 'Nouveau numéro de téléphone'
                    : 'Enregistrez votre numéro',
                style: FanType.h1,
              ),
              const SizedBox(height: FanSpacing.sm),
              if (_hasCurrentPhone)
                Text(
                  'Numéro actuel : $_currentPhone',
                  style: FanType.body.copyWith(
                    color: FanColors.textSecondary,
                  ),
                )
              else
                Text(
                  'Après l’enregistrement, vous recevrez un e-mail '
                  'de confirmation.',
                  style: FanType.body.copyWith(
                    color: FanColors.textSecondary,
                  ),
                ),
              if (_hasCurrentPhone) ...[
                const SizedBox(height: FanSpacing.md),
                const NavyNoticeBanner(
                  icon: Icons.verified_user_outlined,
                  onLight: true,
                  message:
                      'Votre numéro actuel ne sera remplacé qu’après validation '
                      'du code reçu par e-mail.',
                ),
              ],
              const SizedBox(height: FanSpacing.xl),
              Form(
                key: _formKey,
                child: IntlPhoneField(
                  key: const Key('phone-change-input'),
                  controller: _phoneController,
                  initialCountryCode: 'FR',
                  languageCode: 'fr',
                  keyboardType: TextInputType.phone,
                  autovalidateMode: AutovalidateMode.onUserInteraction,
                  disableLengthCheck: false,
                  decoration: const InputDecoration(
                    labelText: 'Nouveau numéro',
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
                    setState(() {
                      _completePhone = phone.completeNumber;
                      _phoneIsValid = phone.isValidNumber();
                      _error = null;
                    });
                  },
                  onCountryChanged: (_) {
                    _phoneController.clear();

                    setState(() {
                      _completePhone = '';
                      _phoneIsValid = false;
                      _error = null;
                    });
                  },
                ),
              ),
              const SizedBox(height: FanSpacing.sm),
              Text(
                'Exemple France : +33 612345678.',
                style: FanType.caption.copyWith(
                  color: FanColors.textSecondary,
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: FanSpacing.md),
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
              const SizedBox(height: FanSpacing.xl),
              FanIdPrimaryButton(
                label: _hasCurrentPhone
                    ? 'Recevoir le code'
                    : 'Enregistrer le numéro',
                loading: _submitting,
                onPressed: _canSubmit ? _submit : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PhoneChangeOtpDialog extends StatefulWidget {
  const _PhoneChangeOtpDialog({
    required this.challenge,
    required this.phone,
    required this.currentPhone,
    required this.onConfirm,
    required this.mapError,
  });

  final PhoneChangeChallenge challenge;
  final String phone;
  final String currentPhone;
  final Future<void> Function(String code) onConfirm;
  final String Function(Object error) mapError;

  @override
  State<_PhoneChangeOtpDialog> createState() => _PhoneChangeOtpDialogState();
}

class _PhoneChangeOtpDialogState extends State<_PhoneChangeOtpDialog> {
  final _codeController = TextEditingController();

  bool _loading = false;
  String? _errorText;

  bool get _hasCurrentPhone => widget.currentPhone.trim().isNotEmpty;

  @override
  void dispose() {
    _codeController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final code = _codeController.text.trim();

    if (!RegExp(r'^[0-9]{6}$').hasMatch(code)) {
      setState(() {
        _errorText = 'Saisissez exactement les 6 chiffres du code.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _errorText = null;
    });

    try {
      await widget.onConfirm(
        code,
      );

      if (!mounted) {
        return;
      }

      setState(() {
        _loading = false;
      });

      Navigator.of(context).pop(
        true,
      );
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _loading = false;
        _errorText = widget.mapError(
          error,
        );
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final minutes = (widget.challenge.expiresInSeconds / 60).ceil();

    return AlertDialog(
      scrollable: true,
      title: const Text(
        'Confirmer le nouveau numéro',
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Un code à 6 chiffres vient d’être envoyé à votre '
            'adresse e-mail. Il expire dans $minutes minutes.',
          ),
          const SizedBox(
            height: 12,
          ),
          Text(
            'Nouveau numéro : ${widget.phone}',
            style: const TextStyle(
              fontWeight: FontWeight.w600,
            ),
          ),
          if (_hasCurrentPhone) ...[
            const SizedBox(
              height: 8,
            ),
            Text(
              'Votre ancien numéro ${widget.currentPhone} '
              'reste actif tant que ce code n’est pas validé.',
            ),
          ],
          const SizedBox(
            height: 16,
          ),
          TextField(
            key: const Key(
              'phone-change-otp',
            ),
            controller: _codeController,
            enabled: !_loading,
            autofocus: true,
            keyboardType: TextInputType.number,
            textInputAction: TextInputAction.done,
            maxLength: 6,
            autofillHints: const [
              AutofillHints.oneTimeCode,
            ],
            inputFormatters: [
              FilteringTextInputFormatter.digitsOnly,
              LengthLimitingTextInputFormatter(
                6,
              ),
            ],
            decoration: InputDecoration(
              labelText: 'Code de vérification',
              hintText: '000000',
              errorText: _errorText,
            ),
            onSubmitted: _loading
                ? null
                : (_) {
                    _submit();
                  },
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _loading
              ? null
              : () {
                  Navigator.of(context).pop(
                    false,
                  );
                },
          child: const Text(
            'Annuler',
          ),
        ),
        FilledButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                  ),
                )
              : const Text(
                  'Confirmer le code',
                ),
        ),
      ],
    );
  }
}
