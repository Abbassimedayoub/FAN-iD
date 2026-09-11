import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:fanid_mobile/features/ticketing/data/fan_tickets_remote_data_source.dart';

void main() {
  test('fetches tickets with the bearer access token', () async {
    final dio = Dio(BaseOptions(baseUrl: 'http://127.0.0.1:8000'));
    String? authorization;

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          authorization = options.headers['Authorization']?.toString();
          handler.resolve(
            Response<Map<String, dynamic>>(
              requestOptions: options,
              statusCode: 200,
              data: <String, dynamic>{
                'results': <Map<String, dynamic>>[
                  <String, dynamic>{
                    'id': 'ticket-1',
                    'status': 'VALID',
                    'event_id': 'event-1',
                    'event_name': 'Finale',
                    'event_starts_at': '2026-10-01T20:00:00Z',
                    'ticket_category_name': 'Standard',
                    'created_at': '2026-09-11T10:00:00Z',
                  },
                ],
              },
            ),
          );
        },
      ),
    );

    final source = FanTicketsRemoteDataSource(dio);
    final tickets = await source.fetchTickets(accessToken: 'test-access-token');

    expect(authorization, 'Bearer test-access-token');
    expect(tickets, hasLength(1));
    expect(tickets.single.id, 'ticket-1');
    expect(tickets.single.eventName, 'Finale');
  });
}
