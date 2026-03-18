"""
migrate_to_supabase.py
======================
Run this ONCE on your local computer to load your Excel data into Supabase.
You never need to run this again unless you reset the database.

BEFORE RUNNING:
  pip install supabase pandas openpyxl

HOW TO RUN:
  1. Fill in SUPABASE_URL and SUPABASE_KEY below (from your Supabase project settings)
  2. Set EXCEL_PATH to the path of your "Trash database.xlsx" file
  3. Open a terminal and run:   python migrate_to_supabase.py
"""

import re
import pandas as pd
import numpy as np
from supabase import create_client

# ──────────────────────────────────────────────
# FILL THESE IN BEFORE RUNNING
# ──────────────────────────────────────────────
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"    # from Supabase → Settings → API
SUPABASE_KEY = "YOUR_SERVICE_ROLE_KEY"                  # from Supabase → Settings → API (service_role, not anon)
EXCEL_PATH   = r"C:\Users\roble\OneDrive\Documents\Sonoran Institute\Data\Trash database.xlsx"
MIN_EVENT_ID = 1   # include all events; set to 209 if you only want replicate-era data
# ──────────────────────────────────────────────

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

KNOWN_BAD_POINT_IDS = {"2023-04-05|32.34576,-110.99314"}

def parse_yymmdd(x):
    if pd.isna(x): return None
    if isinstance(x, pd.Timestamp): return x.date().isoformat() if not pd.isna(x) else None
    s = str(x).strip()
    if s == "": return None
    try:
        s2 = str(int(float(s)))
    except Exception:
        return None
    if len(s2) == 6:
        dt = pd.to_datetime(s2, format="%y%m%d", errors="coerce")
    elif len(s2) == 8:
        dt = pd.to_datetime(s2, format="%Y%m%d", errors="coerce")
    else:
        dt = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(dt) else dt.date().isoformat()

def safe_float(x):
    try: v = float(x); return None if np.isnan(v) else v
    except: return None

def safe_int(x):
    try: v = int(float(x)); return v
    except: return None

def parse_coord(x):
    if pd.isna(x): return None
    try: v = float(x); return None if (np.isnan(v) or abs(v) < 1e-10) else v
    except: return None

def pretty(x):
    if pd.isna(x): return ""
    s = str(x).strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if s.lower() == "ppe": return "PPE"
    return s.title()

def chunk_insert(table, rows, chunk_size=500):
    """Insert rows in batches to avoid Supabase request limits."""
    for i in range(0, len(rows), chunk_size):
        batch = rows[i:i+chunk_size]
        sb.table(table).insert(batch).execute()
        print(f"  → inserted rows {i+1}–{min(i+chunk_size, len(rows))}")

# ──────────────────────────────────────────────
# 1. MIGRATE SITE SHEET
# ──────────────────────────────────────────────
print("\n=== Migrating Site sheet ===")
xls = pd.ExcelFile(EXCEL_PATH)

if "Site" in xls.sheet_names:
    site = pd.read_excel(EXCEL_PATH, sheet_name="Site")

    # Normalize column names
    site.columns = [str(c).strip() for c in site.columns]

    def fc(candidates):
        for c in candidates:
            if c in site.columns: return c
        return None

    event_col  = fc(["Event ID", "event_id", "EventID"])
    date_col   = fc(["Date", "date"])
    rand_col   = fc(["Rand_site code", "Rand site code", "Rand_site_code", "Point ID"])
    loc_col    = fc(["Location description", "Location", "Site"])
    lat_col    = fc(["N decimal", "Northing decimal", "Latitude", "Lat"])
    lon_col    = fc(["W decimal", "Westing decimal", "Longitude", "Lon"])
    rep_col    = fc(["Repeat #", "Repeat", "Replicate #", "Rep"])
    rec_col    = fc(["Recorder", "recorder"])
    area_col   = fc(["Transect width (m)", "Plot area (m2)", "surveyed_m2"])
    comp_col   = fc(["Complete?", "complete"])

    rows = []
    for _, r in site.iterrows():
        eid = safe_int(r.get(event_col)) if event_col else None
        if eid is None or eid < MIN_EVENT_ID: continue
        lat = parse_coord(r.get(lat_col)) if lat_col else None
        lon = parse_coord(r.get(lon_col)) if lon_col else None
        rand = str(r.get(rand_col, "")).strip() if rand_col else ""
        loc  = str(r.get(loc_col,  "")).strip() if loc_col  else ""
        label = rand if rand not in ("", "nan") else loc
        rows.append({
            "event_id":             eid,
            "date_site":            parse_yymmdd(r.get(date_col)) if date_col else None,
            "rand_site_code":       rand if rand not in ("", "nan") else None,
            "location_description": loc  if loc  not in ("", "nan") else None,
            "site_label":           label if label not in ("", "nan") else None,
            "point_id":             rand if rand not in ("", "nan") else None,
            "replicate_no":         safe_int(r.get(rep_col)) if rep_col else None,
            "lat":                  lat,
            "lon":                  lon,
            "recorder":             str(r.get(rec_col, "")).strip() if rec_col else None,
            "surveyed_m2":          safe_float(r.get(area_col)) if area_col else None,
            "complete":             str(r.get(comp_col, "")).strip().lower() if comp_col else None,
        })

    if rows:
        # Delete existing and re-insert
        sb.table("site_events").delete().gte("event_id", MIN_EVENT_ID).execute()
        chunk_insert("site_events", rows)
        print(f"✓ Migrated {len(rows)} site events")
    else:
        print("! No site rows found")
