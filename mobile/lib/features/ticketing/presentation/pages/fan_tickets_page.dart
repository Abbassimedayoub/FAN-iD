import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/errors/failure.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../data/fan_ticket_transfer_remote_data_source.dart';
import '../../domain/fan_ticket.dart';
import '../../domain/fan_ticket_filters.dart';
import 'fan_ticket_qr_page.dart';
import '../providers/fan_tickets_provider.dart';

class FanTicketsPage extends ConsumerStatefulWidget {
  const FanTicketsPage({super.key});

  @override
  ConsumerState<FanTicketsPage> createState() => _FanTicketsPageState();
}

class _FanTicketsPageState extends ConsumerState<FanTicketsPage> {
  FanTicketDateFilter _dateFilter = FanTicketDateFilter.all;
  FanTicketStatusFilter _statusFilter = FanTicketStatusFilter.all;

  @override
  Widget build(BuildContext context) {
    final tickets = ref.watch(fanTicketsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Mes billets'),
      ),
      body: tickets.when(
        loading: () => const Center(
          child: CircularProgressIndicator(),
        ),
        error: (_, __) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const Icon(
                  Icons.error_outline,
                  size: 48,
                ),
                const SizedBox(height: 16),
                const Text(
                  'Impossible de charger vos billets.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: () => ref.invalidate(
                    fanTicketsProvider,
                  ),
                  child: const Text('Réessayer'),
                ),
              ],
            ),
          ),
        ),
        data: (items) {
          final filteredItems = filterAndSortFanTickets(
            items,
            dateFilter: _dateFilter,
            statusFilter: _statusFilter,
          );

          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(fanTicketsProvider);
              await ref.read(fanTicketsProvider.future);
            },
            child: filteredItems.isEmpty
                ? ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(24),
                    children: const <Widget>[
                      SizedBox(height: 96),
                      Icon(
                        Icons.confirmation_number_outlined,
                        size: 64,
                      ),
                      SizedBox(height: 16),
                      Text(
                        'Vous n’avez pas encore de billet.',
                        textAlign: TextAlign.center,
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Vos billets apparaîtront ici après confirmation du paiement.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  )
                : ListView.separated(
                    key: const ValueKey<String>('fan-tickets-list'),
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    itemCount: filteredItems.length + 1,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, index) {
                      if (index == 0) {
                        return Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: <Widget>[
                            ChoiceChip(
                              label: const Text('Tous'),
                              selected: _dateFilter == FanTicketDateFilter.all,
                              onSelected: (_) => setState(
                                () => _dateFilter = FanTicketDateFilter.all,
                              ),
                            ),
                            ChoiceChip(
                              label: const Text('À venir'),
                              selected:
                                  _dateFilter == FanTicketDateFilter.upcoming,
                              onSelected: (_) => setState(
                                () =>
                                    _dateFilter = FanTicketDateFilter.upcoming,
                              ),
                            ),
                            ChoiceChip(
                              label: const Text('Passés'),
                              selected: _dateFilter == FanTicketDateFilter.past,
                              onSelected: (_) => setState(
                                () => _dateFilter = FanTicketDateFilter.past,
                              ),
                            ),
                            ChoiceChip(
                              label: const Text('Valides'),
                              selected:
                                  _statusFilter == FanTicketStatusFilter.valid,
                              onSelected: (_) => setState(
                                () =>
                                    _statusFilter = FanTicketStatusFilter.valid,
                              ),
                            ),
                            ChoiceChip(
                              label: const Text('Utilisés'),
                              selected:
                                  _statusFilter == FanTicketStatusFilter.used,
                              onSelected: (_) => setState(
                                () =>
                                    _statusFilter = FanTicketStatusFilter.used,
                              ),
                            ),
                            ChoiceChip(
                              label: const Text('Annulés'),
                              selected:
                                  _statusFilter == FanTicketStatusFilter.voided,
                              onSelected: (_) => setState(
                                () => _statusFilter =
                                    FanTicketStatusFilter.voided,
                              ),
                            ),
                          ],
                        );
                      }

                      final ticket = filteredItems[index - 1];

                      return _FanTicketCard(
                        ticket: ticket,
                        onTransfer: ticket.canTransfer
                            ? () => _showTransferDialog(
                                  context: context,
                                  ref: ref,
                                  ticket: ticket,
                                )
                            : null,
                        onShowQr: () {
                          Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => FanTicketQrPage(ticket: ticket),
                            ),
                          );
                        },
                      );
                    },
                  ),
          );
        },
      ),
    );
  }

  Future<void> _showTransferDialog({
    required BuildContext context,
    required WidgetRef ref,
    required FanTicket ticket,
  }) async {
    final emailController = TextEditingController();
    final messenger = ScaffoldMessenger.of(context);

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        var submitting = false;
        String? error;

        return StatefulBuilder(
          builder: (dialogContext, setDialogState) {
            Future<void> submit() async {
              final recipientEmail = emailController.text.trim();
              final session = ref.read(authControllerProvider).valueOrNull;

              if (recipientEmail.isEmpty || !recipientEmail.contains('@')) {
                setDialogState(() {
                  error = 'Saisissez l’adresse e-mail FANID du destinataire.';
                });
                return;
              }
              if (session == null || session.access.trim().isEmpty) {
                setDialogState(() {
                  error = 'Votre session a expiré. Reconnectez-vous.';
                });
                return;
              }

              setDialogState(() {
                submitting = true;
                error = null;
              });

              try {
                final dio = ref.read(dioClientProvider).dio;
                await FanTicketTransferRemoteDataSource(dio).transferTicket(
                  ticketId: ticket.id,
                  recipientEmail: recipientEmail,
                  accessToken: session.access,
                );
                ref.invalidate(fanTicketsProvider);

                if (!dialogContext.mounted) {
                  return;
                }
                Navigator.of(dialogContext).pop();
                messenger.showSnackBar(
                  const SnackBar(
                    content: Text('Billet transféré avec succès.'),
                  ),
                );
              } on Failure catch (exception) {
                setDialogState(() {
                  submitting = false;
                  error = exception.message;
                });
              } catch (_) {
                setDialogState(() {
                  submitting = false;
                  error = 'Impossible de transférer ce billet. Réessayez.';
                });
              }
            }

            return AlertDialog(
              title: const Text('Transférer ce billet'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Text(
                    'Le QR actuel sera invalidé. Le destinataire recevra '
                    'un nouveau billet dans son compte FANID.',
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: emailController,
                    enabled: !submitting,
                    keyboardType: TextInputType.emailAddress,
                    autofocus: true,
                    decoration: const InputDecoration(
                      labelText: 'E-mail FANID du destinataire',
                    ),
                  ),
                  if (error != null) ...<Widget>[
                    const SizedBox(height: 10),
                    Text(
                      error!,
                      style: TextStyle(
                        color: Theme.of(dialogContext).colorScheme.error,
                      ),
                    ),
                  ],
                ],
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: submitting
                      ? null
                      : () => Navigator.of(dialogContext).pop(),
                  child: const Text('Annuler'),
                ),
                FilledButton(
                  onPressed: submitting ? null : submit,
                  child: submitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Transférer'),
                ),
              ],
            );
          },
        );
      },
    );
    emailController.dispose();
  }
}

