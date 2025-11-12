import json
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql://archiveorigin:supersecret@db:5432/origin_proofs"
    verify_base_url: str = "https://verify.archiveorigin.com"
    device_token_ttl_seconds: int = 30 * 24 * 60 * 60  # 30 days
    device_token_renewal_buffer: int = 7 * 24 * 60 * 60  # 7 days
    log_level: str = "INFO"
    verify_signatures: bool = False
    ledger_repo_root: str = Field(default="ledger", alias="LEDGER_REPO_ROOT")
    ledger_dir: Optional[str] = Field(default=None, alias="LEDGER_DIR")
    ledger_batches_subdir: str = "batches"
    ledger_roots_subdir: str = "roots"
    ledger_proofs_subdir: str = "proofs"
    ledger_manifest_filename: str = "manifest.jsonl"  # kept for backward compatibility
    ledger_root_index_filename: str = "ledger_index.json"
    ledger_daily_roots_filename: str = "daily_roots.csv"
    ledger_proof_manifest_filename: str = "proof_manifest.jsonl"
    ledger_git_auto_commit: bool = False
    ledger_git_auto_push: bool = False
    ledger_git_remote: str = "origin"
    ledger_git_branch: str = "main"
    cors_allow_origins: list[str] = Field(default=["*"])
    allow_manifest_summary: bool = False
    manifest_summary_max_bytes: int = 4 * 1024
    verifier_api_keys: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    anonymous_rate_limit_per_minute: int = 60
    authenticated_rate_limit_per_minute: int = 600
    ntp_servers: list[str] = Field(default_factory=lambda: ["time.cloudflare.com", "pool.ntp.org"])
    replay_cache_ttl_seconds: int = 300
    tls_required: bool = True
    allowed_manifest_summary_fields: list[str] = Field(
        default_factory=lambda: ["title", "creator", "capture_time_utc", "description"]
    )
    trusted_client_versions: list[str] = Field(default_factory=list)
    devicecheck_enabled: bool = False
    devicecheck_team_id: Optional[str] = None
    devicecheck_key_id: Optional[str] = None
    devicecheck_private_key: Optional[str] = None
    devicecheck_private_key_path: Optional[str] = None
    devicecheck_environment: Literal["production", "development"] = "production"
    devicecheck_allowed_bundle_ids: list[str] = Field(default_factory=list)

    model_config = SettingsConfigDict(env_prefix='', env_file='.env', case_sensitive=False)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if value is None:
            return ["*"]
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            cleaned = [origin.strip() for origin in value.split(",")]
            return [origin for origin in cleaned if origin]
        return value

    @field_validator("verifier_api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, value):
        if value in (None, "", []):
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, list):
                result: Dict[str, Dict[str, Any]] = {}
                for entry in parsed:
                    if not isinstance(entry, dict):
                        continue
                    key = entry.get("key")
                    secret = entry.get("hmac_secret")
                    if not key or not secret:
                        continue
                    record = {
                        "name": entry.get("name", "unnamed"),
                        "hmac_secret": secret,
                        "rate_limit_per_minute": entry.get("rate_limit_per_minute"),
                        "allow_manifest_summary": entry.get("allow_manifest_summary", False),
                    }
                    result[str(key)] = record
                return result
        return value

    @field_validator("devicecheck_allowed_bundle_ids", mode="before")
    @classmethod
    def _parse_bundle_ids(cls, value):
        if value in (None, "", []):
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _apply_legacy_dir(self):
        if self.ledger_dir:
            self.ledger_repo_root = self.ledger_dir
        if not self.devicecheck_private_key and self.devicecheck_private_key_path:
            path = Path(self.devicecheck_private_key_path)
            if path.is_file():
                self.devicecheck_private_key = path.read_text().strip()
        if self.devicecheck_enabled:
            missing = []
            if not self.devicecheck_team_id:
                missing.append("DEVICECHECK_TEAM_ID")
            if not self.devicecheck_key_id:
                missing.append("DEVICECHECK_KEY_ID")
            if not self.devicecheck_private_key:
                missing.append("DEVICECHECK_PRIVATE_KEY or DEVICECHECK_PRIVATE_KEY_PATH")
            if missing:
                raise ValueError(
                    "DeviceCheck enabled but missing required settings: " + ", ".join(missing)
                )
        return self

settings = Settings()
