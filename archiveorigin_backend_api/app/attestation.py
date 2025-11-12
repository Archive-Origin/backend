from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from sqlalchemy.orm import Session

from models import AttestationCertificate

logger = logging.getLogger("archiveorigin.attestation")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_certificate(pem: str) -> x509.Certificate:
    return x509.load_pem_x509_certificate(pem.encode("utf-8"), default_backend())


def extract_crl_urls(cert: x509.Certificate) -> list[str]:
    urls: list[str] = []
    try:
        extension = cert.extensions.get_extension_for_class(x509.CRLDistributionPoints)
    except x509.ExtensionNotFound:
        return urls
    for point in extension.value:
        if point.full_name:
            for name in point.full_name:
                if isinstance(name, x509.UniformResourceIdentifier):
                    urls.append(name.value)
    return urls


def ingest_certificate(pem: str, metadata: Optional[dict], db: Session) -> AttestationCertificate:
    cert = load_certificate(pem)
    der = cert.public_bytes(encoding=serialization.Encoding.DER)
    cert_hash = sha256_hex(der)
    serial_number = format(cert.serial_number, "X")
    issuer = cert.issuer.rfc4514_string()
    crl_urls = extract_crl_urls(cert)

    existing = db.get(AttestationCertificate, cert_hash)
    if existing:
        existing.pem = pem
        existing.metadata_json = json.dumps(metadata) if metadata else existing.metadata_json
        existing.serial_number = serial_number
        existing.issuer = issuer
        if crl_urls:
            existing.crl_urls = json.dumps(crl_urls)
        return existing

    record = AttestationCertificate(
        cert_hash=cert_hash,
        pem=pem,
        metadata_json=json.dumps(metadata) if metadata else None,
        revoked=False,
        created_at_utc=_now(),
        serial_number=serial_number,
        issuer=issuer,
        crl_urls=json.dumps(crl_urls) if crl_urls else None,
    )
    db.add(record)
    return record


def ingest_certificates_from_dir(path_str: str, db: Session) -> list[str]:
    path = Path(path_str)
    if not path.exists():
        logger.warning("attestation seed dir %s does not exist", path)
        return []
    ingested: list[str] = []
    for file in path.glob("**/*"):
        if not file.is_file():
            continue
        if file.suffix.lower() not in {".pem", ".crt", ".cer"}:
            continue
        pem = file.read_text()
        record = ingest_certificate(pem, metadata={"source": str(file)}, db=db)
        ingested.append(record.cert_hash)
    if ingested:
        logger.info("Ingested %s attestation certs from %s", len(ingested), path)
    return ingested
