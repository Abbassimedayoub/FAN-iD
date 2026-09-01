import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/auth_controller.dart';
import '../providers/auth_providers.dart';

class ChangePasswordPage extends ConsumerStatefulWidget {
  const ChangePasswordPage({super.key});

  @override
  ConsumerState<ChangePasswordPage> createState() => _ChangePasswordPageState();
}

class _ChangePasswordPageState extends ConsumerState<ChangePasswordPage> {
  final _currentPassword = TextEditingController();
  final _newPassword = TextEditingController();
  final _confirmation = TextEditingController();

  bool _showCurrentPassword = false;
  bool _showNewPassword = false;
  bool _showConfirmation = false;
  bool _submitting = false;

  String? _error;

  @override
  void dispose() {
    _currentPassword.dispose();
    _newPassword.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  bool get _hasMinimumLength => _newPassword.text.length >= 10;

  bool get _isNotOnlyNumeric =>
      _newPassword.text.isNotEmpty &&
      !RegExp(r'^\d+$').hasMatch(_newPassword.text);

  bool get _isDifferentFromCurrent =>
      _newPassword.text.isNotEmpty &&
      _currentPassword.text.isNotEmpty &&
      _newPassword.text != _currentPassword.text;

  bool get _confirmationMatches =>
      _confirmation.text.isNotEmpty && _confirmation.text == _newPassword.text;

  bool get _canSubmit =>
      !_submitting &&
      _currentPassword.text.isNotEmpty &&
      _hasMinimumLength &&
      _isNotOnlyNumeric &&
      _isDifferentFromCurrent &&
      _confirmationMatches;

  void _refresh() {
    setState(() {
      _error = null;
    });
  }

  Future<void> _submit() async {
    if (!_canSubmit) {
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });

    final navigator = Navigator.of(context);
    final messenger = ScaffoldMessenger.of(context);

    try {
      await ref.read(authRuntimeProvider).repository.changePassword(
            currentPassword: _currentPassword.text,
            newPassword: _newPassword.text,
          );

      // Le backend déconnecte toutes les sessions après modification.
      await ref.read(authControllerProvider.notifier).signOutLocal();

      if (!mounted) {
        return;
      }

      navigator.popUntil((route) => route.isFirst);

      messenger.showSnackBar(
        const SnackBar(
          content: Text(
            'Mot de passe modifié. Reconnectez-vous avec votre nouveau mot de passe.',
          ),
        ),
      );
    } catch (_) {
      if (!mounted) {
        return;
      }

      setState(() {
        _error =
            'Impossible de modifier le mot de passe. Vérifiez votre mot de passe actuel et les conditions indiquées.';
      });
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  Widget _passwordField({
    required String label,
    required TextEditingController controller,
    required bool visible,
    required VoidCallback onToggle,
    required String showTooltip,
    required String hideTooltip,
    TextInputAction? textInputAction,
  }) {
    return TextField(
      controller: controller,
      obscureText: !visible,
      autocorrect: false,
      enableSuggestions: false,
      maxLength: 128,
      textInputAction: textInputAction,
      onChanged: (_) => _refresh(),
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        counterText: '',
        suffixIcon: IconButton(
          tooltip: visible ? hideTooltip : showTooltip,
          onPressed: onToggle,
          icon: Icon(
            visible ? Icons.visibility_off_outlined : Icons.visibility_outlined,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Changer le mot de passe')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Text(
                'Vous devez remplacer le mot de passe temporaire avant de pouvoir accéder au scanner FANID.',
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Sécurité du compte',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Choisissez un nouveau mot de passe sécurisé.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 28),
            _passwordField(
              label: 'Mot de passe actuel',
              controller: _currentPassword,
              visible: _showCurrentPassword,
              showTooltip: 'Afficher le mot de passe actuel',
              hideTooltip: 'Masquer le mot de passe actuel',
              textInputAction: TextInputAction.next,
              onToggle: () {
                setState(() {
                  _showCurrentPassword = !_showCurrentPassword;
                });
              },
            ),
            const SizedBox(height: 18),
            _passwordField(
              label: 'Nouveau mot de passe',
              controller: _newPassword,
              visible: _showNewPassword,
              showTooltip: 'Afficher le nouveau mot de passe',
              hideTooltip: 'Masquer le nouveau mot de passe',
              textInputAction: TextInputAction.next,
              onToggle: () {
                setState(() {
                  _showNewPassword = !_showNewPassword;
                });
              },
            ),
            const SizedBox(height: 16),
            Card(
              elevation: 0,
              color: Theme.of(context).colorScheme.surfaceContainerLowest,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
                side: BorderSide(
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Conditions du mot de passe',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 14),
                    _PasswordRule(
                      valid: _hasMinimumLength,
                      text: 'Au moins 10 caractères',
                    ),
                    _PasswordRule(
                      valid: _isNotOnlyNumeric,
                      text: 'Ne pas être entièrement numérique',
                    ),
                    _PasswordRule(
                      valid: _isDifferentFromCurrent,
                      text: 'Être différent du mot de passe actuel',
                    ),
                    const _ServerPasswordRule(
                      text:
                          'Ne pas être trop similaire à votre nom, prénom ou e-mail',
                    ),
                    const _ServerPasswordRule(
                      text: 'Ne pas être un mot de passe couramment utilisé',
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Les règles marquées avec un bouclier sont vérifiées exactement par le serveur FAN-iD.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 18),
            _passwordField(
              label: 'Confirmer le nouveau mot de passe',
              controller: _confirmation,
              visible: _showConfirmation,
              showTooltip: 'Afficher la confirmation du mot de passe',
              hideTooltip: 'Masquer la confirmation du mot de passe',
              textInputAction: TextInputAction.done,
              onToggle: () {
                setState(() {
                  _showConfirmation = !_showConfirmation;
                });
              },
            ),
            if (_confirmation.text.isNotEmpty) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(
                    _confirmationMatches
                        ? Icons.check_circle
                        : Icons.radio_button_unchecked,
                    color: _confirmationMatches
                        ? Colors.green.shade700
                        : Colors.orange.shade700,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _confirmationMatches
                          ? 'Les deux mots de passe correspondent.'
                          : 'Les deux mots de passe ne correspondent pas encore.',
                      style: TextStyle(
                        color: _confirmationMatches
                            ? Colors.green.shade700
                            : Colors.orange.shade700,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.red.shade200),
                ),
                child: Text(
                  _error!,
                  style: TextStyle(color: Colors.red.shade800),
                ),
              ),
            ],
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _canSubmit ? _submit : null,
              icon: _submitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.lock_reset),
              label: Text(
                _submitting ? 'Modification...' : 'Modifier le mot de passe',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PasswordRule extends StatelessWidget {
  const _PasswordRule({required this.valid, required this.text});

  final bool valid;
  final String text;

  @override
  Widget build(BuildContext context) {
    final color =
        valid ? Colors.green.shade700 : Theme.of(context).colorScheme.outline;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            valid ? Icons.check_circle : Icons.radio_button_unchecked,
            size: 20,
            color: color,
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: color,
                fontWeight: valid ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ServerPasswordRule extends StatelessWidget {
  const _ServerPasswordRule({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.shield_outlined,
            size: 20,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(width: 9),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}
