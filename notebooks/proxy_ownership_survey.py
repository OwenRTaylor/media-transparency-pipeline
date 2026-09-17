"""
Survey beneficial ownership table structure across diverse company types.
Goal: see if pandas.read_html + keyword matching reliably finds ownership tables,
and how much the column structure varies.

Findings so far:
- Most companies use HTML <table> elements — pandas.read_html works.
- Some older/smaller filings (e.g., SALM) use whitespace-aligned plain text
  tables with no <table> tags. Those need a text-based fallback.
"""
from edgar import set_identity, Company
from io import StringIO
import pandas as pd
import re

set_identity("Owen Taylor owentaylor6075@gmail.com")

COMPANIES = [
    # ── Media: Broadcast TV / Station Groups ──
    ("DIS", "Disney — broadcast + streaming conglomerate"),
    ("CMCSA", "Comcast/NBCUniversal — broadcast + cable parent"),
    ("FOXA", "Fox Corp — dual-class broadcast"),
    ("PARA", "Paramount Global — broadcast + streaming"),
    ("WBD", "Warner Bros Discovery — broadcast + streaming"),
    ("NXST", "Nexstar Media — largest local TV station group"),
    ("SBGI", "Sinclair Broadcast — large station group, conservative"),
    ("GTN", "Gray Television — mid-cap broadcast"),
    ("TGNA", "Tegna — station group, post-Gannett split"),
    ("SSP", "E.W. Scripps — broadcast + networks"),
    ("EVC", "Entravision — Hispanic media, broadcast + digital"),

    # ── Media: Cable / Satellite ──
    ("CHTR", "Charter Communications — cable operator"),
    ("CABO", "Cable One — mid-cap cable"),
    ("SIRI", "Sirius XM — satellite radio"),

    # ── Media: Publishing / Newspapers ──
    ("NYT", "New York Times — dual-class newspaper"),
    ("NWSA", "News Corp — dual-class publishing + media"),
    ("GCI", "Gannett — largest US newspaper chain"),
    ("LEE", "Lee Enterprises — regional newspapers"),
    ("MNI", "Manning & Napier — small-cap (was newspaper, verify)"),
    ("DJCO", "Daily Journal Corp — newspaper + tech, Munger-linked"),

    # ── Media: Digital / Streaming ──
    ("NFLX", "Netflix — streaming pure-play"),
    ("ROKU", "Roku — streaming platform"),
    ("SPOT", "Spotify — audio streaming, foreign private issuer"),
    ("CARG", "CarGurus — digital marketplace (test: non-media digital)"),
    ("ZD", "Ziff Davis — digital media conglomerate"),
    ("IAC", "IAC — internet holding company, complex structure"),
    ("ANGI", "Angi — IAC subsidiary/spinoff"),

    # ── Media: Radio ──
    ("SALM", "Salem Communications — small-cap radio"),
    ("IHRT", "iHeartMedia — radio, post-bankruptcy"),
    ("CCO", "Clear Channel Outdoor — billboard/out-of-home"),

    # ── Media: Advertising / PR ──
    ("IPG", "Interpublic Group — advertising holding co"),
    ("OMC", "Omnicom — advertising holding co"),

    # ── Telecom ──
    ("T", "AT&T — telecom, former media parent"),
    ("VZ", "Verizon — telecom"),
    ("TMUS", "T-Mobile — telecom, Deutsche Telekom subsidiary"),
    ("LUMN", "Lumen Technologies — telecom/fiber"),
    ("USM", "US Cellular — regional telecom"),
    ("ASTS", "AST SpaceMobile — speculative telecom"),

    # ── Big Tech (media-adjacent) ──
    ("GOOGL", "Alphabet — triple-class, YouTube parent"),
    ("META", "Meta — social media / advertising"),
    ("AAPL", "Apple — tech, Apple TV+"),
    ("AMZN", "Amazon — tech, Prime Video / MGM parent"),
    ("MSFT", "Microsoft — tech, LinkedIn / gaming"),

    # ── Tech: Mid/Small-cap ──
    ("PINS", "Pinterest — social media / advertising"),
    ("SNAP", "Snap — social media, dual-class"),
    ("RDDT", "Reddit — social media, recent IPO"),
    ("MTCH", "Match Group — IAC spinoff"),
    ("ETSY", "Etsy — e-commerce marketplace"),
    ("TTWO", "Take-Two Interactive — gaming"),
    ("EA", "Electronic Arts — gaming"),
    ("RBLX", "Roblox — gaming platform"),
    ("U", "Unity Technologies — gaming engine"),
    ("DDOG", "Datadog — SaaS (structure diversity)"),
    ("CRWD", "CrowdStrike — cybersecurity"),
    ("PLTR", "Palantir — dual-class tech"),

    # ── Financial: Banks ──
    ("JPM", "JPMorgan Chase — largest US bank"),
    ("BAC", "Bank of America — mega-cap bank"),
    ("WFC", "Wells Fargo — mega-cap bank"),
    ("GS", "Goldman Sachs — investment bank"),
    ("MS", "Morgan Stanley — investment bank"),
    ("C", "Citigroup — global bank"),
    ("USB", "US Bancorp — regional bank"),
    ("SCHW", "Charles Schwab — brokerage / bank"),
    ("TFC", "Truist Financial — regional bank"),
    ("FITB", "Fifth Third Bancorp — regional bank"),
    ("SIVB", "SVB Financial — if still filing (post-collapse test)"),
    ("WAL", "Western Alliance — mid-cap bank"),
    ("PACW", "PacWest Bancorp — mid-cap bank"),

    # ── Financial: Asset Management / PE ──
    ("BLK", "BlackRock — largest asset manager"),
    ("BX", "Blackstone — PE giant"),
    ("KKR", "KKR — PE giant"),
    ("APO", "Apollo Global — PE giant"),
    ("ARES", "Ares Management — PE / credit"),
    ("CG", "Carlyle Group — PE"),
    ("OWL", "Blue Owl Capital — alt asset manager"),
    ("BN", "Brookfield Corp — Canadian asset manager, NYSE-listed"),
    ("BAM", "Brookfield Asset Mgmt — Brookfield spinoff"),
    ("IVZ", "Invesco — asset manager"),
    ("TROW", "T. Rowe Price — asset manager"),
    ("BEN", "Franklin Templeton — asset manager"),

    # ── Financial: Insurance ──
    ("BRK-A", "Berkshire Hathaway — conglomerate / insurance, dual-class"),
    ("MET", "MetLife — insurance"),
    ("ALL", "Allstate — insurance"),
    ("PRU", "Prudential Financial — insurance / asset mgmt"),
    ("AIG", "AIG — insurance, complex post-bailout structure"),
    ("MKL", "Markel — specialty insurance, mini-Berkshire"),
    ("ERIE", "Erie Indemnity — insurance, unusual structure"),

    # ── Conglomerates / Holding Companies ──
    ("GE", "GE Aerospace — post-breakup industrial"),
    ("HON", "Honeywell — diversified industrial"),
    ("MMM", "3M — diversified industrial"),
    ("LBRDA", "Liberty Broadband — Malone tracking stock"),
    ("FWONA", "Liberty Media / Formula One — Malone tracker"),
    ("LSXMA", "Liberty SiriusXM — Malone tracker"),
    ("BATRA", "Atlanta Braves Holdings — Liberty spinoff"),
    ("LBTYA", "Liberty Global — international cable, Malone"),
    ("VIAC", "Verify: old Viacom ticker, may redirect to PARA"),

    # ── Healthcare / Pharma ──
    ("JNJ", "Johnson & Johnson — mega-cap pharma"),
    ("UNH", "UnitedHealth — health insurance / Optum"),
    ("PFE", "Pfizer — pharma"),
    ("LLY", "Eli Lilly — pharma"),
    ("ABBV", "AbbVie — pharma, Abbott spinoff"),
    ("ABT", "Abbott Labs — diversified healthcare"),
    ("CI", "Cigna — health insurance"),
    ("HCA", "HCA Healthcare — hospital chain, PE history"),
    ("MRNA", "Moderna — biotech, pandemic-era growth"),
    ("BIIB", "Biogen — biotech"),
    ("REGN", "Regeneron — biotech, founder-led"),
    ("ILMN", "Illumina — genomics"),

    # ── Consumer / Retail ──
    ("WMT", "Walmart — mega-cap retail, family-controlled"),
    ("COST", "Costco — retail"),
    ("TGT", "Target — retail"),
    ("HD", "Home Depot — retail"),
    ("NKE", "Nike — consumer, dual-class"),
    ("SBUX", "Starbucks — consumer"),
    ("MCD", "McDonald's — consumer/franchise"),
    ("YUM", "Yum Brands — restaurant/franchise"),
    ("DPZ", "Domino's — franchise"),
    ("KO", "Coca-Cola — consumer staples, Berkshire stake"),
    ("PEP", "PepsiCo — consumer staples"),
    ("PG", "Procter & Gamble — consumer staples"),
    ("CL", "Colgate-Palmolive — consumer staples"),
    ("LULU", "Lululemon — consumer discretionary"),

    # ── Energy ──
    ("XOM", "Exxon Mobil — oil major"),
    ("CVX", "Chevron — oil major"),
    ("COP", "ConocoPhillips — oil & gas"),
    ("OXY", "Occidental Petroleum — Berkshire large stake"),
    ("SLB", "SLB (Schlumberger) — oilfield services"),
    ("ET", "Energy Transfer — MLP/partnership structure"),
    ("EPD", "Enterprise Products — MLP/partnership"),
    ("LNG", "Cheniere Energy — LNG export"),
    ("FANG", "Diamondback Energy — Permian Basin"),

    # ── Utilities ──
    ("NEE", "NextEra Energy — utility + renewables"),
    ("SO", "Southern Company — utility"),
    ("DUK", "Duke Energy — utility"),
    ("AEP", "American Electric Power — utility"),
    ("SRE", "Sempra — utility"),

    # ── Industrial / Manufacturing ──
    ("CAT", "Caterpillar — heavy equipment"),
    ("DE", "Deere & Company — agriculture equipment"),
    ("BA", "Boeing — aerospace/defense"),
    ("RTX", "RTX (Raytheon) — defense"),
    ("LMT", "Lockheed Martin — defense"),
    ("NOC", "Northrop Grumman — defense"),
    ("GD", "General Dynamics — defense"),
    ("EMR", "Emerson Electric — industrial automation"),
    ("ITW", "Illinois Tool Works — diversified industrial"),

    # ── REITs / Real Estate ──
    ("AMT", "American Tower — cell tower REIT"),
    ("PLD", "Prologis — industrial REIT"),
    ("SPG", "Simon Property — mall REIT"),
    ("O", "Realty Income — net lease REIT"),
    ("VICI", "Vici Properties — gaming REIT"),
    ("EQIX", "Equinix — data center REIT"),
    ("DLR", "Digital Realty — data center REIT"),
    ("WPC", "W.P. Carey — diversified REIT"),

    # ── SPACs / De-SPACs / Recent IPOs ──
    ("DJT", "Trump Media — de-SPAC, high-profile"),
    ("LCID", "Lucid Motors — de-SPAC, Saudi PIF backed"),
    ("JOBY", "Joby Aviation — de-SPAC"),
    ("DNA", "Ginkgo Bioworks — de-SPAC"),
    ("IONQ", "IonQ — de-SPAC, quantum computing"),
    ("HIMS", "Hims & Hers — de-SPAC, telehealth"),
    ("DKNG", "DraftKings — de-SPAC, gaming"),
    ("SOFI", "SoFi Technologies — de-SPAC, fintech"),
    ("ARM", "ARM Holdings — recent IPO, SoftBank subsidiary"),
    ("BIRK", "Birkenstock — recent IPO, PE-backed"),

    # ── Foreign Private Issuers (20-F, not DEF 14A — tests trail-end) ──
    ("SONY", "Sony — Japanese, 20-F filer"),
    ("TM", "Toyota — Japanese, 20-F filer"),
    ("NVO", "Novo Nordisk — Danish, 20-F filer"),
    ("SAP", "SAP — German, 20-F filer"),
    ("SHOP", "Shopify — Canadian, 20-F filer"),
    ("BABA", "Alibaba — Chinese VIE structure, 20-F"),
    ("TSM", "TSMC — Taiwanese, 20-F filer"),
    ("ASML", "ASML — Dutch, 20-F filer"),
    ("BP", "BP — British, 20-F filer"),
    ("SHEL", "Shell — British/Dutch, 20-F filer"),
    ("UL", "Unilever — British, 20-F filer"),
    ("RIO", "Rio Tinto — Australian/British, 20-F filer"),
    ("BHP", "BHP Group — Australian, 20-F filer"),

    # ── Dual/Multi-class Structures (beyond media) ──
    ("V", "Visa — post-IPO class structure"),
    ("MA", "Mastercard — post-IPO class structure"),
    ("ZM", "Zoom — dual-class, founder-controlled"),
    ("ABNB", "Airbnb — dual-class, founder-controlled"),
    ("COIN", "Coinbase — dual-class, crypto"),
    ("UBER", "Uber — dual-class"),
    ("LYFT", "Lyft — dual-class"),
    ("SQ", "Block (Square) — dual-class"),
    ("DOCU", "DocuSign — dual-class"),

    # ── Micro/Nano-cap (edge cases for parser) ──
    ("CUEN", "Cuentas — micro-cap, sparse filings"),
    ("PHUN", "Phunware — micro-cap, meme stock"),
    ("WKHS", "Workhorse — micro-cap EV"),
    ("SYTA", "Siyata Mobile — nano-cap"),
    ("AITX", "Artificial Intelligence Tech — micro-cap"),
]

