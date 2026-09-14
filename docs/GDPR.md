# Personal data

FAN iD is an individual school project that processes account and ticketing data. This document describes the technical data scope; it is not a legal compliance certification or a complete privacy notice.

## Data categories

| Area | Examples |
| --- | --- |
| Account | Email, name, date of birth, phone and terms acceptance |
| Authentication | Password hashes, sessions and device identifiers |
| Ticketing | Reservations, orders, tickets and transfers |
| Payments | Provider references, amounts and payment or refund status |
| Admission | Ticket scans and event admission records |
| Diagnostics | Request metadata and correlation identifiers |

Payment details are entered through Stripe's payment interface. Payment credentials and client secrets must not be copied into public documentation.

## Storage and services

PostgreSQL holds business records. Redis-compatible infrastructure supports cache, locks and background processing. The hosted environment also uses Render, Cloudflare Pages, Cloudflare R2, Stripe and SMTP delivery.

Local and hosted environments are separate. Use demonstration data when possible and remove identifying information from shared screenshots.

## Retention and requests

Infrastructure cleanup settings do not define a complete personal-data retention policy. Account, transaction and admission records require an explicit retention review before wider use.

Requests concerning personal data can be sent to [Mohamed Ayoub Abbassi](mailto:abbassimohamedayoub@gmail.com). Do not send passwords, access tokens or full payment details by email.

See the [security notes](SECURITY.md) for handling precautions.
