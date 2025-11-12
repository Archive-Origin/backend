from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

import ulid
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from db import SessionLocal
from merkle import MerkleComputationError, build_merkle_tree
from models import CaptureRecord


@dataclass
class BatchResult:
    batch_id: str
    root_hash: str
    sealed_at_utc: datetime
    record_count: int
    artifacts: tuple[Path, ...]
    git_commit_sha: Optional[str] = None


def _ledger_root() -> Path:
    root = Path(settings.ledger_repo_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_ledger_files(
    batch_id: str,
    root_hash: str,
    sealed_at: datetime,
    records: Sequence[CaptureRecord],
    tree_levels: Sequence[Sequence[str]],
) -> tuple[Path, ...]:
    ledger_root = _ledger_root()
    batches_dir = _ensure_dir(ledger_root / settings.ledger_batches_subdir)
    roots_dir = _ensure_dir(ledger_root / settings.ledger_roots_subdir)
    proofs_dir = _ensure_dir(ledger_root / settings.ledger_proofs_subdir)

    batch_filename = f"{sealed_at.strftime('%Y-%m-%d')}_{batch_id}.json"
    batch_path = batches_dir / batch_filename

    formatted_levels = [
        [f"sha256:{node}" for node in level] for level in tree_levels
    ]
    batch_payload = {
        "batch_id": batch_id,
        "root_hash": root_hash,
        "sealed_at_utc": sealed_at.isoformat(),
        "record_count": len(records),
        "records": [
            {
                "record_id": rec.record_id,
                "asset_hash": rec.asset_hash,
                "capture_time_utc": rec.capture_time_utc.isoformat() if rec.capture_time_utc else None,
                "device_id": rec.device_id,
            }
            for rec in records
        ],
        "merkle_tree_levels": formatted_levels,
    }
    with batch_path.open("w", encoding="utf-8") as fh:
        json.dump(batch_payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    index_path = roots_dir / settings.ledger_root_index_filename
    index_entries: list[dict] = []
    if index_path.exists():
        try:
            loaded = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                index_entries = loaded
        except json.JSONDecodeError:
            index_entries = []
    index_entries.append(
        {
            "batch_id": batch_id,
            "sealed_at_utc": sealed_at.isoformat(),
            "root_hash": root_hash,
            "record_count": len(records),
            "batch_file": batch_path.relative_to(ledger_root).as_posix(),
        }
    )
    index_entries.sort(key=lambda item: item["sealed_at_utc"])
    with index_path.open("w", encoding="utf-8") as fh:
        json.dump(index_entries, fh, indent=2, sort_keys=True)
        fh.write("\n")

    roots_csv = roots_dir / settings.ledger_daily_roots_filename
    csv_header = "sealed_at_utc,root_hash,batch_id,record_count"
    if not roots_csv.exists():
        roots_csv.write_text(csv_header + "\n", encoding="utf-8")
    csv_line = ",".join(
        [
            sealed_at.isoformat(),
            root_hash,
            batch_id,
            str(len(records)),
        ]
    )
    with roots_csv.open("a", encoding="utf-8") as fh:
        fh.write(csv_line + "\n")

    proof_manifest = proofs_dir / settings.ledger_proof_manifest_filename
    proof_entry = {
        "batch_id": batch_id,
        "root_hash": root_hash,
        "sealed_at_utc": sealed_at.isoformat(),
        "record_count": len(records),
        "records": [
            {
                "record_id": rec.record_id,
                "asset_hash": rec.asset_hash,
            }
            for rec in records
        ],
    }
    with proof_manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(proof_entry, sort_keys=True) + "\n")

    return batch_path, index_path, roots_csv, proof_manifest


def _git_commit(paths: Iterable[Path], message: str) -> Optional[str]:
    try:
        subprocess.run(
            ["git", "add", *[str(path) for path in paths]],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            capture_output=True,
        )
        show = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return show.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("git executable not found; cannot commit ledger batch")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git command failed: {exc.stderr.decode().strip() if exc.stderr else exc}") from exc


def _git_push(remote: str, branch: str) -> None:
    try:
        subprocess.run(
            ["git", "push", remote, branch],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        raise RuntimeError("git executable not found; cannot push ledger batch")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"git push failed: {exc.stderr.decode().strip() if exc.stderr else exc}") from exc


def seal_pending_records(
    session: Session,
    *,
    commit_to_git: bool = False,
    push_to_git: bool = False,
    git_remote: Optional[str] = None,
    git_branch: Optional[str] = None,
) -> Optional[BatchResult]:
    stmt = (
        select(CaptureRecord)
        .where(CaptureRecord.merkle_batch_id.is_(None))
        .order_by(CaptureRecord.created_at_utc.asc())
    )
    records = list(session.scalars(stmt))
    records = [rec for rec in records if rec.asset_hash]
    if not records:
        return None

    leaves = [rec.asset_hash for rec in records]
    try:
        root_hash, tree_levels = build_merkle_tree(leaves)
    except MerkleComputationError as exc:
        raise RuntimeError(f"Unable to compute Merkle root: {exc}") from exc

    batch_id = str(ulid.ULID())
    sealed_at = datetime.now(timezone.utc)

    try:
        artifacts = _write_ledger_files(
            batch_id,
            root_hash,
            sealed_at,
            records,
            tree_levels,
        )
        for rec in records:
            rec.merkle_batch_id = batch_id
            rec.merkle_root_hash = root_hash
            rec.merkle_sealed_at_utc = sealed_at
        session.commit()
    except Exception:
        session.rollback()
        raise

    result = BatchResult(
        batch_id=batch_id,
        root_hash=root_hash,
        sealed_at_utc=sealed_at,
        record_count=len(records),
        artifacts=artifacts,
    )

    if commit_to_git:
        commit_message = f"Sealed batch {batch_id} | Root: {root_hash}"
        commit_sha = _git_commit(artifacts, commit_message)
        result.git_commit_sha = commit_sha
        if push_to_git:
            remote_name = git_remote or settings.ledger_git_remote
            branch_name = git_branch or settings.ledger_git_branch
            _git_push(remote_name, branch_name)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seal pending capture proofs into a Merkle batch.")
    parser.add_argument("--commit", action="store_true", help="Create a git commit after sealing the batch.")
    parser.add_argument("--push", action="store_true", help="Push the git commit to the configured remote.")
    parser.add_argument("--remote", type=str, default=settings.ledger_git_remote, help="Git remote name (default: %(default)s).")
    parser.add_argument("--branch", type=str, default=settings.ledger_git_branch, help="Git branch name (default: %(default)s).")
    args = parser.parse_args()

    commit_to_git = args.commit or settings.ledger_git_auto_commit
    push_to_git = args.push or settings.ledger_git_auto_push
    if push_to_git:
        commit_to_git = True

    with SessionLocal() as session:
        result = seal_pending_records(
            session,
            commit_to_git=commit_to_git,
            push_to_git=push_to_git,
            git_remote=args.remote,
            git_branch=args.branch,
        )

    if result is None:
        print("No pending capture proofs to seal.")
    else:
        batch_file = next((path for path in result.artifacts if path.name.endswith(".json")), None)
        summary = (
            f"Sealed batch {result.batch_id} ({result.record_count} records) "
            f"root={result.root_hash}"
        )
        if batch_file is not None:
            summary += f" ledger_file={batch_file.name}"
        if result.git_commit_sha:
            summary += f" commit={result.git_commit_sha}"
        print(summary)


if __name__ == "__main__":
    main()
