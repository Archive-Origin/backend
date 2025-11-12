# Archive Origin Proof API (FastAPI)

This stack exposes two core endpoints for device enrollment and capture proof locking, backed by PostgreSQL and packaged for Docker Compose.

## Endpoints

- `POST /device/enroll` - enroll or renew a device token
- `POST /lock-proof` - store an immutable capture proof (requires headers + bearer token)
- `GET /health` - health & DB check
- `POST /api/v1/verify` / `POST /api/v1/ledger/lookup` / `GET /api/v1/certs/{hash}` - privacy-preserving verification APIs

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
curl -s http://localhost:8001/health
```

## Environment

- `DATABASE_URL` - e.g. `postgresql://archiveorigin:supersecret@db:5432/origin_proofs`
- `VERIFY_BASE_URL` - e.g. `https://verify.archiveorigin.com`
- `DEVICE_TOKEN_TTL_SECONDS` - default 30 days
- `DEVICE_TOKEN_RENEWAL_BUFFER` - default 7 days
- `VERIFY_SIGNATURES` - set to `true` to enforce ed25519 message verification
- `LEDGER_REPO_ROOT` - base path for the ledger repo (default `ledger/`)
- `LEDGER_BATCHES_SUBDIR` - subdirectory for batch JSON files (default `batches`)
- `LEDGER_ROOTS_SUBDIR` - subdirectory for root indexes (default `roots`)
- `LEDGER_PROOFS_SUBDIR` - subdirectory for proof manifests (default `proofs`)
- `LEDGER_ROOT_INDEX_FILENAME` - file name for the root index (default `ledger_index.json`)
- `LEDGER_DAILY_ROOTS_FILENAME` - file name for the CSV root log (default `daily_roots.csv`)
- `LEDGER_PROOF_MANIFEST_FILENAME` - JSONL manifest of proofs (default `proof_manifest.jsonl`)
- `LEDGER_GIT_AUTO_COMMIT` - set to `true` to auto-commit ledger updates
- `LEDGER_GIT_AUTO_PUSH` - set to `true` to auto-push after committing (implies auto-commit)
- `LEDGER_GIT_REMOTE` / `LEDGER_GIT_BRANCH` - Git target for automatic pushes
- `DEVICECHECK_*` - Apple DeviceCheck configuration (team/key/private key/bundle allow list)
- `ATTESTATION_SEED_DIR` - optional path of PEM/CRT files ingested into the attestation store
- `CRL_SOURCES`, `CRL_AUTO_REFRESH`, `CRL_REFRESH_INTERVAL_SECONDS` - attestation revocation controls

## Schema

Tables are created at container start and migrations run from `app/migrations/init.sql`.

## Merkle Ledger Sealing

Pending capture proofs without a sealed Merkle batch can be processed with:

```bash
docker compose exec api python -m ledger
```

This will:

1. Collect unsealed `capture_records`, compute the Merkle root, and update their `merkle_*` columns.
2. Write a batch file to `${LEDGER_REPO_ROOT}/${LEDGER_BATCHES_SUBDIR}` and update the root/proof manifests.
3. Optionally create/push a Git commit when `LEDGER_GIT_AUTO_COMMIT` / `LEDGER_GIT_AUTO_PUSH` are enabled (or when `--commit` / `--push` flags are provided).

See CLI options:

```bash
docker compose exec api python -m ledger --help
```

## Notes

- Tokens are 64+ byte URL-safe strings.
- `verify_url` resolves to `VERIFY_BASE_URL/v/{record_id}`; wire this to your Verify portal.
- For rate-limiting, prefer Cloudflare rules in front of the tunnel.
- Detailed verification & attestation docs live in `docs/verification_flow.md`.
