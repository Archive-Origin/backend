from __future__ import annotations

import hashlib
from typing import Iterable, List, Sequence, Tuple

SHA256_PREFIX = "sha256:"
SHA256_LENGTH = 64


class MerkleComputationError(RuntimeError):
    """Raised when Merkle tree computation cannot be completed."""


def _strip_prefix(value: str) -> str:
    if not value.startswith(SHA256_PREFIX):
        raise MerkleComputationError("hash must start with 'sha256:'")
    digest = value.split("sha256:", 1)[1]
    if len(digest) != SHA256_LENGTH:
        raise MerkleComputationError("sha256 digest must be 64 hex characters")
    return digest.lower()


def _hash_pair(left: str, right: str) -> str:
    data = (left + right).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    return digest


def compute_merkle_root(leaves: Sequence[str]) -> str:
    """
    Compute a Merkle root from a sequence of sha256-prefixed hashes.
    """
    if not leaves:
        raise MerkleComputationError("at least one leaf hash is required")

    level = [_strip_prefix(leaf) for leaf in leaves]

    while len(level) > 1:
        if len(level) % 2 == 1:
            level = list(level) + [level[-1]]
        next_level: List[str] = []
        for idx in range(0, len(level), 2):
            next_level.append(_hash_pair(level[idx], level[idx + 1]))
        level = next_level

    return f"{SHA256_PREFIX}{level[0]}"


def build_merkle_tree(leaves: Sequence[str]) -> Tuple[str, List[Sequence[str]]]:
    """
    Build the full Merkle tree levels for auditing/debugging.
    Returns the root hash (sha256-prefixed) and the list of levels used.
    """
    if not leaves:
        raise MerkleComputationError("at least one leaf hash is required")

    levels: List[Sequence[str]] = []
    current = [_strip_prefix(leaf) for leaf in leaves]
    levels.append(tuple(current))

    while len(current) > 1:
        if len(current) % 2 == 1:
            current = list(current) + [current[-1]]
        next_level: List[str] = []
        for idx in range(0, len(current), 2):
            next_level.append(_hash_pair(current[idx], current[idx + 1]))
        current = next_level
        levels.append(tuple(current))

    root_hex = current[0]
    return f"{SHA256_PREFIX}{root_hex}", levels
