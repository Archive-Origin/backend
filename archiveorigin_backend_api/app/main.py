from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from typing import Optional, Union
from datetime import datetime, timezone, timedelta
import orjson
import logging
import uuid

from config import settings
from db import get_db, engine
from models import Base, DeviceToken, CaptureRecord, AttestationCertificate
from schemas import (
    EnrollRequest,
    EnrollResponse,
    LockProofRequest,
    LockProofResponse,
    VerifyRequest,
    VerifySuccessResponse,
    VerifyFailureResponse,
    LedgerLookupRequest,
    LedgerLookupResponse,
    CertificateResponse,
)
from security import (
    new_token_urlsafe, now_utc, calc_expiry, is_expired, near_expiry,
    validate_pubkey_format, validate_signature
)
from utils import random_shortcode
from auth import authenticate_request
from rate_limit import global_rate_limiter
from verification import perform_verification, perform_ledger_lookup
from time_sync import trusted_time
from devicecheck import get_devicecheck_client, DeviceCheckError

logger = logging.getLogger("archiveorigin.api")
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(title="Archive Origin Proof API", default_response_class=JSONResponse)

allow_origins = settings.cors_allow_origins or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure tables exist (idempotent)
with engine.begin() as conn:
    Base.metadata.create_all(bind=conn)
    # run raw migrations too (idempotent)
    try:
        conn.exec_driver_sql(open("/app/migrations/init.sql", "r").read())
    except Exception as e:
        logger.info("Migrations already applied or failed non-fatally: %s", e)

def _require_tls(request: Request):
    if not settings.tls_required:
        return
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.headers.get("X-Forwarded-Proto")
    scheme = forwarded_proto or request.url.scheme
    if scheme and scheme.lower() == "https":
        return
    raise HTTPException(status_code=400, detail="tls_required")

def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID") or str(uuid.uuid4())

def _apply_response_headers(resp: JSONResponse, request_id: str):
    resp.headers["Cache-Control"] = "private, max-age=30"
    resp.headers["X-Request-ID"] = request_id

def _rate_limit(request: Request, identity):
    client_ip = request.client.host if request.client else "unknown"
    key = identity.api_key or f"ip:{client_ip}"
    if not global_rate_limiter.hit(key, identity.rate_limit):
        raise HTTPException(status_code=429, detail="rate_limited")

def _enforce_devicecheck(payload: EnrollRequest):
    if not settings.devicecheck_enabled:
        return
    if not payload.devicecheck_token:
        raise HTTPException(status_code=400, detail="devicecheck_token_required")
    if settings.devicecheck_allowed_bundle_ids:
        if not payload.bundle_id:
            raise HTTPException(status_code=400, detail="bundle_id_required")
        if payload.bundle_id not in settings.devicecheck_allowed_bundle_ids:
            raise HTTPException(status_code=403, detail="bundle_id_not_allowed")
    client = get_devicecheck_client()
    try:
        client.validate(
            device_token=payload.devicecheck_token,
            device_id=payload.device_id,
            bundle_id=payload.bundle_id,
        )
    except DeviceCheckError as exc:
        logger.warning(
            "DeviceCheck validation failed for device_id=%s reason=%s",
            payload.device_id,
            exc.reason,
        )
        raise HTTPException(status_code=403, detail=f"devicecheck_{exc.reason}")

@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_online = True
    except Exception:
        db_online = False
    return {"ok": True, "time_utc": now_utc().isoformat(), "db_online": db_online}

@app.post("/device/enroll", response_model=EnrollResponse)
def enroll_device(payload: EnrollRequest, request: Request, db: Session = Depends(get_db)):
    # Validate public key format early
    if not validate_pubkey_format(payload.public_key):
        raise HTTPException(status_code=400, detail="public_key must be 'ed25519:<base64>'")
    _enforce_devicecheck(payload)

    existing = db.get(DeviceToken, payload.device_id)

    if existing and not payload.force:
        # Enforce token on update unless within renewal buffer
        if not payload.current_token or payload.current_token != existing.token:
            raise HTTPException(status_code=403, detail="current_token required and must match existing token")
        if existing.force_renewal_required is False and not near_expiry(existing.expires_at, settings.device_token_renewal_buffer):
            # Not near expiry; reuse existing
            return EnrollResponse(token=existing.token, expires_at=existing.expires_at, issued_at=existing.issued_at)

    # Issue new token
    token = new_token_urlsafe(64)
    issued_at = now_utc()
    expires_at = issued_at + timedelta(seconds=settings.device_token_ttl_seconds)

    if not existing:
        existing = DeviceToken(
            device_id=payload.device_id,
            token=token,
            public_key=payload.public_key,
            platform=payload.platform,
            app_version=payload.app_version,
            issued_at=issued_at,
            expires_at=expires_at,
            force_renewal_required=False
        )
        db.add(existing)
    else:
        existing.token = token
        existing.public_key = payload.public_key
        existing.platform = payload.platform
        existing.app_version = payload.app_version
        existing.issued_at = issued_at
        existing.expires_at = expires_at
        existing.force_renewal_required = False

    db.commit()
    return EnrollResponse(token=token, issued_at=issued_at, expires_at=expires_at)

