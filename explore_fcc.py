# explore_fcc.py
# Your first pipeline script.
# This reads the FCC LMS data files and shows you what's in them.
#
# Before running this, install DuckDB:
#   pip install duckdb
#
# Then run:
#   python explore_fcc.py
#
# Change the DATA_DIR path below to wherever you extracted Current_LMS_Dump.zip

import duckdb

# ── CHANGE THIS to your actual path ──────────────────────────────────
DATA_DIR = r"unfiltered_data/Current_LMS_Dump"
# On Windows, use raw strings (the r"..." prefix) so backslashes work.
# Example: r"C:\Users\YourName\Downloads\LMS_Dump"
# ─────────────────────────────────────────────────────────────────────

# Connect to DuckDB (in-memory — no database file created)
db = duckdb.connect()

# ── Step 1: Read the facility table ──────────────────────────────────
# This tells DuckDB: read this pipe-delimited file, first row is headers,
# and ignore the trailing ^| column.
print("=" * 60)
print("STEP 1: How many broadcast stations are in the database?")
print("=" * 60)

# First, create a view so we can query the file like a SQL table.
# The settings: pipe delimiter, first row = header names, ignore errors
# on malformed rows.
db.execute(f"""
    CREATE VIEW facility AS
    SELECT * FROM read_csv(
        '{DATA_DIR}/facility.dat',
        delim = '|',
        header = true,
        ignore_errors = true
    )
""")

# Count all stations
total = db.execute("SELECT COUNT(*) FROM facility").fetchone()[0]
print(f"\nTotal stations in database: {total:,}")

# Count by service type (TV, FM, AM, etc.)
print("\nStations by service type:")
rows = db.execute("""
    SELECT service_code, COUNT(*) as station_count
    FROM facility
    GROUP BY service_code
    ORDER BY station_count DESC
""").fetchall()

for service, count in rows:
    print(f"  {service or 'NULL':6s}  {count:,}")

# ── Step 2: Look at licensed TV stations only ────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Licensed full-power TV stations")
print("=" * 60)

# DTV = Digital TV (full power). LICEN = Licensed (active).
rows = db.execute("""
    SELECT callsign, community_served_city, community_served_state,
           channel, network_affiliation, facility_id
    FROM facility
    WHERE service_code = 'DTV'
      AND facility_status = 'LICEN'
    ORDER BY community_served_state, community_served_city
    LIMIT 20
""").fetchall()

print(f"\nFirst 20 licensed digital TV stations:\n")
print(f"  {'CALL':8s} {'CITY':20s} {'ST':4s} {'CH':4s} {'NETWORK':10s} {'FAC_ID'}")
print(f"  {'─'*8} {'─'*20} {'─'*4} {'─'*4} {'─'*10} {'─'*10}")
for row in rows:
    call, city, state, ch, net, fac_id = [str(x) if x is not None else '' for x in row]
    print(f"  {call:8s} {city:20s} {state:4s} {ch:4s} {net:10s} {fac_id}")

# ── Step 3: Which networks have the most stations? ───────────────────
print("\n" + "=" * 60)
print("STEP 3: Network affiliations (licensed TV stations)")
print("=" * 60)

rows = db.execute("""
    SELECT network_affiliation, COUNT(*) as station_count
    FROM facility
    WHERE service_code = 'DTV'
      AND facility_status = 'LICEN'
      AND network_affiliation IS NOT NULL
      AND network_affiliation != ''
    GROUP BY network_affiliation
    ORDER BY station_count DESC
    LIMIT 15
""").fetchall()

print(f"\n  {'NETWORK':15s} {'STATIONS':>10s}")
print(f"  {'─'*15} {'─'*10}")
for net, count in rows:
    print(f"  {net:15s} {count:>10,}")

# ── Step 4: Now connect to ownership data ────────────────────────────
print("\n" + "=" * 60)
print("STEP 4: Connecting stations to their owners")
print("=" * 60)

# Load the other tables we need
db.execute(f"""
    CREATE VIEW ownership_stations AS
    SELECT * FROM read_csv(
        '{DATA_DIR}/ownership_reports_stations.dat',
        delim = '|',
        header = true,
        ignore_errors = true
    )
""")

db.execute(f"""
    CREATE VIEW ownership_applications AS
    SELECT * FROM read_csv(
        '{DATA_DIR}/ownership_reports_application.dat',
        delim = '|',
        header = true,
        ignore_errors = true,
        strict_mode = false,
        all_varchar = true
    )
""")

db.execute(f"""
    CREATE VIEW ownership_interest AS
    SELECT * FROM read_csv(
        '{DATA_DIR}/ownership_reports_ownership_interest.dat',
        delim = '|',
        header = true,
        ignore_errors = true,
        strict_mode = false,
        all_varchar = true
    )
""")

# Now do the full join: pick a well-known station and trace its ownership.
# Let's try to find NBC, ABC, CBS, and Fox flagship stations.
print("\nLooking for major network flagship stations...\n")

