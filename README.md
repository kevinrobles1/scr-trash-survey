# Santa Cruz River Trash Survey Dashboard

**Sonoran Institute — River Restoration Program**  
Live URL: https://scr-trash-survey-j7ktw57hzwcxnlchvv7zax.streamlit.app  
GitHub: github.com/kevinrobles1/scr-trash-survey  
Version: 5.0 · Cloud Edition  

---

## What This Is

A cloud-hosted, real-time web dashboard for the Sonoran Institute's longitudinal trash survey program along the Santa Cruz River corridor in Tucson, Arizona. Previously stored entirely in a local Excel workbook, the full dataset is now in a Supabase cloud database accessible by the entire team from any device via a shared URL.

The dashboard covers 32,144+ recorded items across 395+ survey events, 136 unique locations, 19 trash categories, and 56 individual item types — spanning September 2020 to present.

---

## File Structure

```
app.py                    ← Main Streamlit application (single file, ~3,000 lines)
migrate_plastic_bags.py   ← One-time migration script for Plastic Bags category
diagnose_supabase.py      ← Diagnostic script to verify database contents
README.md                 ← This file
```

---

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend / App | Streamlit (Python) |
| Database | Supabase (PostgreSQL via PostgREST) |
| Hosting | Streamlit Cloud |
| Charts | Plotly Express + Plotly Graph Objects |
| Maps | Leaflet.js (via components.html) |
| Auth | Custom — bcrypt-style hash in Supabase `users` table |
| Fonts | Cormorant Garamond · DM Sans · DM Mono (Google Fonts) |

---

## Supabase Database

**Project URL:** `https://zjnybcfzunhgyhcyuhon.supabase.co`

### Tables

#### `trash_counts`
One row per item per survey event. ~8,963 rows.

| Column | Type | Notes |
|---|---|---|
| `event_id` | integer | Foreign key to site_events |
| `trash_group` | text | One of 19 category names |
| `trash_item` | text | One of 56 item names |
| `count_value` | float | Number of items found |

#### `site_events`
One row per survey event. ~395 rows.

| Column | Type | Notes |
|---|---|---|
| `event_id` | integer | Primary key |
| `date_site` | date | Survey date |
| `site_label` | text | Location name |
| `location_description` | text | Detailed description |
| `recorder` | text | Person who conducted survey |
| `surveyed_m2` | float | Plot area in square meters |
| `submitted_by` | text | Account name who entered data (new entries) |

#### `weights_data`
Optional weight measurements.

| Column | Type |
|---|---|
| `event_id` | integer |
| `date_recorded` | date |
| `total_weight_oz` | float |

#### `users`
Authentication table.

| Column | Type |
|---|---|
| `user_id` | uuid (auto) |
| `username` | text (unique) |
| `full_name` | text |
| `position_title` | text |
| `password_hash` | text |
| `salt` | text |
| `security_question` | text |
| `security_answer_hash` | text |
| `security_answer_salt` | text |

> **Important:** The `submitted_by` column in `site_events` must be added manually if it does not exist. Run this in the Supabase SQL editor:
> ```sql
> ALTER TABLE site_events ADD COLUMN IF NOT EXISTS submitted_by text;
> ```

### Critical: Row Limit

Supabase PostgREST returns at most 1,000 rows by default. The app uses **paginated fetching** (`fetch_all()` with `.range()`) to retrieve all rows. Never use `.execute()` alone on large tables — it silently truncates data.

---

## Local Development

### Requirements

```
streamlit
supabase
pandas
numpy
plotly
openpyxl
```

Install:
```bash
pip install streamlit supabase pandas numpy plotly openpyxl
```

### Secrets

Create `.streamlit/secrets.toml` locally:
```toml
SUPABASE_URL = "https://zjnybcfzunhgyhcyuhon.supabase.co"
SUPABASE_KEY = "your_service_role_key_here"
```

On Streamlit Cloud, add these same keys under **App Settings → Secrets**.

### Run Locally

```bash
streamlit run app.py
```

---

## Deploying to Streamlit Cloud

1. Push `app.py` to the `main` branch of `github.com/kevinrobles1/scr-trash-survey`
2. Go to https://share.streamlit.io
3. Select the repo, branch `main`, file `app.py`
4. Add secrets under App Settings
5. Click **Deploy** — or **Reboot app** if already deployed

> After every push, Streamlit Cloud automatically redeploys. If charts show stale data, use **Manage App → Reboot app** to force a cache clear.

---

## Data Pipeline

### Original Source

`Trash_database.xlsx` — two sheets used:

- **`Data`** — rows 1-2 are headers (group name / item name), row 3 is blank, rows 4+ are data. Columns: Event ID, Date, Surveyed M², then 53 item count columns organized under 19 group headers.
- **`Site`** — one row per event with GPS coordinates (`N decimal`, `W decimal`), recorder, location description, and metadata.

### Migration

The original migration script inserted all non-zero counts from `Data` into `trash_counts`, and all site metadata into `site_events`. **Plastic Bags** (Excel column 3) had no group header row and was not migrated in the original run. Use `migrate_plastic_bags.py` to add the 358 missing rows (3,649 items).

