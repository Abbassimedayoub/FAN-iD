import 'package:flutter/material.dart';

import '../../core/errors/failure.dart';

/// Widgets socles (§4.4 Source B) mappant les cinq états d'écran (§4.2
/// Source B) côté Flutter : SkeletonBox (loading), EmptyView, ErrorView
/// (avec Réessayer), LoadingOverlay (refreshing), le succès étant le
/// contenu métier lui-même (hors périmètre Sprint 0).

class SkeletonBox extends StatelessWidget {
  const SkeletonBox(
      {super.key, this.height = 16, this.width = double.infinity});

  final double height;
  final double width;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Chargement en cours',
      child: Container(
        height: height,
        width: width,
        decoration: BoxDecoration(
          color: const Color(
              0x1A0E2A4D), // navy à 10% — cohérent avec le token web
          borderRadius: BorderRadius.circular(12),
        ),
      ),
    );
  }
}

class EmptyView extends StatelessWidget {
  const EmptyView(
      {super.key,
      required this.title,
      this.description,
      this.actionLabel,
      this.onAction});

  final String title;
  final String? description;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          if (description != null) ...[
            const SizedBox(height: 8),
            Text(description!, textAlign: TextAlign.center),
          ],
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 16),
            FanIdButton(label: actionLabel!, onPressed: onAction!),
          ],
        ],
      ),
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.failure, this.onRetry});

  final Failure failure;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(failure.message, textAlign: TextAlign.center),
          if (onRetry != null) ...[
            const SizedBox(height: 16),
            FanIdButton(label: 'Réessayer', onPressed: onRetry!),
          ],
        ],
      ),
    );
  }
}

class LoadingOverlay extends StatelessWidget {
  const LoadingOverlay({super.key, required this.visible, required this.child});

  final bool visible;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,
        if (visible)
          const Positioned(
            top: 8,
            right: 8,
            child: SizedBox(
              height: 20,
              width: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          ),
      ],
    );
  }
}

class FanIdButton extends StatelessWidget {
  const FanIdButton({super.key, required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(minimumSize: const Size(44, 44)),
      child: Text(label),
    );
  }
}

class FanIdTextField extends StatelessWidget {
  const FanIdTextField(
      {super.key,
      required this.label,
      this.controller,
      this.obscureText = false});

  final String label;
  final TextEditingController? controller;
  final bool obscureText;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscureText,
      decoration:
          InputDecoration(labelText: label, border: const OutlineInputBorder()),
    );
  }
}

class FanIdScaffold extends StatelessWidget {
  const FanIdScaffold({super.key, required this.title, required this.body});

  final String title;
  final Widget body;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
        appBar: AppBar(title: Text(title)), body: SafeArea(child: body));
  }
}