flagships = db.execute("""
    SELECT callsign, community_served_city, community_served_state,
           network_affiliation, facility_id
    FROM facility
    WHERE service_code = 'DTV'
      AND facility_status = 'LICEN'
      AND callsign IN ('WNBC', 'WABC', 'WCBS', 'WNYW', 'KNBC', 'KABC')
    ORDER BY callsign
""").fetchall()

for call, city, state, net, fac_id in flagships:
    print(f"\n  Station: {call} ({city}, {state}) — Network: {net}")
    print(f"  Facility ID: {fac_id}")

    # Find the MOST RECENT ownership filing for this station
    filing = db.execute(f"""
        SELECT os.application_id, oa.legal_title_or_name,
               oa.as_of_date, os.licensee_permittee_name
        FROM ownership_stations os
        JOIN ownership_applications oa
          ON os.application_id = oa.application_id
        WHERE os.facility_id = '{fac_id}'
        ORDER BY oa.as_of_date DESC
        LIMIT 1
    """).fetchone()

    if filing:
        app_id, licensee, as_of, permittee = filing
        # Show the licensee name — try multiple fields since some are empty
        licensee_display = permittee or licensee or '(unknown)'
        print(f"  Licensee: {licensee_display}")
        print(f"  Filing date: {as_of}")

        # Find the interest holders for this filing
        # Key fix: use first_name + last_name for people,
        # company_name for entities (from the schema doc)
        holders = db.execute(f"""
            SELECT
                CASE
                    WHEN individual_entity_ind = 'I'
                    THEN COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')
                    ELSE COALESCE(company_name, last_name, '(unnamed)')
                END AS holder_name,
                voting,
                equity,
                pi_officer_ind,
                pi_director_ind,
                pi_stockholder_ind,
                pi_parent_entity_ind,
                individual_entity_ind,
                listing_type
            FROM ownership_interest
            WHERE application_id = '{app_id}'
            ORDER BY
                CASE WHEN listing_type = 'R' THEN 0 ELSE 1 END,
                TRY_CAST(voting AS FLOAT) DESC NULLS LAST
            LIMIT 15
        """).fetchall()

        if holders:
            print(f"\n  {'NAME':35s} {'VOTE%':>7s} {'EQUITY%':>8s} {'TYPE':8s} {'ROLE'}")
            print(f"  {'─'*35} {'─'*7} {'─'*8} {'─'*8} {'─'*25}")
            for h in holders:
                name, vote, eq, officer, director, stock, parent, ind_ent, listing = h

                # Build role string from the pi_ flags
                roles = []
                if officer == 'Y': roles.append('Officer')
                if director == 'Y': roles.append('Director')
                if stock == 'Y': roles.append('Stockholder')
                if parent == 'Y': roles.append('Parent Entity')
                role_str = ', '.join(roles) if roles else ''

                # Entity type
                if listing == 'R':
                    etype = 'Resp'  # Respondent (the licensee itself)
                elif ind_ent == 'I':
                    etype = 'Person'
                else:
                    etype = 'Entity'

                # Parse vote/equity percentages safely
                try:
                    vote_f = float(vote) if vote else 0.0
                except (ValueError, TypeError):
                    vote_f = 0.0
                try:
                    eq_f = float(eq) if eq else 0.0
                except (ValueError, TypeError):
                    eq_f = 0.0

                name_display = str(name or '(unnamed)').strip()[:35]
                print(f"  {name_display:35s} {vote_f:>7.1f} {eq_f:>8.1f} {etype:8s} {role_str}")
        else:
            print("  No interest holders found")
    else:
        print("  No ownership filing found for this station")

# ── Step 5: Largest station groups by number of stations ─────────────
print("\n\n" + "=" * 60)
print("STEP 5: Largest station groups by number of stations")
print("=" * 60)

# This counts how many stations each ownership interest ENTITY controls.
# We filter to parent entities and entities with significant voting interest
# to avoid counting every individual officer/director.
rows = db.execute("""
    SELECT
        COALESCE(oi.company_name, oi.last_name) AS entity_name,
        COUNT(DISTINCT os.facility_id) as stations
    FROM ownership_stations os
    JOIN ownership_interest oi
      ON os.application_id = oi.application_id
    WHERE oi.individual_entity_ind != 'I'
      AND COALESCE(oi.company_name, oi.last_name) IS NOT NULL
      AND COALESCE(oi.company_name, oi.last_name) != ''
      AND TRY_CAST(oi.voting AS FLOAT) > 0
    GROUP BY entity_name
    ORDER BY stations DESC
    LIMIT 20
""").fetchall()

print(f"\n  {'ENTITY NAME':50s} {'STATIONS':>10s}")
print(f"  {'─'*50} {'─'*10}")
for name, count in rows:
    print(f"  {str(name)[:50]:50s} {count:>10,}")

print("\n\nDone! You just queried the entire FCC broadcast database.")
print("This is the same data your pipeline will transform into the ownership graph.")