import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/fan_ticket.dart';
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
                    return _FanTicketCard(ticket: items[index]);
                  },
                ),
        ),
      ),
    );
  }
}

class _FanTicketCard extends StatelessWidget {
  const _FanTicketCard({required this.ticket});

  final FanTicket ticket;

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
                  Text(_formatDate(ticket.eventStartsAt)),
                  const SizedBox(height: 10),
                  Chip(
                    label: Text(ticket.statusLabel),
                    visualDensity: VisualDensity.compact,
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
