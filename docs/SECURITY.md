# Security

FAN iD applies security controls across authentication, business operations and external-service integration.

## Application controls

- Role and resource-level permissions are enforced by the backend.
- Device binding and session revocation protect account access.
- Versioned writes use `ETag` and `If-Match` to reject missing or stale preconditions.
- Selected operations use idempotency protection against duplicate requests.
- Order confirmation and ticket issuance share a database transaction.
- Stripe webhook requests require signature verification.
- Admission validation checks ticket state and prevents duplicate entry.

## Configuration boundaries

Server secrets belong in environment configuration, not in Git or client builds. Django, JWT and QR signing keys must remain separate.

Hosted browser access uses HTTPS, secure cookies and explicit trusted origins. R2 media storage is private. Frontend build variables must not contain database, storage or payment-provider secrets.

## Safe testing

Use disposable accounts, events and tickets. The hosted demonstration uses Stripe test mode, and the current Android APK is debug-signed for sideload testing.

Redact credentials, tokens, payment client secrets and active QR codes before sharing logs or screenshots. Automated checks and successful demonstrations do not constitute an independent security audit.

## Reporting

Send suspected vulnerabilities privately to [Mohamed Ayoub Abbassi](mailto:abbassimohamedayoub@gmail.com). Include the affected feature, reproduction steps and a redacted example. Do not publish working credentials or personal data in an issue.

See the [architecture](adr/README.md) and [API reference](api/README.md) for technical boundaries.
