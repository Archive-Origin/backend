from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable, Set

import httpx
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from models import AttestationCertificate

logger = logging.getLogger("archiveorigin.crl")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_crl(data: bytes) -> x509.CertificateRevocationList:
    try:
        return x509.load_der_x509_crl(data, default_backend())
    except ValueError:
        return x509.load_pem_x509_crl(data, default_backend())


def _fetch(url: str) -> bytes:
    resp = httpx.get(url, timeout=settings.crl_request_timeout_seconds)
    resp.raise_for_status()
    return resp.content


def _collect_urls(db: Session) -> Set[str]:
    urls: Set[str] = set(settings.crl_sources or [])
    stmt = select(AttestationCertificate.crl_urls).where(AttestationCertificate.crl_urls.is_not(None))
    for (raw,) in db.execute(stmt):
        try:
            entries = json.loads(raw)
            for entry in entries:
                urls.add(entry)
        except (json.JSONDecodeError, TypeError):
            continue
    return {url for url in urls if url}


def refresh_crls(db: Session) -> dict:
    urls = _collect_urls(db)
    if not urls:
        logger.info("No CRL URLs configured")
        return {"checked": 0, "revoked": 0}

    revoked_serials: Set[str] = set()
    checked = 0
    for url in urls:
        try:
            content = _fetch(url)
            crl = _load_crl(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch CRL %s: %s", url, exc)
            continue
        checked += 1
        for revoked in crl:
            revoked_serials.add(format(revoked.serial_number, "X"))

    result = {"checked": checked, "revoked": 0}
    if not revoked_serials:
        return result

    stmt = select(AttestationCertificate).where(AttestationCertificate.serial_number.in_(revoked_serials))
    now = _now()
    count = 0
    for cert in db.scalars(stmt):
        if cert.revoked:
            cert.last_checked_at = now
            continue
        cert.revoked = True
        cert.revoked_at = now
        cert.revocation_reason = "crl_revoked"
        cert.last_checked_at = now
        count += 1
    db.commit()
    result["revoked"] = count
    logger.info("CRL refresh complete checked=%s newly_revoked=%s", checked, count)
    return result
