#!/usr/bin/env python3
"""
Embedding utilities for abby-normal.

Provides a shared embedding model, sqlite-vec connection factory,
and encoding helpers used by memory_query.py and backfill_embeddings.py.
"""

import struct
from pathlib import Path
from typing import List, Optional

# Lazy-loaded singletons — only load the model when first needed
_model = None
_model_name = "all-MiniLM-L6-v2"
_embedding_dim = 384

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


def get_model():
    """Lazily load and cache the sentence-transformers model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_model_name)
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


def get_connection(db_path: Optional[Path] = None):
    """
    Open a SQLite connection with sqlite-vec loaded.

    Uses pysqlite3 (which supports load_extension) instead of the
    standard library sqlite3 (which may be compiled without it).
    """
    import pysqlite3
    import sqlite_vec

    path = db_path or DB_PATH
    conn = pysqlite3.connect(str(path))
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
