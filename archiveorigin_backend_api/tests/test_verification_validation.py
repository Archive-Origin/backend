import pytest

from app.verification import validate_manifest_summary, ensure_payload_safe
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
