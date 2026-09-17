"""
Extract beneficial ownership tables from DEF 14A proxy filing HTML.
Two approaches: pandas.read_html for structured data, raw HTML for answer card passthrough.
"""
from edgar import set_identity, Company
from io import StringIO
import pandas as pd
import re
from lxml import etree

set_identity("Owen Taylor owentaylor6075@gmail.com")

company = Company("NYT")
proxy = company.get_filings(form="DEF 14A").latest().obj()
html = re.sub(r"<\?xml[^>]+\?>", "", proxy._filing_html)

# === Approach 1: pandas.read_html ===
print("=== PANDAS EXTRACTION ===")
tables = pd.read_html(StringIO(html), flavor="lxml")
print(f"Found {len(tables)} tables total\n")

ownership_keywords = ["beneficial", "shares of class", "percent of class", "shares owned"]
for i, t in enumerate(tables):
    text = t.to_string().lower()
    if any(kw in text for kw in ownership_keywords):
        t_clean = t.dropna(how="all")
        print(f"--- Table {i} ({t_clean.shape}) ---")
        print(t_clean.to_string())
        print()

# === Approach 2: raw HTML extraction via lxml ===
print("\n=== RAW HTML EXTRACTION ===")
tree = etree.HTML(html)
all_tables = tree.xpath("//table")
print(f"Found {len(all_tables)} <table> elements\n")

for i, table in enumerate(all_tables):
    table_text = etree.tostring(table, method="text", encoding="unicode").lower()
    if "beneficial" in table_text and ("class a" in table_text or "percent" in table_text):
        raw_html = etree.tostring(table, encoding="unicode", pretty_print=True)
        print(f"--- HTML Table {i} ({len(raw_html)} chars) ---")
        print(raw_html[:3000])
        print("...\n")
