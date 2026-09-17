"""
Test three parser fixes against one filing from each failure category:
1. Unicode junk in numeric data (Otis Worldwide — was no_ownership_tables)
2. _filing_html is None (Andersen Group — was html_error)
3. No <table> tags (Auburn National — was parse_error)
"""
from edgar import set_identity, Filing
from io import StringIO
import pandas as pd
import re

set_identity("Owen Taylor owentaylor6075@gmail.com")

HEADER_STRONG_SIGNALS = [
    "beneficially owned", "beneficial owner", "shares beneficially",
    "percent of class", "% of class", "percent of common stock",
    "shares of class", "voting power", "% vote of all classes", "% vote",
]

DISQUALIFY_PATTERNS = [
    r"page\s*no", r"^\s*Q\.\s", r"table of contents",
    r"proxy solicited on behalf", r"items of business",
    r"proposal.*board.*recommend", r"compensation committee",
    r"proxy statement summary", r"vote required",
    r"effect of (broker|abstention)", r"change of control",
    r"change in the composition", r"reorganization.*merger",
    r"approval by the shareholders", r"limitations on awards",
    r"the \d{4} equity plan", r"what constitutes a quorum",
    r"who bears the cost", r"a message from", r"shareholder proposal",
]

UNICODE_JUNK = re.compile(r"[​‌‍‎‏\xa0﻿]")

TEXT_OWNERSHIP_PATTERN = re.compile(
    r"security ownership of certain beneficial owners|"
    r"beneficial ownership of common stock|"
    r"security ownership of management",
    re.IGNORECASE,
)


def has_numeric_data(df, min_numeric_cells=3):
    count = 0
    for col in df.columns:
        for val in df[col]:
            s = UNICODE_JUNK.sub("", str(val))
            s = s.replace(",", "").replace("%", "").replace("*", "").strip()
            s = re.sub(r"\(\d+\)$", "", s).strip()
            if s in ("", "nan", "—", "-", "NaN"):
                continue
            try:
                float(s)
                count += 1
                if count >= min_numeric_cells:
                    return True
            except ValueError:
                continue
    return False


def get_header_text(t_clean, n_rows=3):
    parts = []
    for row_idx in range(min(n_rows, len(t_clean))):
        parts.append(" ".join(str(v) for v in t_clean.iloc[row_idx].dropna()).lower())
    text = " ".join(parts)
    return UNICODE_JUNK.sub(" ", text).replace("  ", " ")


def is_ownership_table(t_clean):
    if len(t_clean) < 3 or len(t_clean.columns) < 3:
        return False
    header_text = get_header_text(t_clean)
    if not any(sig in header_text for sig in HEADER_STRONG_SIGNALS):
        return False
    full_text = header_text + " " + t_clean.to_string().lower()
    for pattern in DISQUALIFY_PATTERNS:
        if re.search(pattern, full_text[:1200]):
            return False
    if not has_numeric_data(t_clean):
        return False
    return True


def check_text_fallback(text):
    match = TEXT_OWNERSHIP_PATTERN.search(text)
    if not match:
        return None
    start = match.start()
    section = text[start:start + 3000]
    lines_with_numbers = 0
    for line in section.split("\n"):
        nums = re.findall(r"[\d,]{3,}", line)
        if len(nums) >= 2:
            lines_with_numbers += 1
    if lines_with_numbers >= 3:
        return section
    return None


def get_filing_html(proxy):
    html = proxy._filing_html
    if html is not None:
        return re.sub(r"<\?xml[^>]+\?>", "", html)
    text = proxy._filing_text
    if text is None:
        return None
    return text


def parse_proxy(proxy):
    source = get_filing_html(proxy)
    if source is None:
        return "no_content", [], None

    try:
        tables = pd.read_html(StringIO(source), flavor="lxml")
    except ValueError:
        fallback = check_text_fallback(source)
        if fallback:
            return "text_fallback", [], fallback
        return "no_tables_in_html", [], None
    except Exception as e:
        return f"parse_error: {e}", [], None

    matches = []
    for i, t in enumerate(tables):
        t_clean = t.dropna(how="all")
        if is_ownership_table(t_clean):
            matches.append((i, t_clean))

    if matches:
        return "ok", matches, None

    fallback = check_text_fallback(proxy._filing_text or "")
    if fallback:
        return "text_fallback", [], fallback

    return "no_ownership_tables", [], None


# === Test cases ===

import sqlite3

DB_PATH = "/tmp/proxy_parse_results.db"

TEST_CASES = [
    {
        "label": "FIX 1 — Unicode junk (was: no_ownership_tables)",
        "accession_no": "0001140361-26-015389",
    },
    {
        "label": "FIX 2 — _filing_html is None (was: html_error)",
        "accession_no": "0001193125-26-196171",
    },
    {
        "label": "FIX 3 — No <table> tags (was: parse_error)",
        "accession_no": "0001193125-26-139480",
    },
]

conn = sqlite3.connect(DB_PATH)

for tc in TEST_CASES:
    cur = conn.execute(
        "SELECT company, cik, filing_date FROM results WHERE accession_no=?",
        (tc["accession_no"],))
    row = cur.fetchone()
    company, cik, filing_date = row

    print(f"\n{'='*60}")
    print(f"  {tc['label']}")
    print(f"  {company}")
    print(f"{'='*60}")

    filing = Filing(form="DEF 14A", filing_date=filing_date,
                    company=company, cik=cik,
                    accession_no=tc["accession_no"])
    proxy = filing.obj()

    status, matches, fallback_text = parse_proxy(proxy)
    print(f"  Status: {status}")

    if matches:
        print(f"  Ownership tables: {len(matches)}")
        for i, t_clean in matches:
            print(f"    Table {i} ({t_clean.shape})")
            for r in range(min(2, len(t_clean))):
                vals = [str(v)[:50] for v in t_clean.iloc[r].dropna()]
                print(f"      row {r}: {' | '.join(vals[:5])}")

    if fallback_text:
        print(f"  Text fallback ({len(fallback_text)} chars):")
        for line in fallback_text.split("\n")[:8]:
            print(f"    {line.rstrip()}")

conn.close()
print(f"\n{'='*60}")
print("DONE")
