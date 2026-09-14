# API reference

FAN iD exposes a versioned REST API for identity, event management, purchasing and admission control.

## Base URLs

| Environment | Base URL |
| --- | --- |
| Local API | `http://localhost:8000` |
| Local gateway | `http://localhost:8080` |
| Hosted demonstration | `https://fanid-api-9sep.onrender.com` |

Business routes use `/api/v1` and generally have no trailing slash. The local OpenAPI schema is available at `/api/v1/schema/`; Swagger UI is at `/swagger-ui/`. These documentation endpoints are disabled in the hosted configuration.

## Main endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/health` | Database and Redis health |
| GET | `/api/v1/health/ready` | Detailed dependency readiness |
| POST | `/api/v1/auth/register` | Register a fan account |
| POST | `/api/v1/auth/login` | Authenticate |
| POST | `/api/v1/auth/token/refresh` | Refresh a session |
| GET / PATCH | `/api/v1/auth/me` | Read or update the authenticated profile |
| GET | `/api/v1/catalog/events` | Browse the fan catalog |
| GET / POST | `/api/v1/events` | List or create managed events |
| PUT | `/api/v1/events/{event_id}/image` | Save an event image |
| POST | `/api/v1/events/{event_id}/cancel` | Cancel an event |
| POST | `/api/v1/orders/reservations` | Create a reservation |
| GET | `/api/v1/orders/{order_id}` | Read order status |
| POST | `/api/v1/orders/{order_id}/payment-intent` | Prepare payment |
| POST | `/api/v1/payments/stripe/webhook` | Receive signed Stripe events |
| GET | `/api/v1/tickets` | List the current user's tickets |
| GET | `/api/v1/tickets/{ticket_id}/qr` | Retrieve a dynamic ticket QR payload |
| POST | `/api/v1/access/scans` | Validate an admission scan |
| GET | `/api/v1/access/events/{event_id}/live-dashboard` | Read event admission activity |

This is a navigation reference, not an exhaustive schema. Request fields and endpoint permissions are defined by the serializers, views and generated OpenAPI schema.

## Authentication and request headers

Protected endpoints require the appropriate authenticated user and role. Object-level permissions still apply after login. The Stripe webhook uses signature verification rather than a user session.

| Header | Use |
| --- | --- |
| `Authorization: Bearer <access_token>` | Bearer authentication |
| `If-Match: "7"` | Expected resource version for a versioned write; use the current ETag, not a fixed value |
| `Idempotency-Key` | Request deduplication where required |
| `X-Correlation-ID` | Request identification across logs |
| `Stripe-Signature` | Stripe webhook verification |

Browser cookie flows must also respect CSRF and trusted-origin requirements. Never expose tokens, passwords or payment client secrets in shared examples.

## Responses and errors

Successful reads usually return 200; creation may return 201. Business failures include a machine-readable error code and a message. Application errors can include `details`, `correlation_id` and `trace_id`; some provider-facing responses use a different shape.

| Status | Interpretation |
| --- | --- |
| 400 | Invalid request or rejected webhook signature |
| 401 | Authentication required or no longer valid |
| 403 | Insufficient permission or an explicit security restriction |
| 404 | Resource unavailable or route not exposed |
| 409 | Business conflict, including an expired reservation |
| 428 | Required write precondition missing or unusable |
| 500 | Unhandled backend failure; investigate using the correlation ID |

## Payment contract

A created PaymentIntent is not a completed purchase. The backend processes signed `payment_intent.succeeded` events before confirming the order and issuing tickets. It processes `refund.updated` for refund outcomes.

Clients should read the resulting order and ticket state. An accepted cancellation request or webhook response does not establish that all refunds are complete.

## Related documents

- [Architecture](../adr/README.md)
- [Workflow diagrams](../diagrams/README.md)
- [Project README](../../README.md)
