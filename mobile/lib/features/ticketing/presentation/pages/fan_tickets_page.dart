import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/fan_ticket.dart';
import 'fan_ticket_qr_page.dart';
import '../providers/fan_tickets_provider.dart';

class FanTicketsPage extends ConsumerWidget {
  const FanTicketsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
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
        data: (items) => RefreshIndicator(
          onRefresh: () async {
            ref.invalidate(fanTicketsProvider);
            await ref.read(fanTicketsProvider.future);
          },
          child: items.isEmpty
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
                  itemCount: items.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final ticket = items[index];

                    return _FanTicketCard(
                      ticket: ticket,
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
        ),
      ),
    );
  }
}

class _FanTicketCard extends StatelessWidget {
  const _FanTicketCard({
    required this.ticket,
    required this.onShowQr,
  });

  final FanTicket ticket;
  final VoidCallback onShowQr;

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
