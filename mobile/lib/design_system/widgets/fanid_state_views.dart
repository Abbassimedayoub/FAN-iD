import 'package:flutter/material.dart';

import '../colors.dart';
import '../spacing.dart';
import '../typography.dart';
import 'fanid_buttons.dart';

/// Vue de chargement.
///
/// Shared primitives for loading, error, empty, and success states so screens
/// do not reimplement their own state UI.
class LoadingView extends StatelessWidget {
  const LoadingView({this.message, this.onDark = false, super.key});

  final String? message;
  final bool onDark;

  @override
  Widget build(BuildContext context) {
    final Color fg = onDark ? Colors.white : FanColors.textSecondary;
    return Semantics(
      liveRegion: true,
      label: message ?? 'Chargement en cours',
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            SizedBox(
              width: 34,
              height: 34,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                valueColor: const AlwaysStoppedAnimation<Color>(FanColors.cyan),
                backgroundColor:
                    onDark ? FanColors.onNavySurface : FanColors.border,
              ),
            ),
            if (message != null) ...<Widget>[
              const SizedBox(height: FanSpacing.lg),
              Text(message!, style: FanType.body.copyWith(color: fg)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Empty-content view.
class EmptyView extends StatelessWidget {
  const EmptyView({
    required this.title,
    this.message,
    this.icon = Icons.inbox_outlined,
    this.actionLabel,
    this.onAction,
    super.key,
  });

  final String title;
  final String? message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(FanSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 44, color: FanColors.textPlaceholder),
            const SizedBox(height: FanSpacing.lg),
            Text(title, style: FanType.h3, textAlign: TextAlign.center),
            if (message != null) ...<Widget>[
              const SizedBox(height: FanSpacing.sm),
              Text(
                message!,
                style: FanType.body.copyWith(color: FanColors.textSecondary),
                textAlign: TextAlign.center,
              ),
            ],
            if (actionLabel != null && onAction != null) ...<Widget>[
              const SizedBox(height: FanSpacing.xl),
              FanIdSecondaryButton(
                label: actionLabel!,
                onPressed: onAction,
                expanded: false,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Error view.
///
/// The error state includes icon, title, and text so it remains understandable without relying on red alone.
class ErrorView extends StatelessWidget {
  const ErrorView({
    required this.title,
    this.message,
    this.retryLabel = 'Réessayer',
    this.onRetry,
    super.key,
  });

  final String title;
  final String? message;
  final String retryLabel;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(FanSpacing.xxl),
        child: Semantics(
          liveRegion: true,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(
                Icons.error_outline,
                size: 44,
                color: FanColors.danger,
              ),
              const SizedBox(height: FanSpacing.lg),
              Text(title, style: FanType.h3, textAlign: TextAlign.center),
              if (message != null) ...<Widget>[
                const SizedBox(height: FanSpacing.sm),
                Text(
                  message!,
                  style: FanType.body.copyWith(color: FanColors.textSecondary),
                  textAlign: TextAlign.center,
                ),
              ],
              if (onRetry != null) ...<Widget>[
                const SizedBox(height: FanSpacing.xl),
                FanIdSecondaryButton(
                  label: retryLabel,
                  onPressed: onRetry,
                  expanded: false,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
