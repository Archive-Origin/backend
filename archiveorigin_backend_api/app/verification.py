from __future__ import annotations

import json
from datetime import timedelta
from threading import Lock
from typing import Any, Dict, Optional

import orjson
from cachetools import TTLCache
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import ClientIdentity
from config import settings
from models import LedgerEntry, AttestationCertificate
from schemas import (
    VerifyRequest,
    VerifySuccessResponse,
    VerifyFailureResponse,
    VerifyFailureDetails,
    LedgerEntrySchema,
    VerificationDetails,
    LedgerLookupResponse,
)
from time_sync import trusted_time

REPLAY_CACHE = TTLCache(maxsize=50_000, ttl=settings.replay_cache_ttl_seconds)
REPLAY_LOCK = Lock()
SUSPICIOUS_KEYS = {"media", "file", "binary", "payload", "image", "video", "audio", "blob"}
MAX_STRING_LENGTH = 512
MAX_NOTES = 4

def _raise_bad_request(message: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

def ensure_payload_safe(payload_dict: Dict[str, Any]) -> None:
    for key, value in payload_dict.items():
        normalized_key = key.lower()
        if normalized_key in SUSPICIOUS_KEYS:
            _raise_bad_request("media_payload_not_allowed")
        if isinstance(value, (bytes, bytearray)):
            _raise_bad_request("binary_payload_not_allowed")
        if isinstance(value, str):
            if "data:image" in value.lower() or "base64," in value.lower():
                _raise_bad_request("media_payload_not_allowed")
            if len(value) > MAX_STRING_LENGTH and normalized_key not in {"manifest_summary"}:
                _raise_bad_request("unexpected_field_size")
        if isinstance(value, dict):
            ensure_payload_safe(value)

def validate_manifest_summary(summary: Optional[Dict[str, Any]], allow_summary: bool):
    if summary is None:
        return
    if not allow_summary:
        _raise_bad_request("manifest_summary_not_allowed")
    forbidden = [key for key in summary.keys() if key not in settings.allowed_manifest_summary_fields]
    if forbidden:
        _raise_bad_request("manifest_summary_contains_disallowed_fields")
    encoded = orjson.dumps(summary)
    if len(encoded) > settings.manifest_summary_max_bytes:
        _raise_bad_request("manifest_summary_too_large")

def enforce_replay_guard(payload: VerifyRequest):
    digest = payload.content_hash
    if payload.client_nonce:
        digest = f"{payload.client_nonce}:{payload.content_hash}"
    with REPLAY_LOCK:
        if digest in REPLAY_CACHE:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="replay_detected")
        REPLAY_CACHE[digest] = True

