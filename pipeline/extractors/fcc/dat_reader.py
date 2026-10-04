"""Streaming reader for FCC LMS/CDBS bulk `.dat` files.

The `.dat` files are NOT plain pipe-delimited-lines. Real structure:

    field1|field2|...|fieldN|^|<CRLF>

- Fields are delimited by `|`.
- The record terminator is the literal 3-char sequence ``|^|`` (a `^`
  sentinel guarded by pipes), followed by a CRLF.
- Free-text fields (names, addresses) sometimes contain raw newlines, so a
  single logical record can span several physical lines. In the current dump
  ~2,345 of app_party.dat's 1.77M physical lines are such continuations.

Consequences that force this reader to exist:
- Splitting on physical newlines (what `csv.DictReader(delimiter="|")` does)
  corrupts every multi-line record. We split on the ``|^|`` terminator instead.
- Because the separator is the whole ``|^|``, the trailing `^`/empty columns
  that a naive `|`-split produces never appear here: a record splits into
  exactly its N real columns.

INV-15: never whole-reads the file. Reads in fixed-size chunks, keeps only a
small tail buffer between chunks, yields one record dict at a time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, List, Optional

RECORD_SEP = "|^|"
# latin-1 never raises on decode; FCC dumps carry cp1252-ish bytes in names.
ENCODING = "latin-1"
CHUNK = 1 << 20  # 1 MiB


def _split_fields(raw: str) -> List[str]:
    """One record chunk -> its field list.

    A chunk arrives as e.g. "\r\nf1|f2|...|fN" — a leading CRLF left over from
    the previous record's terminator. Strip the record-edge whitespace, then
    split on the field delimiter.
    """
    return raw.strip("\r\n").split("|")


def iter_records(
    path: str | Path,
    chunk_size: int = CHUNK,
) -> Iterator[Dict[str, str]]:
    """Stream one dict per logical record, keyed by the header row.

    Field counts that don't match the header are still yielded but tagged with
    a synthetic ``__malformed__`` key so callers can flag rather than silently
    misalign (an embedded `|` in a text field is the usual cause).
    """
    path = Path(path)
    header: Optional[List[str]] = None
    buf = ""
    with open(path, "r", encoding=ENCODING, newline="") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            buf += chunk
            parts = buf.split(RECORD_SEP)
            buf = parts.pop()  # last part is an incomplete record; carry it over
            for raw in parts:
                fields = _split_fields(raw)
                if header is None:
                    header = fields
                    continue
                yield _to_dict(header, fields)
    # Trailing record (file may or may not end with a terminator + newline).
    tail = buf.strip("\r\n")
    if tail and header is not None:
        yield _to_dict(header, _split_fields(tail))


def _to_dict(header: List[str], fields: List[str]) -> Dict[str, str]:
    row = dict(zip(header, fields))
    if len(fields) != len(header):
        row["__malformed__"] = f"expected {len(header)} cols, got {len(fields)}"
    return row
