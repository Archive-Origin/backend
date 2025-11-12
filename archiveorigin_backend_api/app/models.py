from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, TIMESTAMP, Boolean

class Base(DeclarativeBase):
    pass

class DeviceToken(Base):
    __tablename__ = "device_tokens"
    device_id: Mapped[str] = mapped_column(Text, primary_key=True)
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    expires_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    force_renewal_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

class CaptureRecord(Base):
    __tablename__ = "capture_records"
    record_id: Mapped[str] = mapped_column(Text, primary_key=True)
    shortcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    verify_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    capture_time_utc: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    device_pubkey: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo_lat: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo_lon: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo_accuracy_m: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    merkle_batch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    merkle_root_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    merkle_sealed_at_utc: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    entry_id: Mapped[str] = mapped_column(Text, primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    device_signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attestation_cert_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    timestamp_utc: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    proof_level: Mapped[str] = mapped_column(String(32), nullable=False, default="basic")
    merkle_root: Mapped[str | None] = mapped_column(String(128), nullable=True)
    merkle_proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at_utc: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    sourced_from: Mapped[str | None] = mapped_column(Text, nullable=True)

class AttestationCertificate(Base):
    __tablename__ = "attestation_certs"
    cert_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revoked_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    issuer: Mapped[str | None] = mapped_column(Text, nullable=True)
    crl_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[str | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