def _load_merkle_proof(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None

def _entry_to_schema(entry: LedgerEntry) -> LedgerEntrySchema:
    return LedgerEntrySchema(
        entry_id=entry.entry_id,
        timestamp=entry.timestamp_utc,
        attestation_cert_hash=entry.attestation_cert_hash,
        device_signature_hash=entry.device_signature_hash,
        proof_level=entry.proof_level,
        merkle_root=entry.merkle_root,
        merkle_proof=_load_merkle_proof(entry.merkle_proof),
        sourced_from=entry.sourced_from,
    )

def lookup_ledger(db: Session, payload: VerifyRequest) -> Optional[LedgerEntry]:
    stmt = select(LedgerEntry).where(LedgerEntry.content_hash == payload.content_hash)
    entry = db.execute(stmt).scalar_one_or_none()
    if entry:
        return entry
    if payload.manifest_hash:
        stmt = select(LedgerEntry).where(LedgerEntry.manifest_hash == payload.manifest_hash)
        entry = db.execute(stmt).scalar_one_or_none()
        if entry:
            return entry
    if payload.signature_hash:
        stmt = select(LedgerEntry).where(LedgerEntry.device_signature_hash == payload.signature_hash)
        return db.execute(stmt).scalar_one_or_none()
    return None

def _verify_attestation(db: Session, payload: VerifyRequest, entry: LedgerEntry, notes: list[str]) -> bool:
    if payload.attestation_cert_hash != entry.attestation_cert_hash:
        notes.append("attestation hash mismatch")
        return False
    cert = db.get(AttestationCertificate, entry.attestation_cert_hash)
    if cert is None:
        notes.append("certificate_missing")
        return False
    if cert.revoked:
        notes.append("certificate_revoked")
        return False
    return True

def _verify_signature(payload: VerifyRequest, entry: LedgerEntry, notes: list[str]) -> bool:
    if entry.device_signature_hash and payload.signature_hash:
        if entry.device_signature_hash != payload.signature_hash:
            notes.append("signature_hash_mismatch")
            return False
        return True
    if entry.device_signature_hash and not payload.signature_hash:
        notes.append("missing_signature_hash")
        return False
    # If ledger stored no signature hash, treat as unknown but not blocking
    return True

def _verify_manifest(payload: VerifyRequest, entry: LedgerEntry, notes: list[str]) -> bool:
    if payload.manifest_hash and entry.manifest_hash and payload.manifest_hash != entry.manifest_hash:
        notes.append("manifest_hash_mismatch")
        return False
    return True

def _verify_timestamp(entry: LedgerEntry, notes: list[str]) -> bool:
    trusted_now = trusted_time.now()
    # Reject if entry timestamp is in future beyond 2 minutes
    if entry.timestamp_utc and (entry.timestamp_utc - trusted_now).total_seconds() > 120:
        notes.append("timestamp_in_future")
        return False
    return True

def perform_verification(payload: VerifyRequest, identity: ClientIdentity, db: Session):
    ensure_payload_safe(payload.model_dump())
    validate_manifest_summary(payload.manifest_summary, identity.allow_manifest_summary)
    enforce_replay_guard(payload)

    entry = lookup_ledger(db, payload)
    if not entry:
        return VerifyFailureResponse(
            status="not_verified",
            reason="ledger_not_found",
            details=VerifyFailureDetails(
                ledger_found=False,
                signature_valid=False,
                attestation_valid=False,
            ),
        )

    notes: list[str] = []
    ledger_match = entry.content_hash == payload.content_hash
    if not ledger_match:
        notes.append("content_hash_mismatch")

    attestation_ok = _verify_attestation(db, payload, entry, notes)
    signature_ok = _verify_signature(payload, entry, notes)
    manifest_ok = _verify_manifest(payload, entry, notes)
    timestamp_ok = _verify_timestamp(entry, notes)

    if not (ledger_match and attestation_ok and signature_ok and manifest_ok and timestamp_ok):
        reason = "ledger_not_found"
        if not attestation_ok:
            reason = "attestation_revoked"
        elif not signature_ok or not manifest_ok:
            reason = "signature_mismatch"
        elif not timestamp_ok:
            reason = "timestamp_mismatch"
        return VerifyFailureResponse(
            status="not_verified",
            reason=reason,
            details=VerifyFailureDetails(
                ledger_found=True,
                signature_valid=signature_ok and manifest_ok,
                attestation_valid=attestation_ok,
            ),
        )

    expires_at = trusted_time.now() + timedelta(minutes=5)
    details = VerificationDetails(
        signature_valid=True,
        attestation_valid=True,
        ledger_match=True,
        notes=notes[:MAX_NOTES] if notes else ["Ledger entry matched."],
    )
    ledger_schema = _entry_to_schema(entry)
    proof_level = entry.proof_level if entry.proof_level in {"basic", "attested", "rooted"} else "basic"
    return VerifySuccessResponse(
        status="verified",
        content_hash=payload.content_hash,
        ledger_entry=ledger_schema,
        verification_details=details,
        proof_level=proof_level,
        expires_at=expires_at,
    )

def perform_ledger_lookup(payload: VerifyRequest, db: Session) -> LedgerLookupResponse:
    entry = lookup_ledger(db, payload)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ledger_not_found")
    return LedgerLookupResponse(status="ok", ledger_entry=_entry_to_schema(entry))
