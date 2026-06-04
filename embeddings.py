#!/usr/bin/env python3
"""
Embedding utilities for abby-normal.

Provides a shared embedding model, sqlite-vec connection factory,
and encoding helpers used by memory_query.py and backfill_embeddings.py.
"""

import contextlib
import io
import logging
import struct
import warnings
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded singletons — only load the model when first needed
_model = None
_model_name = "all-MiniLM-L6-v2"
_embedding_dim = 384

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


def get_model():
    """Lazily load and cache the sentence-transformers model."""
    global _model
    if _model is None:
        stderr_buf = io.StringIO()
        with warnings.catch_warnings(record=True) as caught, \
             contextlib.redirect_stderr(stderr_buf):
            warnings.simplefilter("always")
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(_model_name)
        for w in caught:
            logger.debug("huggingface: %s", str(w.message))
        captured = stderr_buf.getvalue().strip()
        if captured:
            logger.debug("huggingface: %s", captured)
    return _model


def get_embedding_dim() -> int:
    """Return the embedding dimension for the configured model."""
    return _embedding_dim


def get_model_name() -> str:
    """Return the configured model name."""
    return _model_name


def encode_text(text: str) -> bytes:
    """Encode a single text string into a packed float32 vector."""
    model = get_model()
    emb = model.encode(text, normalize_embeddings=True)
    return encode_float32(emb)


def encode_texts(texts: List[str]) -> List[bytes]:
    """Encode multiple text strings into packed float32 vectors."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [encode_float32(emb) for emb in embeddings]


def encode_float32(vec) -> bytes:
    """Pack a float32 vector into bytes for sqlite-vec storage."""
    return struct.pack("<" + "f" * len(vec), *vec)


def _get_sqlite_module():
    """Return a sqlite3-compatible module that supports load_extension.

    Prefers pysqlite3 when available (guaranteed load_extension support).
    Falls back to stdlib sqlite3 if it supports load_extension.
    Raises RuntimeError if neither works.
    """
    try:
        import pysqlite3
        return pysqlite3
    except ImportError:
        pass

    import sqlite3
    # Probe: stdlib sqlite3 may or may not support load_extension
    probe = sqlite3.connect(":memory:")
    try:
        probe.enable_load_extension(True)
        probe.close()
        return sqlite3
    except (AttributeError, Exception):
        probe.close()
        raise RuntimeError(
            "Neither pysqlite3 nor stdlib sqlite3 supports load_extension. "
            "Install pysqlite3-binary: pip install pysqlite3-binary"
        )


def get_connection(db_path: Optional[Path] = None):
    """
    Open a SQLite connection with sqlite-vec loaded.

    Prefers pysqlite3 (which always supports load_extension), falls back
    to stdlib sqlite3 if it supports load_extension on this platform.
    """
    sqlite_mod = _get_sqlite_module()
    import sqlite_vec

    path = db_path or DB_PATH
    conn = sqlite_mod.connect(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # Performance pragmas
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    return conn


def ensure_vec_table(conn):
    """Create the memory_embeddings vec0 table if it doesn't exist."""
    dim = get_embedding_dim()
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings "
        f"USING vec0(embedding float[{dim}])"
    )
    conn.commit()
