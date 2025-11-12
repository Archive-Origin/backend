import base64
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime
import re

SHA256_PREFIXED = re.compile(r'^sha256:[0-9a-fA-F]{64}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')

class EnrollRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    device_id: str
    public_key: str
    platform: Optional[str] = "iOS"
    app_version: Optional[str] = None
    bundle_id: Optional[str] = None
    current_token: Optional[str] = None
    force: bool = False
    devicecheck_token: Optional[str] = Field(default=None, alias="devicecheckToken")

    @field_validator("devicecheck_token")
    @classmethod
    def validate_devicecheck_token(cls, value):
        if value is None:
            return value
        try:
            base64.b64decode(value, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("devicecheck_token must be base64-encoded") from exc
        return value

class EnrollResponse(BaseModel):
    token: str
    expires_at: datetime
    issued_at: datetime

class Geo(BaseModel):
    lat: float
    lon: float
    accuracy_m: float

class LockProofRequest(BaseModel):
    asset_hash: str
    capture_time_utc: str
    device_id: str
    device_pubkey: str
    geo: Optional[Geo] = None
    signature: str

    @field_validator('asset_hash')
    @classmethod
    def check_asset_hash(cls, v):
        if not SHA256_PREFIXED.match(v):
            raise ValueError('asset_hash must be "sha256:<64 hex>"')
        return v

    @field_validator('capture_time_utc')
    @classmethod
    def check_iso8601(cls, v):
        # Allow trailing 'Z'
        try:
            if v.endswith('Z'):
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            else:
                datetime.fromisoformat(v)
        except Exception:
            raise ValueError('capture_time_utc must be ISO8601 (e.g., 2025-11-03T01:01:45Z)')
        return v

class LockProofResponse(BaseModel):
    status: Literal["LOCKED"]
    record_id: str
    shortcode: str
    verify_url: str
    merkle: dict

class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_hash: str = Field(..., description="SHA-256 hash (hex lowercase)")
    manifest_hash: Optional[str] = Field(None, description="SHA-256 hash of manifest")
    attestation_cert_hash: str = Field(..., description="SHA-256 hash of attestation certificate (DER)")
    signature_hash: Optional[str] = Field(None, description="SHA-256 hash of device signature")
    manifest_summary: Optional[Dict[str, Any]] = Field(default=None, description="Optional summary <=4KB")
    client_nonce: Optional[str] = Field(default=None, max_length=128)
    client_version: Optional[str] = Field(default=None, max_length=64)

    @field_validator("content_hash", "manifest_hash", "attestation_cert_hash", "signature_hash")
    @classmethod
    def _check_hex(cls, value, info):
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError(f"{info.field_name} must be a lowercase hex string")
        if not HEX64.match(value):
            raise ValueError(f"{info.field_name} must be 64 lowercase hex characters")
        return value

    @field_validator("client_nonce")
    @classmethod
    def _strip_nonce(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        return value

class LedgerLookupRequest(VerifyRequest):
    pass

class LedgerEntrySchema(BaseModel):
    entry_id: str
    timestamp: datetime
    attestation_cert_hash: str
    device_signature_hash: Optional[str]
    proof_level: str
    merkle_root: Optional[str]
    merkle_proof: Optional[Dict[str, Any]]
    sourced_from: Optional[str]

class VerificationDetails(BaseModel):
    signature_valid: bool
    attestation_valid: bool
    ledger_match: bool
    notes: list[str] = Field(default_factory=list)

class VerifySuccessResponse(BaseModel):
    status: Literal["verified"]
    content_hash: str
    ledger_entry: LedgerEntrySchema
    verification_details: VerificationDetails
    proof_level: Literal["basic", "attested", "rooted"]
    expires_at: datetime

class VerifyFailureDetails(BaseModel):
    ledger_found: bool
    signature_valid: bool
    attestation_valid: bool

class VerifyFailureResponse(BaseModel):
    status: Literal["not_verified"]
    reason: Literal["ledger_not_found", "signature_mismatch", "attestation_revoked", "timestamp_mismatch"]
    details: VerifyFailureDetails

class LedgerLookupResponse(BaseModel):
    status: Literal["ok"]
    ledger_entry: LedgerEntrySchema

class CertificateResponse(BaseModel):
    cert_hash: str
    revoked: bool
    revocation_reason: Optional[str]
    metadata: Optional[Dict[str, Any]]
    pem: Optional[str]