# Strong signals: phrases that only appear in ownership table headers
HEADER_STRONG_SIGNALS = [
    "beneficially owned",
    "beneficial owner",
    "shares beneficially",
    "percent of class",
    "% of class",
    "percent of common stock",
    "shares of class",
    "voting power",
    "% vote of all classes",
    "% vote",
]

# Disqualifiers: tables that match keywords but aren't ownership data
DISQUALIFY_PATTERNS = [
    r"page\s*no",
    r"^\s*Q\.\s",
    r"table of contents",
    r"proxy solicited on behalf",
    r"items of business",
    r"proposal.*board.*recommend",
    r"compensation committee",
    r"proxy statement summary",
    r"vote required",
    r"effect of (broker|abstention)",
    r"change of control",
    r"change in the composition",
    r"reorganization.*merger",
    r"approval by the shareholders",
    r"limitations on awards",
    r"the \d{4} equity plan",
    r"what constitutes a quorum",
    r"who bears the cost",
    r"a message from",
    r"shareholder proposal",
]


def has_numeric_data(df, min_numeric_cells=3):
    count = 0
    for col in df.columns:
        for val in df[col]:
            s = str(val).replace(",", "").replace("%", "").replace("*", "").strip()
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
    text = text.replace("\xa0", " ").replace(" ", " ")
    return text


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


