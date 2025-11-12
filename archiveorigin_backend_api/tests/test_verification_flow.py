from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import ClientIdentity
from app.models import Base, LedgerEntry, AttestationCertificate
from app.schemas import VerifyRequest
from app.verification import perform_verification

CONTENT_HASH = "a" * 64
MANIFEST_HASH = "b" * 64
CERT_HASH = "c" * 64
SIGNATURE_HASH = "d" * 64


def _session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)


def _identity():
    return ClientIdentity(api_key=None, name="anon", authenticated=False, rate_limit=10, allow_manifest_summary=False)


def _verify_request(nonce: str = "nonce-123"):
    return VerifyRequest(
        content_hash=CONTENT_HASH,
        manifest_hash=MANIFEST_HASH,
        attestation_cert_hash=CERT_HASH,
        signature_hash=SIGNATURE_HASH,
        client_nonce=nonce,
    )


def _insert_records(session):
    now = datetime.now(timezone.utc)
    cert = AttestationCertificate(
        cert_hash=CERT_HASH,
        pem=None,
        metadata_json=None,
        revoked=False,
        created_at_utc=now,
        serial_number="1234ABC",
        issuer="CN=ArchiveOrigin Test",
        crl_urls=None,
        last_checked_at=None,
    )
    entry = LedgerEntry(
        entry_id="entry-1",
        content_hash=CONTENT_HASH,
        manifest_hash=MANIFEST_HASH,
        device_signature_hash=SIGNATURE_HASH,
        attestation_cert_hash=CERT_HASH,
        timestamp_utc=now,
        proof_level="rooted",
        merkle_root="merkleRoot",
        merkle_proof=None,
        entry_hash="e" * 64,
        created_at_utc=now,
        sourced_from="test",
    )
    session.add(cert)
    session.add(entry)
    session.commit()


def test_perform_verification_success():
    Session = _session_factory()
    with Session() as session:
        _insert_records(session)
        result = perform_verification(_verify_request("nonce-success"), _identity(), session)
        assert result.status == "verified"
        assert result.verification_details.signature_valid is True
        assert result.proof_level == "rooted"


def test_perform_verification_ledger_miss():
    Session = _session_factory()
    with Session() as session:
        result = perform_verification(_verify_request("nonce-miss"), _identity(), session)
        assert result.status == "not_verified"
        assert result.reason == "ledger_not_found"
