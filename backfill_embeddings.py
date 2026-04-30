#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill vector embeddings for existing memory entries.

To use, activate the venv first:
  source ~/code/abby-normal/.venv/bin/activate
Or run directly:
  ~/code/abby-normal/.venv/bin/python backfill_embeddings.py
"""

import os
import sys

# Auto-activate venv if not already in it
_ABBY_VENV = os.path.expanduser("~/code/abby-normal/.venv")
if not os.environ.get("ABBY_NORMAL_IN_VENV") and os.path.isdir(_ABBY_VENV):
    import subprocess
    result = subprocess.run(
        [os.path.join(_ABBY_VENV, "bin", "python3")] + sys.argv,
        env={**os.environ, "ABBY_NORMAL_IN_VENV": "1"},
    )
    sys.exit(result.returncode)

"""

One-time script to generate and store embeddings for all entries
that don't yet have one in the memory_embeddings vec0 table.

Usage:
    python3 backfill_embeddings.py [--batch-size=32] [--dry-run]

Requires: pysqlite3-binary, sqlite-vec, sentence-transformers
Install:  pip install pysqlite3-binary sqlite-vec sentence-transformers
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


def backfill(batch_size: int = 32, dry_run: bool = False):
    """Generate embeddings for all memory entries that lack them."""
    from embeddings import (
        DB_PATH as EMB_DB_PATH,
        encode_texts,
        ensure_vec_table,
        get_connection,
        get_model,
    )

    # Open connections
    # Standard sqlite3 for reading entries (simpler, no extension needed)
    read_conn = __import__("sqlite3").connect(str(DB_PATH))
    read_conn.row_factory = __import__("sqlite3").Row

    # pysqlite3 connection for writing embeddings
    vec_conn = get_connection()
    ensure_vec_table(vec_conn)

    # Find entries without embeddings
    existing = vec_conn.execute("SELECT rowid FROM memory_embeddings").fetchall()
    existing_rowids = {r[0] for r in existing}

    total = read_conn.execute("SELECT count(*) FROM memory_entries").fetchone()[0]
    print(f"Total memory entries: {total}")
    print(f"Existing embeddings: {len(existing_rowids)}")
    print(f"Entries needing embeddings: {total - len(existing_rowids)}")

    # Clean up orphaned embeddings (entries that were deleted from memory_entries)
    orphans = vec_conn.execute(
        "SELECT me.rowid FROM memory_embeddings me "
        "LEFT JOIN memory_entries m ON me.rowid = m.rowid "
        "WHERE m.rowid IS NULL"
    ).fetchall()
    if orphans:
        orphan_ids = [o[0] for o in orphans]
        placeholders = ",".join("?" * len(orphan_ids))
        vec_conn.execute(f"DELETE FROM memory_embeddings WHERE rowid IN ({placeholders})", orphan_ids)
        vec_conn.commit()
        print(f"   Cleaned up {len(orphans)} orphaned embeddings")

    if total - len(existing_rowids) <= 0:
        print("All entries already have embeddings! Nothing to do.")
        vec_conn.close()
        read_conn.close()
        return

    # Load model (show progress)
    print(f"\nLoading embedding model...")
    model = get_model()
    print(f"Model loaded: {model}")

    # Fetch entries that need embeddings
    all_entries = read_conn.execute(
        "SELECT rowid, id, title, content FROM memory_entries ORDER BY rowid"
    ).fetchall()

    to_embed = [
        (row["rowid"], row["id"], f"{row['title']} {row['content']}")
        for row in all_entries
        if row["rowid"] not in existing_rowids
    ]

    if dry_run:
        print(f"\n[DRY RUN] Would embed {len(to_embed)} entries:")
        for rowid, entry_id, text in to_embed[:5]:
            print(f"  rowid={rowid} id={entry_id} text={text[:80]}...")
        if len(to_embed) > 5:
            print(f"  ... and {len(to_embed) - 5} more")
        vec_conn.close()
        read_conn.close()
        return

    # Process in batches
    print(f"\nEmbedding {len(to_embed)} entries (batch_size={batch_size})...")
    start = time.time()
    embedded = 0

    for i in range(0, len(to_embed), batch_size):
        batch = to_embed[i : i + batch_size]
        rowids = [b[0] for b in batch]
        texts = [b[2] for b in batch]

        # Generate embeddings
        embeddings = encode_texts(texts)

        # Insert into vec0 table
        for rowid, embedding in zip(rowids, embeddings):
            vec_conn.execute(
                "INSERT INTO memory_embeddings(rowid, embedding) VALUES (?, ?)",
                (rowid, embedding),
            )

        vec_conn.commit()
        embedded += len(batch)
        elapsed = time.time() - start
        rate = embedded / elapsed if elapsed > 0 else 0
        print(f"  [{embedded}/{len(to_embed)}] {rate:.0f} entries/sec")

    total_time = time.time() - start
    print(f"\n✅ Backfill complete! Embedded {embedded} entries in {total_time:.1f}s")

    # Verify
    final_count = vec_conn.execute("SELECT count(*) FROM memory_embeddings").fetchone()[0]
    print(f"   Total embeddings in database: {final_count}")

    # Quick sanity check: query with a test string
    print("\n--- Sanity Check ---")
    test_queries = [
        "payment processing errors",
        "database schema changes",
        "how to test features",
    ]
    from embeddings import encode_text

    for q in test_queries:
        q_emb = encode_text(q)
        results = vec_conn.execute(
            "SELECT rowid, distance FROM memory_embeddings "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT 3",
            (q_emb,),
        ).fetchall()

        print(f'  "{q}" -> top matches:')
        for rowid, dist in results:
            entry = read_conn.execute(
                "SELECT id, title FROM memory_entries WHERE rowid = ?", (rowid,)
            ).fetchone()
            if entry:
                print(f"    {entry['id']}: {entry['title']} (distance={dist:.4f})")

    vec_conn.close()
    read_conn.close()


def main():
    batch_size = 32
    dry_run = False

    for arg in sys.argv[1:]:
        if arg.startswith("--batch-size="):
            batch_size = int(arg.split("=", 1)[1])
        elif arg == "--dry-run":
            dry_run = True
        elif arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)

    try:
        backfill(batch_size=batch_size, dry_run=dry_run)
    except ImportError as e:
        print(f"Error: Missing dependency: {e}")
        print("Install with: pip install pysqlite3-binary sqlite-vec sentence-transformers")
        sys.exit(1)


if __name__ == "__main__":
    main()
