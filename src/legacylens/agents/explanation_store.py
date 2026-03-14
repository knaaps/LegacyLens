"""ExplanationStore — Persist high-confidence verified explanations.

Stores finalized explanations (post-Finalizer, verdict == PASS, fidelity >= threshold)
in a dedicated ChromaDB collection called 'verified_explanations'.

Design decisions
----------------
* Same ``db_path`` as CodeEmbedder (default ./legacylens_db) — zero extra config.
* **No vector/embedding stored** — lookup is exact-id by qualified function name,
  so CodeBERT does NOT need to load for cache reads.  Chroma supports this via
  ``collection.get(ids=[...])``.
* Metadata stored as Chroma scalar fields (str / float / int only — Chroma
  limitation).  ``explanation_text`` and ``finalized_markdown`` are stored there.
* Fidelity threshold: 0.75 by default; override via env
  ``LEGACYLENS_FIDELITY_THRESHOLD``.
* Codebase version fingerprint: read from ``~/.legacylens/index_fingerprint.txt``
  (written by ``legacylens index``).  If absent → ``None`` (cache still works;
  staleness check skipped).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

COLLECTION_NAME = "verified_explanations"
_DEFAULT_DB_PATH = "./legacylens_db"
_FINGERPRINT_FILE = Path.home() / ".legacylens" / "index_fingerprint.txt"

# Minimum fidelity score required to persist an explanation (configurable).
FIDELITY_THRESHOLD: float = float(os.environ.get("LEGACYLENS_FIDELITY_THRESHOLD", "0.75"))


# ── Helpers ────────────────────────────────────────────────────────────────────


def current_fingerprint() -> Optional[str]:
    """Return the current codebase index fingerprint, or None if not available.

    The ``legacylens index`` command writes this file.  If absent (e.g. first
    run, or user hasn't used the CLI indexer), staleness checking is skipped and
    the cache is always considered valid.
    """
    try:
        if _FINGERPRINT_FILE.exists():
            return _FINGERPRINT_FILE.read_text().strip() or None
    except OSError:
        pass
    return None


# ── ExplanationStore ───────────────────────────────────────────────────────────


class ExplanationStore:
    """Thin Chroma wrapper for storing and retrieving verified explanations.

    Usage
    -----
    >>> store = ExplanationStore()
    >>> store.upsert("com.example.Foo.bar", text="...", markdown="...",
    ...              confidence=85.0, fidelity=0.82, codebase_version="abc123")
    >>> record = store.get("com.example.Foo.bar", codebase_version="abc123")
    >>> if record:
    ...     print(record["finalized_markdown"])
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        # Lazily initialised on first use
        self._client = None
        self._collection = None

    # ── Private helpers ────────────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        """Lazily connect to ChromaDB and get/create the collection."""
        if self._collection is not None:
            return
        try:
            import chromadb
            from chromadb.config import Settings

            self._db_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self._db_path),
                settings=Settings(anonymized_telemetry=False),
            )
            # No embedding function — we rely on exact-id lookup via .get()
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                # No HNSW space metadata needed since we don't do similarity search
            )
        except Exception as exc:
            logger.warning("ExplanationStore: could not connect to ChromaDB: %s", exc)
            raise

    # ── Public API ─────────────────────────────────────────────────────────────

    def upsert(
        self,
        fn_qualified_name: str,
        text: str,
        markdown: str,
        confidence: float,
        fidelity: float,
        codebase_version: Optional[str] = None,
    ) -> None:
        """Store (or update) a high-confidence explanation.

        Args:
            fn_qualified_name: Fully-qualified function name used as the
                               Chroma document id (e.g.
                               "petclinic.owner.OwnerController.processFindForm").
            text:              Plain-text explanation (from Writer/Finalizer).
            markdown:          Formatted markdown explanation.
            confidence:        Critic confidence score (0–100).
            fidelity:          Regeneration fidelity score (0.0–1.0).
            codebase_version:  Git hash / mtime fingerprint of the indexed
                               codebase (or None if not tracked).
        """
        self._ensure_connected()

        timestamp = datetime.now(tz=timezone.utc).isoformat()

        # Chroma metadata values must be str/int/float — no nested objects.
        metadata: dict = {
            "explanation_text": text[:4096],  # guard against Chroma field limit
            "finalized_markdown": markdown[:8192],
            "confidence": float(confidence),
            "fidelity": float(fidelity),
            "critic_verdict": "PASS",
            "timestamp": timestamp,
            "codebase_version": codebase_version or "",
        }

        # Upsert with id = qualified name; document = plain-text explanation
        # (document is mandatory in Chroma, use text for it)
        self._collection.upsert(
            ids=[fn_qualified_name],
            documents=[text[:4096]],
            metadatas=[metadata],
        )

        logger.info(
            "ExplanationStore: stored high-confidence explanation for '%s' "
            "(confidence=%.0f%%, fidelity=%.0%%, version=%s)",
            fn_qualified_name,
            confidence,
            fidelity,
            codebase_version or "n/a",
        )
        print(
            f"  [ExplanationStore] Stored high-confidence explanation for "
            f"'{fn_qualified_name}' "
            f"(confidence={confidence:.0f}%, fidelity={fidelity:.0%})"
        )

    def get(
        self,
        fn_qualified_name: str,
        codebase_version: Optional[str] = None,
    ) -> Optional[dict]:
        """Retrieve a stored explanation, or None if not found / stale.

        Args:
            fn_qualified_name: Fully-qualified function name (same id used in
                               upsert).
            codebase_version:  If provided, the stored record is rejected
                               (returns None) when its version doesn't match —
                               forcing a fresh LLM run after a re-index.
                               Pass None to skip version checking.

        Returns:
            dict with keys: ``explanation_text``, ``finalized_markdown``,
            ``confidence``, ``fidelity``, ``critic_verdict``, ``timestamp``,
            ``codebase_version`` — or None if no valid record exists.
        """
        try:
            self._ensure_connected()
        except Exception:
            return None

        try:
            result = self._collection.get(
                ids=[fn_qualified_name],
                include=["documents", "metadatas"],
            )
        except Exception as exc:
            logger.warning("ExplanationStore.get() failed: %s", exc)
            return None

        if not result["ids"]:
            return None

        meta = result["metadatas"][0]

        # Staleness check: if the caller provides a version AND it differs from
        # what's stored, treat the record as stale.
        if codebase_version and meta.get("codebase_version"):
            stored_version = meta["codebase_version"]
            if stored_version and stored_version != codebase_version:
                logger.debug(
                    "ExplanationStore: stale record for '%s' (stored=%s, current=%s)",
                    fn_qualified_name,
                    stored_version,
                    codebase_version,
                )
                return None

        return {
            "fn_qualified_name": fn_qualified_name,
            "explanation_text": meta.get("explanation_text", ""),
            "finalized_markdown": meta.get("finalized_markdown", ""),
            "confidence": meta.get("confidence", 0.0),
            "fidelity": meta.get("fidelity", 0.0),
            "critic_verdict": meta.get("critic_verdict", "PASS"),
            "timestamp": meta.get("timestamp", ""),
            "codebase_version": meta.get("codebase_version", ""),
        }

    def count(self) -> int:
        """Return the number of stored explanations (useful for tests/stats)."""
        try:
            self._ensure_connected()
            return self._collection.count()
        except Exception:
            return 0
