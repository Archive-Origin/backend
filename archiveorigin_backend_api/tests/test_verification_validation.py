import pytest

from app.verification import validate_manifest_summary, ensure_payload_safe
from app.schemas import EnrollRequest
from config import settings

def test_manifest_summary_disallowed_when_globally_disabled():
    with pytest.raises(Exception):
        validate_manifest_summary({"title": "example"}, allow_summary=False)

def test_manifest_summary_size_limit():
    data = {"title": "x" * (settings.manifest_summary_max_bytes)}
    with pytest.raises(Exception):
        validate_manifest_summary(data, allow_summary=True)

def test_payload_rejects_media_inline():
    with pytest.raises(Exception):
        ensure_payload_safe({"media": "data:image/png;base64,AAAA"})

def test_enroll_request_rejects_invalid_devicecheck_token():
    with pytest.raises(Exception):
        EnrollRequest(
            device_id="dev1",
            public_key="ed25519:AAA",
            devicecheck_token="not-base64!!",
        )

def test_enroll_request_accepts_valid_devicecheck_token():
    req = EnrollRequest(
        device_id="dev1",
        public_key="ed25519:AAA",
        devicecheck_token="QUJDRA==",
    )
    assert req.devicecheck_token == "QUJDRA=="