def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)

@app.post("/lock-proof", response_model=LockProofResponse)
def lock_proof(
    payload: LockProofRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
    x_device_pubkey: Optional[str] = Header(None, alias="X-Device-PublicKey"),
    request: Request = None
):
    # Header validations
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split("Bearer ", 1)[1]
    if not x_device_id or not x_device_pubkey:
        raise HTTPException(status_code=400, detail="Missing X-Device-ID or X-Device-PublicKey headers")

    # Cross-check payload vs headers
    if payload.device_id != x_device_id or payload.device_pubkey != x_device_pubkey:
        raise HTTPException(status_code=400, detail="device_id/public_key mismatch between headers and body")

    # Validate token & device
    dev: DeviceToken | None = db.get(DeviceToken, x_device_id)
    if dev is None or dev.token != token:
        logger.warning("Auth failure: bad token for device_id=%s ip=%s", x_device_id, request.client.host if request else "unknown")
        raise HTTPException(status_code=403, detail="Invalid token or device")
    if dev.public_key != x_device_pubkey:
        logger.warning("Auth failure: pubkey mismatch device_id=%s ip=%s", x_device_id, request.client.host if request else "unknown")
        raise HTTPException(status_code=403, detail="Public key mismatch")
    if is_expired(dev.expires_at):
        raise HTTPException(status_code=401, detail="Token expired")

    # Optional signature verification
    if settings.verify_signatures:
        msg = (payload.asset_hash + "|" + payload.capture_time_utc).encode("utf-8")
        if not validate_signature(x_device_pubkey, msg, payload.signature):
            raise HTTPException(status_code=400, detail="Invalid signature")

    # Validate capture_time_utc and compute fields
    try:
        capture_dt = _parse_iso(payload.capture_time_utc)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid capture_time_utc")

    record_id = str(uuid.uuid4())
    shortcode = random_shortcode(6)
    verify_url = settings.verify_base_url.rstrip("/") + "/v/" + record_id

    rec = CaptureRecord(
        record_id=record_id,
        shortcode=shortcode,
        verify_url=verify_url,
        asset_hash=payload.asset_hash,
        capture_time_utc=capture_dt,
        device_id=payload.device_id,
        device_pubkey=payload.device_pubkey,
        geo_lat=str(payload.geo.lat) if payload.geo else None,
        geo_lon=str(payload.geo.lon) if payload.geo else None,
        geo_accuracy_m=str(payload.geo.accuracy_m) if payload.geo else None,
        signature=payload.signature,
        created_at_utc=datetime.now(timezone.utc),
        merkle_batch_id=None,
        merkle_root_hash=None,
        merkle_sealed_at_utc=None
    )
    db.add(rec)
    db.commit()

    return LockProofResponse(
        status="LOCKED",
        record_id=record_id,
        shortcode=shortcode,
        verify_url=verify_url,
        merkle={
            "batch_id": None,
            "root_hash": None,
            "sealed_at_utc": None
        }
    )

@app.post(
    "/api/v1/verify",
    response_model=Union[VerifySuccessResponse, VerifyFailureResponse],
)
def verify_artifact(payload: VerifyRequest, request: Request, db: Session = Depends(get_db)):
    _require_tls(request)
    request_id = _request_id(request)
    identity = authenticate_request(request.headers, payload.content_hash)
    _rate_limit(request, identity)
    result = perform_verification(payload, identity, db)
    response = JSONResponse(content=jsonable_encoder(result))
    _apply_response_headers(response, request_id)
    return response

@app.post(
    "/api/v1/ledger/lookup",
    response_model=LedgerLookupResponse,
)
def ledger_lookup(payload: LedgerLookupRequest, request: Request, db: Session = Depends(get_db)):
    _require_tls(request)
    request_id = _request_id(request)
    identity = authenticate_request(request.headers, payload.content_hash)
    if not identity.authenticated:
        raise HTTPException(status_code=401, detail="api_key_required")
    _rate_limit(request, identity)
    result = perform_ledger_lookup(payload, db)
    response = JSONResponse(content=jsonable_encoder(result))
    _apply_response_headers(response, request_id)
    return response

@app.get("/api/v1/certs/{cert_hash}", response_model=CertificateResponse)
def get_certificate(cert_hash: str, request: Request, db: Session = Depends(get_db)):
    _require_tls(request)
    request_id = _request_id(request)
    identity = authenticate_request(request.headers, None)
    _rate_limit(request, identity)
    cert = db.get(AttestationCertificate, cert_hash)
    if not cert:
        raise HTTPException(status_code=404, detail="cert_not_found")
    include_pem = identity.authenticated
    metadata = None
    if cert.metadata_json:
        try:
            metadata = orjson.loads(cert.metadata_json)
        except orjson.JSONDecodeError:
            metadata = None
    response_body = CertificateResponse(
        cert_hash=cert_hash,
        revoked=cert.revoked,
        revocation_reason=cert.revocation_reason,
        metadata=metadata,
        pem=cert.pem if include_pem else None,
    )
    response = JSONResponse(content=jsonable_encoder(response_body))
    _apply_response_headers(response, request_id)
    return response
