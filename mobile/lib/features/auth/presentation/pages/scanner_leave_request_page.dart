import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../domain/entities/scanner_leave_challenge.dart';
import '../controllers/auth_controller.dart';
import 'scanner_leave_request_error.dart';

class ScannerLeaveRequestPage extends ConsumerStatefulWidget {
  const ScannerLeaveRequestPage({super.key});

  @override
  ConsumerState<ScannerLeaveRequestPage> createState() =>
      _ScannerLeaveRequestPageState();
}

class _ScannerLeaveRequestPageState
    extends ConsumerState<ScannerLeaveRequestPage> {
  bool _submitting = false;
  bool _sent = false;
  String? _error;

  String _otpErrorMessage(Object error) {
    if (error is BusinessFailure) {
      switch (error.code) {
        case 'OTP_INVALID':
          return 'Code incorrect ou expiré.';
        case 'OTP_MAX_ATTEMPTS':
          return 'Trop de tentatives. Demandez un nouveau code.';
        case 'STALE_RESOURCE':
          return 'La situation du compte a changé. Réessayez.';
      }
    }

    if (error is NetworkFailure) {
      return 'Connexion indisponible. Vérifiez votre connexion.';
    }

    return 'Impossible de confirmer ce code pour le moment.';
  }

  Future<bool> _showOtpDialog(
    ScannerLeaveChallenge challenge,
  ) async {
    final controller = TextEditingController();
    var loading = false;
    String? errorText;

    try {
      final result = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) {
          return StatefulBuilder(
            builder: (context, setDialogState) {
              Future<void> submit() async {
                final code = controller.text.trim();

                if (!RegExp(r'^[0-9]{6}$').hasMatch(code)) {
                  setDialogState(() {
                    errorText = 'Saisissez exactement les 6 chiffres du code.';
                  });
                  return;
                }

                setDialogState(() {
                  loading = true;
                  errorText = null;
                });

                try {
                  await ref
                      .read(authControllerProvider.notifier)
                      .confirmScannerLeave(
                        challengeId: challenge.challengeId,
                        code: code,
                      );

                  if (dialogContext.mounted) {
                    Navigator.of(dialogContext).pop(true);
                  }
                } catch (error) {
                  if (!dialogContext.mounted) {
                    return;
                  }

                  if (isScannerLeaveAlreadyRequested(error)) {
                    Navigator.of(dialogContext).pop(true);
                    return;
                  }

                  setDialogState(() {
                    loading = false;
                    errorText = _otpErrorMessage(error);
                  });
                }
              }

              return AlertDialog(
                title: const Text(
                  'Confirmer ma demande',
                ),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Un code à 6 chiffres vient d’être envoyé '
                      'à votre adresse e-mail. '
                      'Il expire dans '
                      '${challenge.expiresInSeconds ~/ 60} minutes.',
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: controller,
                      enabled: !loading,
                      autofocus: true,
                      keyboardType: TextInputType.number,
                      textInputAction: TextInputAction.done,
                      maxLength: 6,
                      inputFormatters: [
                        FilteringTextInputFormatter.digitsOnly,
                        LengthLimitingTextInputFormatter(6),
                      ],
                      decoration: InputDecoration(
                        labelText: 'Code de vérification',
                        hintText: '000000',
                        errorText: errorText,
                      ),
                      onSubmitted: loading ? null : (_) => submit(),
                    ),
                  ],
                ),
                actions: [
                  TextButton(
                    onPressed: loading
                        ? null
                        : () {
                            Navigator.of(
                              dialogContext,
                            ).pop(false);
                          },
                    child: const Text('Annuler'),
                  ),
                  FilledButton(
                    onPressed: loading ? null : submit,
                    child: loading
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
            },
          );
        },
      );

      return result == true;
    } finally {
      controller.dispose();
    }
  }

  Future<void> _submit() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Demander mon départ ?',
          ),
          content: const Text(
            'Pour confirmer que cette demande vient bien de vous, '
            'un code de sécurité à 6 chiffres sera envoyé à votre '
            'adresse e-mail. La demande ne sera transmise à '
            'l’organisateur qu’après validation du code.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text(
                'Recevoir le code',
              ),
            ),
          ],
        );
      },
    );

    if (confirmed != true || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final challenge = await ref
          .read(authControllerProvider.notifier)
          .requestScannerLeaveCode();

      if (!mounted) {
        return;
      }

      final otpConfirmed = await _showOtpDialog(
        challenge,
      );

      if (!mounted) {
        return;
      }

      if (!otpConfirmed) {
        setState(() {
          _submitting = false;
        });
        return;
      }

      setState(() {
        _sent = true;
        _submitting = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }

      if (isScannerLeaveAlreadyRequested(error)) {
        setState(() {
          _sent = true;
          _submitting = false;
          _error = null;
        });
        return;
      }

      setState(() {
        _submitting = false;
        _error = 'Impossible d’envoyer le code pour le moment. '
            'Vérifiez votre connexion ou réessayez plus tard.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Suppression de mon accès',
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            const SizedBox(height: 16),
            Icon(
              _sent
                  ? Icons.mark_email_read_outlined
                  : Icons.person_remove_outlined,
              size: 72,
            ),
            const SizedBox(height: 24),
            Text(
              _sent
                  ? 'Demande déjà envoyée'
                  : 'Demander la suppression de mon accès scanner',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            if (_sent) ...[
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(18),
                  child: Text(
                    'Votre demande est en attente de validation de '
                    'l’organisateur. Vous recevrez une notification '
                    'ou un e-mail lorsqu’il aura accepté ou refusé '
                    'votre demande.',
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text(
                  'Retour à mon compte',
                ),
              ),
            ] else ...[
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Comment ça fonctionne ?',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      SizedBox(height: 12),
                      Text(
                        '1. Vous recevez un code de sécurité à '
                        '6 chiffres sur votre e-mail.\n\n'
                        '2. Vous saisissez ce code pour confirmer '
                        'votre demande.\n\n'
                        '3. Seulement après validation, la demande '
                        'est transmise à l’organisateur.\n\n'
                        '4. L’organisateur peut ensuite l’accepter '
                        'ou la refuser.\n\n'
                        '5. En cas d’acceptation, votre accès scanner '
                        'et vos sessions sont désactivés.',
                      ),
                    ],
                  ),
                ),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: _submitting ? null : _submit,
                icon: _submitting
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                        ),
                      )
                    : const Icon(
                        Icons.person_remove_outlined,
                      ),
                label: Text(
                  _submitting
                      ? 'Traitement en cours…'
                      : 'Demander la suppression de mon accès',
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Aucune demande n’est créée tant que le code '
                'reçu par e-mail n’a pas été validé.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
