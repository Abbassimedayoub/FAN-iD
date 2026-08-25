import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../controllers/register_controller.dart';
import '../mappers/register_failure_mapper.dart';
import '../views/register_view.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({
    this.onRegistered,
    this.onBackToLogin,
    this.today,
    super.key,
  });

  final VoidCallback? onRegistered;
  final VoidCallback? onBackToLogin;

  /// Injecté uniquement pour rendre le contrôle d'âge déterministe en test.
  final DateTime? today;

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _phone = TextEditingController();

  DateTime? _dateOfBirth;
  bool _termsAccepted = false;
  String? _localError;

  DateTime get _today => widget.today ?? DateTime.now();

  @override
  void dispose() {
    _firstName.dispose();
    _lastName.dispose();
    _email.dispose();
    _password.dispose();
    _phone.dispose();
    super.dispose();
  }

  bool _isAtLeast16(DateTime birthDate) {
    final today = _today;
    final birthday16 = DateTime(
      birthDate.year + 16,
      birthDate.month,
      birthDate.day,
    );

    return !birthday16.isAfter(
      DateTime(today.year, today.month, today.day),
    );
  }

  Future<void> _pickDate() async {
    final today = _today;
    final initialDate =
        _dateOfBirth ?? DateTime(today.year - 16, today.month, today.day);

    final selected = await showDatePicker(
      context: context,
      initialDate: initialDate,
      firstDate: DateTime(1900),
      lastDate: today,
    );

    if (selected != null && mounted) {
      setState(() {
        _dateOfBirth = selected;
        _localError = null;
      });
    }
  }

  void _submit() {
    final birthDate = _dateOfBirth;

    if (birthDate == null) {
      setState(() {
        _localError = 'Sélectionnez votre date de naissance.';
      });
      return;
    }

    if (!_isAtLeast16(birthDate)) {
      setState(() {
        _localError = 'Vous devez avoir au moins 16 ans pour créer un compte.';
      });
      return;
    }

    if (!_termsAccepted) {
      setState(() {
        _localError =
            'Vous devez accepter les conditions générales pour créer un compte.';
      });
      return;
    }

    setState(() => _localError = null);

    final phone = _phone.text.trim();

    ref.read(registerControllerProvider.notifier).register(
          email: _email.text.trim(),
          password: _password.text,
          firstName: _firstName.text.trim(),
          lastName: _lastName.text.trim(),
          dateOfBirth: birthDate,
          termsAccepted: true,
          phone: phone.isEmpty ? null : phone,
        );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(registerControllerProvider);

    ref.listen(registerControllerProvider, (previous, next) {
      if (next.hasValue && next.value != null) {
        widget.onRegistered?.call();
      }
    });

    return RegisterView(
      firstNameController: _firstName,
      lastNameController: _lastName,
      emailController: _email,
      passwordController: _password,
      phoneController: _phone,
      dateOfBirth: _dateOfBirth,
      termsAccepted: _termsAccepted,
      isLoading: state.isLoading,
      errorText: _localError ??
          (state.hasError ? mapRegisterFailureMessage(state.error) : null),
      onPickDate: _pickDate,
      onTermsChanged: (value) {
        setState(() {
          _termsAccepted = value;
          _localError = null;
        });
      },
      onSubmit: _submit,
      onBackToLogin: widget.onBackToLogin,
    );
  }
}