def check_text_fallback(proxy):
    """Detect ownership data in plain-text tables (no HTML <table> tags)."""
    text = proxy._filing_text
    pattern = r"(?i)security ownership of certain beneficial owners"
    match = re.search(pattern, text)
    if not match:
        return None

    # Grab the section (up to next major heading or 3000 chars)
    start = match.start()
    section = text[start:start + 3000]
    # Look for tabular structure: lines with multiple number-like values
    lines_with_numbers = 0
    for line in section.split("\n"):
        nums = re.findall(r"[\d,]{3,}", line)
        if len(nums) >= 2:
            lines_with_numbers += 1
    if lines_with_numbers >= 3:
        return section
    return None


def survey_proxy(ticker, label):
    result = {"ticker": ticker, "label": label, "status": None,
              "filing_date": None, "total_tables": 0, "ownership_tables": 0,
              "total_data_rows": 0, "text_fallback": False, "error": None}

    try:
        company = Company(ticker)
    except Exception as e:
        result["status"] = "no_company"
        result["error"] = str(e)[:120]
        return result

    try:
        filing = company.get_filings(form="DEF 14A").latest()
        proxy = filing.obj()
    except Exception as e:
        result["status"] = "no_filing"
        result["error"] = str(e)[:120]
        return result

    result["filing_date"] = str(proxy.filing_date)
    html = re.sub(r"<\?xml[^>]+\?>", "", proxy._filing_html)

    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as e:
        result["status"] = "parse_error"
        result["error"] = str(e)[:120]
        return result

    result["total_tables"] = len(tables)

    matches = []
    for i, t in enumerate(tables):
        t_clean = t.dropna(how="all")
        if is_ownership_table(t_clean):
            matches.append((i, t_clean))

    result["ownership_tables"] = len(matches)
    result["total_data_rows"] = sum(max(0, len(t) - 1) for _, t in matches)

    if len(matches) > 0:
        result["status"] = "ok"
    else:
        text_table = check_text_fallback(proxy)
        if text_table:
            result["status"] = "text_fallback"
            result["text_fallback"] = True
        else:
            result["status"] = "no_ownership_tables"

    return result


