from datetime import datetime, timedelta, timezone

import json
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import NameOID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import attestation, crl
from app.models import Base, AttestationCertificate


def _in_memory_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _generate_cert_and_crl():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ArchiveOriginTest")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=30))
        .add_extension(
            x509.CRLDistributionPoints(
                [
                    x509.DistributionPoint(
                        full_name=[x509.UniformResourceIdentifier("mock://crl")],
                        relative_name=None,
                        reasons=None,
                        crl_issuer=None,
                    )
                ]
            ),
            critical=False,
        )
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    crl_builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer)
        .last_update(datetime.now(timezone.utc) - timedelta(minutes=1))
        .next_update(datetime.now(timezone.utc) + timedelta(days=1))
    )
    crl_entry = x509.RevokedCertificateBuilder().serial_number(cert.serial_number).revocation_date(
        datetime.now(timezone.utc)
    ).build()
    crl_obj = crl_builder.add_revoked_certificate(crl_entry).sign(private_key=key, algorithm=hashes.SHA256())
    crl_bytes = crl_obj.public_bytes(serialization.Encoding.DER)
    return cert.public_bytes(serialization.Encoding.PEM).decode(), crl_bytes


def test_ingest_certificate_extracts_metadata():
    Session = _in_memory_session()
    pem, _ = _generate_cert_and_crl()
    with Session() as session:
        record = attestation.ingest_certificate(pem, metadata={"env": "test"}, db=session)
        session.commit()
        assert record.cert_hash
        assert record.serial_number
        assert record.issuer.startswith("CN")


def test_crl_refresh_marks_revoked(monkeypatch):
    Session = _in_memory_session()
    pem, crl_bytes = _generate_cert_and_crl()
    with Session() as session:
        record = attestation.ingest_certificate(pem, metadata=None, db=session)
        record.crl_urls = json.dumps(["mock://crl"])
        session.commit()
        cert_hash = record.cert_hash

    monkeypatch.setattr(crl, "_collect_urls", lambda db: {"mock://crl"})
    monkeypatch.setattr(crl, "_fetch", lambda url: crl_bytes)

    with Session() as session:
        result = crl.refresh_crls(session)
        assert result["revoked"] == 1
        refreshed = session.get(AttestationCertificate, cert_hash)
        assert refreshed.revoked is True
