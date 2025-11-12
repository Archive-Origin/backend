# Verification & Attestation Flow

This backend never accepts raw media. Clients extract manifests locally, generate hashes, and call the verification APIs with minimal cryptographic artifacts.

## Primary Endpoints

### `POST /api/v1/verify`
Payload:
```jsonc
{
  "content_hash": "hex64",
  "manifest_hash": "hex64",
  "attestation_cert_hash": "hex64",
  "signature_hash": "hex64",
  "manifest_summary": { "title": "optional" },
  "client_nonce": "optional",
  "client_version": "ArchiveOriginVerifier/1.2.3"
}
```
Behavior:
1. Rejects media/base64 blobs.
2. Enforces replay cache and rate-limits (anonymous vs API-key).
3. Looks up ledger entry by content/manifest/signature hash.
4. Validates attestation certificate status (revocation aware).
5. Validates signature hash and timestamps.
6. Returns either:
```json
{
  "status": "verified",
  "content_hash": "…",
  "ledger_entry": { "entry_id": "…", "timestamp": "…", "proof_level": "rooted", "merkle_root": "…" },
  "verification_details": { "signature_valid": true, "attestation_valid": true, "ledger_match": true, "notes": ["Ledger entry matched."] },
  "proof_level": "rooted",
  "expires_at": "2025-11-09T12:39:56Z"
}
```
or
```json
{
  "status": "not_verified",
  "reason": "ledger_not_found",
  "details": { "ledger_found": false, "signature_valid": false, "attestation_valid": false }
}
```

### `POST /api/v1/ledger/lookup`
*Whitelisted clients only.* Returns the ledger entry + merkle proof fragments for internal tooling.

### `GET /api/v1/certs/{cert_hash}`
Returns attestation certificate metadata and PEM (only for authenticated callers). A revoked certificate returns `revoked=true` and includes `revocation_reason`.

## Device Enrollment (`/device/enroll`)

Device tokens are issued only when DeviceCheck succeeds (when `DEVICECHECK_ENABLED=true`). Required environment variables:

| Variable | Description |
| --- | --- |
| `DEVICECHECK_TEAM_ID` | Apple Developer Team ID |
| `DEVICECHECK_KEY_ID` | DeviceCheck Key ID |
| `DEVICECHECK_PRIVATE_KEY` or `_PATH` | ES256 signing key |
| `DEVICECHECK_ALLOWED_BUNDLE_IDS` | JSON array of bundle IDs allowed to enroll |

Clients must send `devicecheckToken` (base64) and optionally `bundle_id`.

## Attestation & CRL Management

| Env Var | Purpose |
| --- | --- |
| `ATTESTATION_SEED_DIR` | Directory of PEM/CRT files ingested on startup. |
| `CRL_SOURCES` | JSON array or comma list of CRL URLs to poll. |
| `CRL_AUTO_REFRESH` | `true` to fetch CRLs during API startup. |
| `CRL_REFRESH_INTERVAL_SECONDS` | Recommended interval for scheduled jobs. |
| `CRL_REQUEST_TIMEOUT_SECONDS` | HTTP timeout per CRL fetch. |

`app/attestation.py` ingests certs (hashes, serials, issuers, CRL URLs). `app/crl.py` fetches CRLs, parses DER/PEM, and marks matching certs as revoked; this feeds directly into `/api/v1/verify`.

## Testing

```
pip install -r app/requirements.txt
python -m pytest
```

Included tests cover:
- Payload & manifest summary guards (`tests/test_verification_validation.py`)
- Attestation ingestion & CRL revocation logic (`tests/test_attestation.py`)
- Verification flow success/failure cases (`tests/test_verification_flow.py`)

## Operational Notes

- Run CRL refreshers on a schedule (Celery/cron/K8s CronJob) using `crl.refresh_crls`.
- Seed attestation certs during deploys (`ATTESTATION_SEED_DIR`) and store PEMs securely (optionally encrypt filesystem or move to HSM-backed secrets).
- Ensure TLS 1.3 termination (e.g., Cloudflare tunnel) and keep `tls_required=true` so HTTP requests are rejected before reaching verification logic.