class _FanTicketCard extends StatelessWidget {
  const _FanTicketCard({
    required this.ticket,
    required this.onShowQr,
    required this.onTransfer,
  });

  final FanTicket ticket;
  final VoidCallback onShowQr;
  final VoidCallback? onTransfer;

  @override
  Widget build(BuildContext context) {
    final color = ticket.isValid
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.outline;

    return Card(
      key: ValueKey<String>('fan-ticket-${ticket.id}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              Icons.confirmation_number_outlined,
              color: color,
              size: 34,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    ticket.eventName,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 6),
                  Text(ticket.ticketCategoryName),
                  const SizedBox(height: 6),
                  Text(_formatDate(ticket.effectiveStartsAt)),
                  if (ticket.isPostponed) ...<Widget>[
                    const SizedBox(height: 12),
                    _PostponementNotice(ticket: ticket),
                  ],
                  const SizedBox(height: 10),
                  Chip(
                    label: Text(ticket.statusLabel),
                    visualDensity: VisualDensity.compact,
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: ticket.isValid ? onShowQr : null,
                    icon: const Icon(Icons.qr_code_2_outlined),
                    label: const Text('Afficher le QR dynamique'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton.icon(
                    onPressed: onTransfer,
                    icon: const Icon(Icons.send_outlined),
                    label: const Text('Transférer ce billet'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _formatDate(DateTime value) {
    final date = value.toLocal();

    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year} à '
        '${date.hour.toString().padLeft(2, '0')}:'
        '${date.minute.toString().padLeft(2, '0')}';
  }
}

class _PostponementNotice extends StatelessWidget {
  const _PostponementNotice({required this.ticket});

  final FanTicket ticket;

  @override
  Widget build(BuildContext context) {
    final hasNewDate = ticket.postponedToStartsAt != null;
    final scheme = Theme.of(context).colorScheme;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: scheme.tertiaryContainer,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              Icons.event_repeat_outlined,
              color: scheme.onTertiaryContainer,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: DefaultTextStyle(
                style: Theme.of(context).textTheme.bodySmall!.copyWith(
                      color: scheme.onTertiaryContainer,
                    ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const Text(
                      'Événement reporté',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      hasNewDate
                          ? 'Nouvelle date : ${_formatDate(ticket.postponedToStartsAt!)}. '
                              'Votre billet et son QR restent valides.'
                          : 'Nouvelle date à venir. Votre billet est conservé ; '
                              'les entrées restent fermées jusque-là.',
                    ),
                    if (ticket.postponementReason != null) ...<Widget>[
                      const SizedBox(height: 4),
                      Text('Motif : ${ticket.postponementReason}'),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _formatDate(DateTime value) {
    final date = value.toLocal();

    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year} à '
        '${date.hour.toString().padLeft(2, '0')}:'
        '${date.minute.toString().padLeft(2, '0')}';
  }
}