results = []
total = len(COMPANIES)
for idx, (ticker, label) in enumerate(COMPANIES, 1):
    print(f"  [{idx}/{total}] {ticker}...", end=" ", flush=True)
    r = survey_proxy(ticker, label)
    results.append(r)
    print(r["status"])

df = pd.DataFrame(results)

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"\nStatus counts:")
print(df["status"].value_counts().to_string())
print(f"\nTotal companies: {len(df)}")
print(f"Ownership tables found: {df['ownership_tables'].sum()}")
print(f"Total data rows: {df['total_data_rows'].sum()}")

failures = df[~df["status"].isin(["ok", "no_filing", "no_company"])]
if len(failures) > 0:
    print(f"\n--- Needs investigation ({len(failures)}) ---")
    print(failures[["ticker", "label", "status", "error"]].to_string(index=False))

no_tables = df[df["status"] == "no_ownership_tables"]
if len(no_tables) > 0:
    print(f"\n--- Has DEF 14A but no ownership tables ({len(no_tables)}) ---")
    print(no_tables[["ticker", "label", "total_tables"]].to_string(index=False))

print(f"\n--- No filing (expected for foreign issuers etc.) ({len(df[df['status'].isin(['no_filing', 'no_company'])])}) ---")
no_filing = df[df["status"].isin(["no_filing", "no_company"])]
if len(no_filing) > 0:
    print(no_filing[["ticker", "label", "error"]].to_string(index=False))
