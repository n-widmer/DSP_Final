#Merkle tree utilities for building roots, generating proofs, and verifying them.

from __future__ import annotations

import hashlib
from typing import List, Tuple


def sha256(data: bytes) -> bytes:
    """Return raw 32-byte SHA-256 digest for `data`."""
    return hashlib.sha256(data).digest()


def compute_row_hash(values: List[object]) -> bytes:
    """Compute a deterministic row hash from an ordered list of values.

    - `values` should be ordered the same way every time (e.g. primary key order).
    - None values become the empty string.
    - Uses a simple pipe ('|') separator; avoid using this character in raw data
      or normalize values before hashing to guarantee determinism.

    Returns the 32-byte raw digest.
    """
    # deterministic serialization: convert each value to string and join
    parts = []
    for v in values:
        if v is None:
            parts.append("")
        elif isinstance(v, bytes):
            # include bytes directly as latin1 to preserve byte values
            parts.append(v.decode('latin1'))
        else:
            parts.append(str(v))
    serialized = "|".join(parts).encode("utf-8")
    # prefix with 0x00 to domain-separate leaf hashes from internal nodes
    return sha256(b"\x00" + serialized)


def node_hash(left: bytes, right: bytes) -> bytes:
    """Hash an internal node given left and right child hashes.

    Prefix with 0x01 to domain-separate nodes from leaves.
    """
    return sha256(b"\x01" + left + right)


def build_root_from_hashes(leaf_hashes: List[bytes]) -> bytes:
    """Build a Merkle root from a list of leaf hashes (raw bytes).

    If the number of leaves is odd, the last hash is duplicated (simple padding).
    Returns the root hash (32-byte raw digest). If `leaf_hashes` is empty,
    returns the hash of the empty byte array as convention.
    """
    if not leaf_hashes:
        return sha256(b"")
    level = list(leaf_hashes)
    while len(level) > 1:
        next_level: List[bytes] = []
        for i in range(0, len(level), 2):
            left = level[i]
            if i + 1 < len(level):
                right = level[i + 1]
            else:
                # duplicate last
                right = left
            next_level.append(node_hash(left, right))
        level = next_level
    return level[0]


def get_proof(leaf_hashes: List[bytes], index: int) -> List[Tuple[bytes, bool]]:
    """Return an inclusion proof for the leaf at `index`.

    The proof is a list of (sibling_hash, is_left) tuples where `is_left` is True
    if the sibling is the left child relative to the path node. The verifier
    should apply the node hashing accordingly.

    Raises IndexError if index out of range.
    """
    n = len(leaf_hashes)
    if index < 0 or index >= n:
        raise IndexError("leaf index out of range")
    # Build levels
    levels: List[List[bytes]] = [list(leaf_hashes)]
    while len(levels[-1]) > 1:
        prev = levels[-1]
        next_level: List[bytes] = []
        for i in range(0, len(prev), 2):
            left = prev[i]
            if i + 1 < len(prev):
                right = prev[i + 1]
            else:
                right = left
            next_level.append(node_hash(left, right))
        levels.append(next_level)

    proof: List[Tuple[bytes, bool]] = []
    idx = index
    for level in levels[:-1]:
        # sibling index
        if idx % 2 == 0:
            # sibling is idx+1 if present else duplicate
            sib_idx = idx + 1 if idx + 1 < len(level) else idx
            sibling = level[sib_idx]
            # sibling is right
            proof.append((sibling, False))
        else:
            sib_idx = idx - 1
            sibling = level[sib_idx]
            # sibling is left
            proof.append((sibling, True))
        idx = idx // 2
    return proof


def verify_proof(leaf_hash: bytes, proof: List[Tuple[bytes, bool]], root: bytes) -> bool:
    """Verify an inclusion proof.

    `proof` is the list returned by `get_proof` — sequence of (sibling_hash, is_left).
    Returns True if recomputed root matches `root`.
    """
    cur = leaf_hash
    for sibling_hash, is_left in proof:
        if is_left:
            cur = node_hash(sibling_hash, cur)
        else:
            cur = node_hash(cur, sibling_hash)
    return cur == root


def bytes_to_hex(b: bytes) -> str:
    return b.hex()


def hex_to_bytes(h: str) -> bytes:
    return bytes.fromhex(h)


__all__ = [
    "sha256",
    "compute_row_hash",
    "node_hash",
    "build_root_from_hashes",
    "get_proof",
    "verify_proof",
    "bytes_to_hex",
    "hex_to_bytes",
]
