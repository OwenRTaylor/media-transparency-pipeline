"""
Batch DEF 14A ownership table parser test.
Runs parser against all 2026 DEF 14A filings, saves results to SQLite for analysis.
"""
from edgar import set_identity, get_filings, Filing
from io import StringIO
import pandas as pd
import sqlite3
import re
import sys
import traceback

set_identity("Owen Taylor owentaylor6075@gmail.com")

DB_PATH = "/tmp/proxy_parse_results.db"

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


def check_text_fallback(text):
    if not text:
        return None
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


def get_filing_html(proxy):
    html = proxy._filing_html
    if html is not None:
        return re.sub(r"<\?xml[^>]+\?>", "", html)
    text = proxy._filing_text
    if text is not None:
        return text
    return None


def parse_filing(filing):
    result = {
        "cik": filing.cik,
        "company": filing.company,
        "accession_no": filing.accession_no,
        "filing_date": str(filing.filing_date),
        "status": None,
        "total_tables": 0,
        "ownership_tables": 0,
        "total_data_rows": 0,
        "error": None,
    }

    try:
        proxy = filing.obj()
    except Exception as e:
        result["status"] = "obj_error"
        result["error"] = str(e)[:200]
        return result, []

    source = get_filing_html(proxy)
    if source is None:
        result["status"] = "no_content"
        return result, []

    try:
        tables = pd.read_html(StringIO(source), flavor="lxml")
    except ValueError:
        fallback = check_text_fallback(source)
        if fallback:
            result["status"] = "text_fallback"
        else:
            result["status"] = "no_tables_in_html"
        return result, []
    except Exception as e:
        result["status"] = "parse_error"
        result["error"] = str(e)[:200]
        return result, []

    result["total_tables"] = len(tables)

    ownership_tables = []
    for i, t in enumerate(tables):
        t_clean = t.dropna(how="all")
        if is_ownership_table(t_clean):
            data_rows = max(0, len(t_clean) - 1)
            ownership_tables.append({
                "cik": filing.cik,
                "accession_no": filing.accession_no,
                "table_index": i,
                "rows": len(t_clean),
                "cols": len(t_clean.columns),
                "data_rows": data_rows,
                "header_text": get_header_text(t_clean)[:500],
            })

    result["ownership_tables"] = len(ownership_tables)
    result["total_data_rows"] = sum(t["data_rows"] for t in ownership_tables)

    if len(ownership_tables) > 0:
        result["status"] = "ok"
    else:
        fallback = check_text_fallback(proxy._filing_text or "")
        if fallback:
            result["status"] = "text_fallback"
        else:
            result["status"] = "no_ownership_tables"

    return result, ownership_tables


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            cik INTEGER,
            company TEXT,
            accession_no TEXT PRIMARY KEY,
            filing_date TEXT,
            status TEXT,
            total_tables INTEGER,
            ownership_tables INTEGER,
            total_data_rows INTEGER,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ownership_table_details (
            cik INTEGER,
            accession_no TEXT,
            table_index INTEGER,
            rows INTEGER,
            cols INTEGER,
            data_rows INTEGER,
            header_text TEXT,
            PRIMARY KEY (accession_no, table_index)
        )
    """)
    conn.commit()
    return conn


def get_failures(conn):
    cur = conn.execute(
        "SELECT accession_no, company, cik, filing_date FROM results "
        "WHERE status NOT IN ('ok')"
    )
    return cur.fetchall()


def main():
    rerun = "--rerun-failures" in sys.argv

    conn = init_db(DB_PATH)

    if rerun:
        failures = get_failures(conn)
        total = len(failures)
        print(f"Re-running {total} failures with fixes...")

        for idx, (acc, company, cik, filing_date) in enumerate(failures, 1):
            print(f"  [{idx}/{total}] {company[:40]}...", end=" ", flush=True)

            filing = Filing(form="DEF 14A", filing_date=filing_date,
                            company=company, cik=cik, accession_no=acc)
            try:
                result, table_details = parse_filing(filing)
            except Exception as e:
                result = {
                    "cik": cik, "company": company, "accession_no": acc,
                    "filing_date": filing_date, "status": "crash",
                    "total_tables": 0, "ownership_tables": 0,
                    "total_data_rows": 0, "error": traceback.format_exc()[:200],
                }
                table_details = []

            conn.execute(
                "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?)",
                (result["cik"], result["company"], result["accession_no"],
                 result["filing_date"], result["status"], result["total_tables"],
                 result["ownership_tables"], result["total_data_rows"], result["error"])
            )
            for td in table_details:
                conn.execute(
                    "INSERT OR REPLACE INTO ownership_table_details VALUES (?,?,?,?,?,?,?)",
                    (td["cik"], td["accession_no"], td["table_index"],
                     td["rows"], td["cols"], td["data_rows"], td["header_text"])
                )
            conn.commit()
            print(result["status"])

    else:
        print("Fetching 2026 DEF 14A filing index...")
        filings = get_filings(form="DEF 14A", year=2026)
        total = len(filings)
        print(f"Found {total} filings")

        already_done = set(
            r[0] for r in conn.execute("SELECT accession_no FROM results").fetchall()
        )
        print(f"Already processed: {len(already_done)}, remaining: {total - len(already_done)}")

        for idx in range(total):
            filing = filings[idx]
            if filing.accession_no in already_done:
                continue

            print(f"  [{idx+1}/{total}] {filing.company[:40]}...", end=" ", flush=True)

            try:
                result, table_details = parse_filing(filing)
            except Exception as e:
                result = {
                    "cik": filing.cik, "company": filing.company,
                    "accession_no": filing.accession_no,
                    "filing_date": str(filing.filing_date),
                    "status": "crash", "total_tables": 0,
                    "ownership_tables": 0, "total_data_rows": 0,
                    "error": traceback.format_exc()[:200],
                }
                table_details = []

            conn.execute(
                "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?)",
                (result["cik"], result["company"], result["accession_no"],
                 result["filing_date"], result["status"], result["total_tables"],
                 result["ownership_tables"], result["total_data_rows"], result["error"])
            )
            for td in table_details:
                conn.execute(
                    "INSERT OR REPLACE INTO ownership_table_details VALUES (?,?,?,?,?,?,?)",
                    (td["cik"], td["accession_no"], td["table_index"],
                     td["rows"], td["cols"], td["data_rows"], td["header_text"])
                )
            conn.commit()
            print(result["status"])

    # Summary
    print(f"\n{'='*60}")
    print("BATCH COMPLETE")
    print(f"{'='*60}")
    df = pd.read_sql("SELECT * FROM results", conn)
    print(f"\nTotal: {len(df)}")
    print(f"\nStatus counts:")
    print(df["status"].value_counts().to_string())
    print(f"\nOwnership tables found: {df['ownership_tables'].sum()}")
    print(f"Total data rows: {df['total_data_rows'].sum()}")
    print(f"\nResults saved to: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
