"""Ingest documents from data/test-docs/ into the RAG pipeline.

Usage:
    python -m scripts.ingest_docs                   # ingest all test docs
    python -m scripts.ingest_docs --path some/file.pdf  # ingest one file
    python -m scripts.ingest_docs --dry-run          # preview without writing
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
TEST_DOCS = ROOT / "data" / "test-docs"


def ingest_file(path: Path, *, dry_run: bool = False) -> int | None:
    from rag.extract import extract_text, doc_type_from_filename
    from rag.indexer import DocIn, upsert_document

    data = path.read_bytes()
    text = extract_text(path.name, data)
    if not text:
        log.warning("skipping %s — no text extracted", path.name)
        return None

    doc_type = doc_type_from_filename(path.name)
    log.info("%s → %d chars, type=%s", path.name, len(text), doc_type)

    if dry_run:
        from rag.indexer import chunk_text
        chunks = chunk_text(text)
        log.info("  would create %d chunks", len(chunks))
        for i, c in enumerate(chunks[:3]):
            log.info("  chunk %d: %s…", i, c[:120])
        return None

    doc = DocIn(
        title=path.stem,
        doc_type=doc_type,
        text=text,
        source_path=str(path.relative_to(ROOT)),
        metadata={"filename": path.name, "size_bytes": len(data)},
    )
    doc_id = upsert_document(doc, replace=True)
    log.info("  → document_id=%d", doc_id)
    return doc_id


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into PEHero RAG")
    parser.add_argument("--path", help="single file to ingest")
    parser.add_argument("--dry-run", action="store_true", help="preview without writing to DB")
    args = parser.parse_args()

    if args.path:
        files = [Path(args.path)]
    elif TEST_DOCS.is_dir():
        files = sorted(TEST_DOCS.iterdir())
    else:
        log.error("no test-docs directory at %s", TEST_DOCS)
        sys.exit(1)

    files = [f for f in files if f.is_file() and not f.name.startswith(".")]
    log.info("found %d files to ingest", len(files))

    ids = []
    for f in files:
        doc_id = ingest_file(f, dry_run=args.dry_run)
        if doc_id is not None:
            ids.append(doc_id)

    if not args.dry_run and ids:
        from rag.indexer import build_ann_index
        build_ann_index()

    log.info("done — %d documents indexed", len(ids))


if __name__ == "__main__":
    main()