### Known Coordinate Corrections

These are hardcoded in `load_data()` at runtime:

| Event | Field | Wrong | Correct | Reason |
|---|---|---|---|---|
| 20, 187, 188, 189 | lat & lon | 0.0 | null | No GPS recorded |
| 78 | lon | -111.990556 | -110.990556 | Off by 1 degree |
| 249 | lat | 32.345760 | 32.245760 | Off by 0.1 degree |
| 197 | lon | -110.963360 | -110.985360 | Typo |
| 334 | lat | 32.110259 | 32.210259 | Off by 0.1 degree |

---

## Application Architecture

### Authentication

- Staff sign in with username + password (hashed with SHA-256 + random salt stored in Supabase)
- Password reset via 3-step security question flow (no email required)
- Username lookup by full name + security answer
- **Volunteers** skip login entirely — enter name, org, experience level, contact info via the "Volunteer Entry" tab. They access Data Entry only (no Manage/Delete).

### Data Loading (`load_data`)

Decorated with `@st.cache_data(ttl=300)` — cached for 5 minutes. Uses paginated fetch to bypass the 1,000-row Supabase limit. After fetching:

1. Strips phantom rows (Event ID / Date / Surveyed M² accidentally stored as trash items)
2. Remaps Plastic Bags from `NULL` or `Ungrouped` group to `"Plastic Bags"`
3. Corrects known bad GPS coordinates
4. Merges `site_events` GPS and metadata onto `trash_counts` to produce the `long` dataframe

### Pages

| Page | Key Features |
|---|---|
| **Overview** | KPI strip, monthly time series with rolling average, category donut, top 15 items, segment stacked bar |
| **Map** | Leaflet map — 3 modes: by segment, by burden (color gradient), individual events. Corrected GPS coordinates. |
| **Trends** | 6 selectable figures: monthly, annual, month-by-month, avg per event, quarterly by segment, weight over time |
| **Categories** | 21 selectable figures across 5 groups. Interactive category toggle (include/exclude groups). Color legend on every figure. |
| **Locations** | 4 tabs: N→S mean with SE error bars, variability (SD/CV/Range), segment comparison, full stats table. Plain-language stats explainer. |
| **Data Table** | Wide format (Excel-like pivot: 1 row per event, 56 item columns) + Long format. Filters: segment, location, category, date. |
| **Data Entry** | Staff: 2-step form with review panel before submit. Volunteer: same form, no manage tab. "Added By" tracked per entry. |
| **Export** | 3 CSV formats: Long (raw), Event Totals, Site Summary |
| **About** | Program narrative, photos, stats, methodology, 6 reason cards, team cards, contact |

### Environmental Classifications

Used to color-code categories across all charts:

| Color | Classification | Categories |
|---|---|---|
| Blue | Recyclable (City of Tucson) | Beer, Liquor, Soda, Water, Sports Drinks, Juice, Paper Litter |
| Red | Health Hazard | Rx/Drugs, Nicotine, Toiletries |
| Amber | Floatable (river health / ADEQ risk) | Plastic Bags, Cups, Soda, Water, Sports Drinks, Juice, Food Packaging, Paper Litter |
| Green | Other Non-Recyclable | All remaining categories |

---

## Known Issues & Pending Items

| Item | Status | Notes |
|---|---|---|
| Plastic Bags migration | **Pending** | Run `migrate_plastic_bags.py` locally to add 3,649 items |
| `submitted_by` column | **Pending** | May need `ALTER TABLE site_events ADD COLUMN submitted_by text` in Supabase |
| Some category charts | **In review** | Statistical accuracy being validated — some figures may need axis or chart type adjustment |
| Summer gap (Jun–Aug) | **Documented** | Gray bars = no survey, not no trash. Noted on all monthly charts. |
| Nav bar | **Working** | Uses CSS-styled `st.radio` — iframe/postMessage approach was removed (blocked by Streamlit Cloud) |

---

## Design System

| Token | Value |
|---|---|
| Forest (darkest) | `#13291a` |
| Green (header) | `#1e4d1e` |
| Sage | `#2d6a2d` |
| Mint (accent) | `#5da832` |
| Cream (background) | `#faf7f0` |
| Sand | `#f2ede2` |
| Amber | `#e8a620` |
| Brick (red) | `#b5451b` |
| Body font | DM Sans |
| Title font | Cormorant Garamond |
| Mono / labels | DM Mono |
| Body padding | 36px top · 96px right · 100px bottom · 124px left |

---

## Team

| Name | Role |
|---|---|
| Luke Cole | Program Director, Santa Cruz River Restoration Program |
| Kevin Robles | Database Specialist · RISE Intern — Dashboard development & data migration |
| Sofia Angkasa, Kimberly Stanley, Marie Olson | Field Survey Team |

**Sonoran Institute**  
5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711 · (520) 290-0828  
https://sonoraninstitute.org/card/santacruz/

---

*Dashboard v5.0 · Cloud Edition · Last updated March 2026*
