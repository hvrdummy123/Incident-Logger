"""Upload / ingest hard limits."""

from __future__ import annotations

MAX_LINE_BYTES = 64 * 1024
MAX_UNCOMPRESSED_RATIO = 100  # gzip/zip bomb guard
ALLOWED_ARCHIVE_SUFFIXES = (".gz", ".zip", ".tar.gz", ".tgz")


def truncate_line(line: str, max_bytes: int = MAX_LINE_BYTES) -> tuple[str, bool]:
    raw = line.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return line, False
    return raw[:max_bytes].decode("utf-8", errors="replace"), True
