CREATE TABLE IF NOT EXISTS device_tokens (
  device_id TEXT PRIMARY KEY,
  token TEXT UNIQUE NOT NULL,
  public_key TEXT NOT NULL,
  platform TEXT,
  app_version TEXT,
  issued_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  force_renewal_required BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS capture_records (
  record_id TEXT PRIMARY KEY,
  shortcode TEXT,
  verify_url TEXT,
  asset_hash TEXT,
  capture_time_utc TIMESTAMPTZ,
  device_id TEXT,
  device_pubkey TEXT,
  geo_lat TEXT,
  geo_lon TEXT,
  geo_accuracy_m TEXT,
  signature TEXT,
  created_at_utc TIMESTAMPTZ,
  merkle_batch_id TEXT,
  merkle_root_hash TEXT,
  merkle_sealed_at_utc TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ledger_entries (
  entry_id TEXT PRIMARY KEY,
  content_hash VARCHAR(64) NOT NULL,
  manifest_hash VARCHAR(64),
  device_signature_hash VARCHAR(64),
  attestation_cert_hash VARCHAR(64) NOT NULL,
  timestamp_utc TIMESTAMPTZ NOT NULL,
  proof_level VARCHAR(32) NOT NULL DEFAULT 'basic',
  merkle_root VARCHAR(128),
  merkle_proof TEXT,
  entry_hash VARCHAR(64) NOT NULL,
  created_at_utc TIMESTAMPTZ NOT NULL,
  sourced_from TEXT
);

CREATE INDEX IF NOT EXISTS idx_ledger_content_hash ON ledger_entries (content_hash);
CREATE INDEX IF NOT EXISTS idx_ledger_manifest_hash ON ledger_entries (manifest_hash);
CREATE INDEX IF NOT EXISTS idx_ledger_signature_hash ON ledger_entries (device_signature_hash);
CREATE INDEX IF NOT EXISTS idx_ledger_cert_hash ON ledger_entries (attestation_cert_hash);

CREATE TABLE IF NOT EXISTS attestation_certs (
  cert_hash VARCHAR(64) PRIMARY KEY,
  pem TEXT,
  metadata_json TEXT,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  revoked_at TIMESTAMPTZ,
  revocation_reason TEXT,
  created_at_utc TIMESTAMPTZ NOT NULL
);