else:
    print("! No Site sheet found — skipping")

# ──────────────────────────────────────────────
# 2. MIGRATE DATA SHEET (wide → long)
# ──────────────────────────────────────────────
print("\n=== Migrating Data sheet ===")
raw = pd.read_excel(EXCEL_PATH, sheet_name="Data", header=None)

group_row  = raw.iloc[0].tolist()
item_row   = raw.iloc[1].tolist()
group_fill = pd.Series(group_row).ffill().tolist()
for i in range(3): group_fill[i] = None

df_wide = raw.iloc[3:].copy()
df_wide = df_wide.rename(columns={0: "event_id", 1: "date_raw", 2: "surveyed_m2"})
df_wide["event_id"] = pd.to_numeric(df_wide["event_id"], errors="coerce")
df_wide = df_wide[df_wide["event_id"].notna() & (df_wide["event_id"] >= MIN_EVENT_ID)].copy()

# Delete existing trash counts
sb.table("trash_counts").delete().gte("event_id", MIN_EVENT_ID).execute()

rows = []
item_cols = list(range(3, min(61, len(item_row))))
for c in item_cols:
    g = group_fill[c] if c < len(group_fill) else None
    it = item_row[c]  if c < len(item_row)  else None
    if pd.isna(g) and pd.isna(it): continue
    grp = "Misc" if (pd.isna(g) or str(g).lower().startswith("unnamed")) else str(g).strip()
    itm = str(it).strip() if not pd.isna(it) else f"col_{c}"
    if itm in ["Complete?", "Total items", "Total items/m2"]: continue

    counts = pd.to_numeric(df_wide[c] if c in df_wide.columns else pd.Series(), errors="coerce")
    for idx, eid in enumerate(df_wide["event_id"].values):
        val = counts.iloc[idx] if idx < len(counts) else np.nan
        if pd.isna(val) or val <= 0: continue
        rows.append({
            "event_id":   int(eid),
            "trash_group": pretty(grp),
            "trash_item":  pretty(itm),
            "count_value": float(val),
        })

if rows:
    chunk_insert("trash_counts", rows)
    print(f"✓ Migrated {len(rows)} non-zero trash count rows")
else:
    print("! No trash count rows found")

# ──────────────────────────────────────────────
# 3. MIGRATE WEIGHTS SHEET
# ──────────────────────────────────────────────
print("\n=== Migrating Weights sheet ===")
if "Weights" in xls.sheet_names:
    wraw = pd.read_excel(EXCEL_PATH, sheet_name="Weights", header=None)
    if wraw.shape[0] >= 3:
        hdr = wraw.iloc[1].tolist()
        def wfc(t):
            for i, v in enumerate(hdr):
                if not pd.isna(v) and t.lower() in str(v).lower(): return i
            return None
        ec = wfc("event id"); dc = wfc("date"); tc = wfc("total weight")
        if ec is not None and tc is not None:
            wdf = wraw.iloc[3:].copy()
            wdf["event_id"]   = pd.to_numeric(wdf[ec], errors="coerce")
            wdf["weight_oz"]  = pd.to_numeric(wdf[tc], errors="coerce")
            wdf["date_rec"]   = wdf[dc].apply(parse_yymmdd) if dc else None
            wdf = wdf[wdf["event_id"].notna() & wdf["weight_oz"].notna()].copy()
            sb.table("weights_data").delete().gte("event_id", MIN_EVENT_ID).execute()
            wrows = []
            for _, r in wdf.iterrows():
                wrows.append({
                    "event_id":        int(r["event_id"]),
                    "date_recorded":   r["date_rec"],
                    "total_weight_oz": float(r["weight_oz"]),
                })
            if wrows:
                chunk_insert("weights_data", wrows)
                print(f"✓ Migrated {len(wrows)} weight records")
        else:
            print("! Could not find Event ID or weight column in Weights sheet")
    else:
        print("! Weights sheet too small to parse")
else:
    print("! No Weights sheet found — skipping")

print("\n✅ Migration complete! Your Supabase database is now loaded.")
print("   You can now deploy app.py to Streamlit Community Cloud.")
