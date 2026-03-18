# streamlit run app.py
# ─────────────────────────────────────────────────────────────
# Santa Cruz River Trash Survey Dashboard
# Sonoran Institute — River Restoration Program
# Cloud version: data stored in Supabase (PostgreSQL)
# ─────────────────────────────────────────────────────────────
import os
import re
import json
import html
import hashlib
import secrets
from datetime import datetime, date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

# ─────────────────────────────────────────────────────────────
# SUPABASE CONNECTION
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
LOGO_URL   = "https://sonoraninstitute.org/wp-content/themes/sonoran-institute-2016/assets/img/si_logo_2018.png"
LOGO_WHITE = "https://sonoraninstitute.org/wp-content/themes/sonoran-institute-2016/assets/img/si_logo_white_2018.png"

KNOWN_BAD_IDS = {"2023-04-05|32.34576,-110.99314"}

TRASH_GROUPS = {
    "Cups": ["Styrofoam (Polar Pop)", "Styrofoam (Qt)", "Styrofoam (other)", "Plastic", "Paper"],
    "Beer": ["Bottles", "Cans"],
    "Liquor": ["Plastic bottles", "Glass"],
    "Soda": ["Bottles", "Cans"],
    "Water": ["Bottles"],
    "Sports drinks": ["Bottles", "Cans"],
    "Juice": ["Bottles", "Cans"],
    "Food packaging": [
        "Food wrappers (candy, etc.)", "Non-cup styrofoam", "Non-cup plastic",
        "Non-cup paper (bags, boxes)", "Straws", "6-pack rings",
        "Plates and bowls plastic", "Cans, milk jugs, mixes",
        "Plates, styrofoam", "Utensils", "Misc"
    ],
    "Nicotine": ["cigs, cigars, lighters, dip, packs"],
    "Toiletries": ["Toiletries", "Packaging"],
    "Rx, drugs": ["Rx and drug packaging", "Syringes, paraphernalia"],
    "Toys, games": ["Balls, games", "CD, DVD, electronic packaging",
                    "School/office supplies", "ID cards, credit cards", "Batteries"],
    "Paper litter": ["News, books, magazines", "Advertising, signs, cards"],
    "Clothing": ["Clothes, shoes, hats", "PPE", "Misc. fabric"],
    "Auto": ["Car parts (small)", "Car parts (large)", "Tires"],
    "Construction": ["Small items", "Large items"],
    "Appliances": ["Bikes, bike parts", "Furniture/cushions/pillows",
                   "Shopping carts", "Carpet", "Rope/line",
                   "Buckets", "Appliances"],
    "Plastic bags": ["Plastic bags"],
    "Misc": ["Sm. debris (ex. metal, plastic scraps)", "Lg. debris (ex. garbage cans)"],
}

SANTA_CRUZ_SITES = [
    "Santa Cruz River North of CoCerro",
    "W side of Cushing St. bridge, north of the bridge at outfall",
    "Midway between Cushing and Congress, southern site",
    "Midway between Cushing and Congress, northern site",
    "outfall CW Cushing, North side",
    "South of Trail's end wash",
    "South of Speedway (St. Mary's) (West)",
    "Speedway and St. Mary",
    "Santa Cruz river, Drexel and Irvington",
    "Between an outfall and Camino del Cerro",
    "Santa Cruz River at Camino del Cerro",
    "Silverlake Bridge on Santa Cruz",
    "Rillito at Country Club",
    "Arcadia wash",
]

TEAM_MEMBERS = [
    "Luke Cole", "Sofia Angkasa", "Kimberly Stanley", "Marie Olson",
    "S. Griset", "Soroush Hedayah", "Vata Aflatoone", "Kimberly Baeza",
    "Joan Woodward", "Mark Krieski", "Jamie Irby", "Marsha Colbert",
    "Axhel Munoz", "Christine Hehenga",
]

st.set_page_config(
    page_title="Santa Cruz River Trash Survey — Sonoran Institute",
    page_icon=LOGO_URL,
    layout="wide",
    initial_sidebar_state="collapsed",
)

PLOTLY_CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}

# ─────────────────────────────────────────────────────────────
# DESIGN SYSTEM
# ─────────────────────────────────────────────────────────────
SI_GREEN      = "#2d5016"
SI_GREEN_MED  = "#4a7c2e"
SI_GREEN_SOFT = "#e8f0e0"
SI_BLUE       = "#1a5276"
SI_SAND       = "#f5f0e8"
SI_SAND_DARK  = "#ddd4c0"
TEXT_DARK     = "#1a1a1a"
TEXT_MED      = "#3d3d3d"
TEXT_MUTED    = "#6b6b6b"
DIVIDER       = "#d4ccc0"
PALETTE = [SI_GREEN, SI_BLUE, "#c0622f", "#e8a44a", "#7b4fa0", "#4ec9b0", "#d64541", "#888"]

GF = "https://fonts.googleapis.com/css2?family=Merriweather:wght@300;400;700&family=Source+Sans+3:wght@300;400;500;600;700&display=swap"

def inject_css():
    st.markdown(f'<link href="{GF}" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown(f"""
    <style>
    html, body, [class*="css"] {{ font-family: 'Source Sans 3', sans-serif; color: {TEXT_DARK}; }}
    .stApp {{ background: {SI_SAND}; }}
    [data-testid="stSidebar"] {{ display: none !important; }}
    [data-testid="collapsedControl"] {{ display: none !important; }}
    .block-container {{ padding: 0 !important; max-width: 100% !important; }}
    .si-header {{ background: {SI_GREEN}; border-bottom: 3px solid {SI_GREEN_MED}; }}
    .si-header-inner {{ max-width: 1300px; margin: 0 auto; padding: 14px 36px; display: flex; align-items: center; justify-content: space-between; }}
    .si-logo {{ height: 40px; width: auto; }}
    .si-header-title {{ font-family:'Merriweather',serif; font-size:1rem; font-weight:700; color:white; line-height:1.25; }}
    .si-header-sub {{ font-size:11px; color:rgba(255,255,255,0.6); letter-spacing:0.8px; text-transform:uppercase; margin-top:2px; }}
    .si-user {{ text-align:right; color:rgba(255,255,255,0.7); font-size:13px; line-height:1.5; }}
    .si-user strong {{ color:white; font-size:14px; display:block; }}
    .si-nav {{ background: {SI_GREEN}; border-bottom: 1px solid rgba(255,255,255,0.1); }}
    .si-nav-inner {{ max-width:1300px; margin:0 auto; padding:0 36px; display:flex; justify-content:center; }}
    .si-nav-item {{ padding: 12px 24px; font-size: 12.5px; font-weight:600; letter-spacing:0.5px; text-transform:uppercase; color: rgba(255,255,255,0.62); border-bottom: 3px solid transparent; cursor: pointer; white-space: nowrap; transition: all 0.15s; }}
    .si-nav-item:hover {{ color:white; border-bottom-color:rgba(255,255,255,0.35); background:rgba(255,255,255,0.05); }}
    .si-nav-item.active {{ color:white; border-bottom-color:#7ec850; background:rgba(255,255,255,0.07); }}
    .si-body {{ max-width:1300px; margin:0 auto; padding:32px 36px 72px; }}
    .si-h1 {{ font-family:'Merriweather',serif; font-size:1.65rem; font-weight:700; color:{SI_GREEN}; margin-bottom:4px; line-height:1.3; }}
    .si-lead {{ font-size:14px; color:{TEXT_MUTED}; margin-bottom:24px; line-height:1.7; max-width:820px; }}
    .si-metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:28px; }}
    .si-metric {{ background:white; border:1px solid {SI_SAND_DARK}; border-top:3px solid {SI_GREEN}; border-radius:2px; padding:20px 22px 16px; }}
    .si-metric-label {{ font-size:11px; text-transform:uppercase; letter-spacing:1.2px; color:{TEXT_MUTED}; font-weight:700; margin-bottom:8px; }}
    .si-metric-value {{ font-family:'Merriweather',serif; font-size:2.1rem; font-weight:700; color:{SI_GREEN}; line-height:1; }}
    .si-metric-note {{ font-size:12px; color:{TEXT_MUTED}; margin-top:5px; }}
    .si-card {{ background:white; border:1px solid {SI_SAND_DARK}; border-radius:2px; padding:24px; margin-bottom:18px; }}
    .si-card-title {{ font-family:'Merriweather',serif; font-size:0.95rem; font-weight:700; color:{TEXT_DARK}; margin-bottom:3px; }}
    .si-card-sub {{ font-size:12px; color:{TEXT_MUTED}; margin-bottom:14px; }}
    .si-form-sec {{ background:white; border:1px solid {DIVIDER}; border-left:4px solid {SI_GREEN}; border-radius:0 2px 2px 0; padding:22px 26px; margin-bottom:14px; }}
    .si-form-sec-title {{ font-family:'Merriweather',serif; font-size:0.9rem; font-weight:700; color:{SI_GREEN}; margin-bottom:16px; padding-bottom:10px; border-bottom:1px solid {DIVIDER}; }}
    .si-group-label {{ font-size:11.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.9px; color:{SI_GREEN}; margin:18px 0 8px; padding-bottom:4px; border-bottom:1px solid {SI_SAND_DARK}; }}
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {{ background:white !important; border:1px solid #b8b0a4 !important; border-radius:2px !important; font-size:14px !important; }}
    .stButton > button {{ font-family:'Source Sans 3',sans-serif !important; font-size:13px !important; font-weight:600 !important; padding:8px 18px !important; border-radius:2px !important; border:1px solid {SI_SAND_DARK} !important; background:white !important; color:{TEXT_DARK} !important; }}
    .stButton > button:hover {{ background:{SI_GREEN_SOFT} !important; border-color:{SI_GREEN} !important; color:{SI_GREEN} !important; }}
    .stDownloadButton > button {{ background:{SI_GREEN} !important; color:white !important; border-color:{SI_GREEN} !important; border-radius:2px !important; font-weight:600 !important; }}
    .stTabs [data-baseweb="tab-list"] {{ display:none !important; }}
    .total-bar {{ background:{SI_GREEN_SOFT}; border:1px solid {SI_GREEN}; border-radius:2px; padding:12px 18px; margin:12px 0; font-size:14px; color:{SI_GREEN}; font-weight:700; }}
    .si-footer {{ background:{SI_GREEN}; padding:22px 36px; margin-top:48px; }}
    .si-footer-inner {{ max-width:1300px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:16px; }}
    div[data-testid="stHorizontalBlock"] {{ margin:0 !important; padding:0 !important; height:0 !important; overflow:hidden !important; }}
    div[data-testid="stHorizontalBlock"] > div {{ height:0 !important; overflow:hidden !important; }}
    </style>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CHART HELPERS
# ─────────────────────────────────────────────────────────────
def styled_fig(fig, x_title=None, y_title=None, height=400):
    fig.update_layout(
        height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="'Source Sans 3', sans-serif", color=TEXT_DARK, size=13),
        margin=dict(l=8, r=8, t=32, b=8),
        legend=dict(bgcolor="rgba(255,255,255,0.95)", bordercolor=DIVIDER, borderwidth=1),
        xaxis_title=x_title, yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=DIVIDER, tickfont=dict(size=12, color=TEXT_MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=SI_SAND_DARK, zeroline=False, linecolor=DIVIDER, tickfont=dict(size=12, color=TEXT_MUTED))
    return fig

def st_chart(fig, height=None, key=None):
    if height: fig.update_layout(height=height)
    st.plotly_chart(fig, config=PLOTLY_CFG, use_container_width=True, key=key)

def st_df(df, height=380):
    st.dataframe(df, use_container_width=True, height=height)

def pretty(x):
    if pd.isna(x): return ""
    s = str(x).strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    if s.lower() == "ppe": return "PPE"
    return s.title()

# ─────────────────────────────────────────────────────────────
# AUTH (Supabase-backed, same logic as before)
# ─────────────────────────────────────────────────────────────
def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 100000).hex()

def create_user(username, password, full_name, position):
    u = username.strip(); fn = full_name.strip(); pos = position.strip()
    if len(u) < 3: return False, "Username must be at least 3 characters."
    if len(password) < 6: return False, "Password must be at least 6 characters."
    if not fn: return False, "Full name required."
    if not pos: return False, "Position required."
    salt = secrets.token_hex(16)
    sb = get_supabase()
    try:
        sb.table("users").insert({
            "username": u, "password_hash": hash_pw(password, salt),
            "salt": salt, "full_name": fn, "position_title": pos,
        }).execute()
        return True, "Account created."
    except Exception as e:
        msg = str(e)
        if "duplicate" in msg.lower() or "unique" in msg.lower():
            return False, "Username already exists."
        return False, msg

def verify_user(username, password):
    sb = get_supabase()
    try:
        res = sb.table("users").select("*").eq("username", username.strip()).execute()
        if not res.data: return False, None
        row = res.data[0]
        if secrets.compare_digest(row["password_hash"], hash_pw(password, row["salt"])):
            return True, {"user_id": row["user_id"], "username": row["username"],
                          "full_name": row.get("full_name", row["username"]),
                          "position_title": row.get("position_title", "Team Member")}
        return False, None
    except Exception:
        return False, None

def auth_ui():
    for k, v in [("authenticated", False), ("user_profile", None)]:
        if k not in st.session_state: st.session_state[k] = v
    if st.session_state["authenticated"]: return
    st.markdown(f"""
    <div style="background:{SI_GREEN};width:100%;padding:16px 40px;display:flex;align-items:center;gap:14px;">
        <img src="{LOGO_WHITE}" style="height:36px;">
        <span style="color:white;font-family:'Merriweather',serif;font-size:1rem;font-weight:700;">Santa Cruz River Trash Survey</span>
    </div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(f"""
        <div style="background:white;border:1px solid {DIVIDER};border-top:4px solid {SI_GREEN};
        border-radius:0 0 3px 3px;padding:36px 40px;box-shadow:0 4px 24px rgba(0,0,0,0.08);margin-top:40px;">
        <div style="font-family:'Merriweather',serif;font-size:1.3rem;font-weight:700;color:{TEXT_DARK};margin-bottom:4px;">Sign In</div>
        <div style="font-size:13px;color:{TEXT_MUTED};margin-bottom:20px;">Sonoran Institute — River Restoration Program<br>Director: Luke Cole</div></div>
        """, unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign In", "Create Account"])
        with tab1:
            with st.form("login"):
                un = st.text_input("Username")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    ok, prof = verify_user(un, pw)
                    if ok:
                        st.session_state["authenticated"] = True
                        st.session_state["user_profile"] = prof
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
        with tab2:
            with st.form("register"):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Full Name"); pos = c2.text_input("Position / Title")
                nu = st.text_input("Username (min 3 characters)")
                c3, c4 = st.columns(2)
                np_ = c3.text_input("Password (min 6 characters)", type="password")
                np2 = c4.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if np_ != np2: st.error("Passwords do not match.")
                    else:
                        ok, msg = create_user(nu, np_, fn, pos)
                        if ok: st.success(msg)
                        else: st.error(msg)
    st.stop()

# ─────────────────────────────────────────────────────────────
# DATA LOADING FROM SUPABASE
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)   # cache for 5 minutes
def load_data():
    """Load all data from Supabase and return the same structure the rest of the app expects."""
    sb = get_supabase()

    # --- Trash counts ---
    tc_res = sb.table("trash_counts").select("event_id,trash_group,trash_item,count_value").execute()
    tc = pd.DataFrame(tc_res.data) if tc_res.data else pd.DataFrame(
        columns=["event_id", "trash_group", "trash_item", "count_value"])
    tc.rename(columns={"count_value": "count_for_totals"}, inplace=True)

    # --- Site events ---
    se_res = sb.table("site_events").select("*").execute()
    se = pd.DataFrame(se_res.data) if se_res.data else pd.DataFrame()

    # --- Weights ---
    wt_res = sb.table("weights_data").select("event_id,date_recorded,total_weight_oz").execute()
    wt = pd.DataFrame(wt_res.data) if wt_res.data else pd.DataFrame()

    # --- Merge counts with site info ---
    long_df = tc.copy()
    if len(se) > 0 and len(long_df) > 0:
        site_cols = ["event_id", "date_site", "site_label", "point_id",
                     "replicate_no", "lat", "lon", "recorder", "surveyed_m2"]
        site_cols = [c for c in site_cols if c in se.columns]
        long_df = long_df.merge(se[site_cols], on="event_id", how="left")

    # Standardize column names to match what the chart/map code expects
    if "date_site" in long_df.columns:
        long_df["date_plot"] = pd.to_datetime(long_df["date_site"], errors="coerce")
    else:
        long_df["date_plot"] = pd.NaT

    if "site_label" in long_df.columns:
        long_df["site_label_plot"] = long_df["site_label"].fillna("Unknown")
    else:
        long_df["site_label_plot"] = "Unknown"

    for col in ["lat", "lon"]:
        if col not in long_df.columns:
            long_df[col] = np.nan
    long_df.rename(columns={"lat": "lat_plot", "lon": "lon_plot"}, inplace=True)
    long_df["count_for_totals"] = pd.to_numeric(long_df["count_for_totals"], errors="coerce").fillna(0)

    # --- Event summary ---
    ev_df = long_df.groupby("event_id", dropna=False).agg(
        date_plot=("date_plot", "first"),
        site_label_plot=("site_label_plot", "first"),
        surveyed_m2=("surveyed_m2", "first") if "surveyed_m2" in long_df.columns else ("event_id", "count"),
    ).reset_index()

    # --- Weights ---
    if len(wt) > 0:
        wt["date_plot"] = pd.to_datetime(wt["date_recorded"], errors="coerce")
        wt.rename(columns={"total_weight_oz": "weight_oz"}, inplace=True)
    else:
        wt = pd.DataFrame(columns=["event_id", "date_plot", "weight_oz"])

    return ev_df, long_df, se, wt

# ─────────────────────────────────────────────────────────────
# SAVE NEW ENTRY TO SUPABASE
# ─────────────────────────────────────────────────────────────
def save_entry(event_id, survey_date, area_m2, site, recorder, counts_dict):
    sb = get_supabase()

    # Upsert site event
    sb.table("site_events").upsert({
        "event_id":   int(event_id),
        "date_site":  survey_date.isoformat(),
        "site_label": site,
        "location_description": site,
        "recorder":   recorder,
        "surveyed_m2": float(area_m2) if area_m2 else None,
        "complete":   "y",
    }).execute()

    # Insert trash counts (only non-zero)
    rows = []
    for trash_group, items in TRASH_GROUPS.items():
        for item in items:
            val = counts_dict.get(item, 0)
            if val and val > 0:
                rows.append({
                    "event_id":    int(event_id),
                    "trash_group": trash_group,
                    "trash_item":  item,
                    "count_value": float(val),
                })

    if rows:
        sb.table("trash_counts").insert(rows).execute()

    # Clear cache so dashboard reflects new data immediately
    load_data.clear()

# ─────────────────────────────────────────────────────────────
# ANALYSIS HELPERS
# ─────────────────────────────────────────────────────────────
def build_site_stats(df):
    need = {"point_id", "event_id", "replicate_no", "count_for_totals"}
    if not need.issubset(df.columns): return pd.DataFrame()
    pp = df.groupby(["point_id", "event_id", "replicate_no"],
                    dropna=False)["count_for_totals"].sum().reset_index(name="plot_total")
    pp = pp[pp["point_id"].notna()].copy()
    ss = pp.groupby("point_id")["plot_total"].agg(
        n_plots="count", mean="mean", min="min",
        max="max", sd="std", total="sum").reset_index()
    ss["range"] = ss["max"] - ss["min"]
    ss["ok_trip"] = ss["n_plots"] == 3
    labs = df.groupby("point_id", dropna=False).agg(
        site_label=("site_label_plot", "first"),
        lat=("lat_plot", "mean"), lon=("lon_plot", "mean")).reset_index()
    ss = ss.merge(labs, on="point_id", how="left")
    ss = ss.sort_values(["lat", "point_id"], ascending=[False, True]).reset_index(drop=True)
    ss["north_rank"] = np.arange(1, len(ss) + 1)
    ss["site_label"] = ss["site_label"].fillna(ss["point_id"]).astype(str)
    ss["display"] = ss["north_rank"].astype(int).astype(str) + ". " + ss["site_label"]
    return ss

def build_event_totals(df):
    if "event_id" not in df.columns: return pd.DataFrame()
    cols = [c for c in ["event_id", "date_plot", "site_label_plot", "surveyed_m2"] if c in df.columns]
    grp = df.groupby(cols, dropna=False)["count_for_totals"].sum().reset_index(name="total")
    if "surveyed_m2" in grp.columns:
        a = pd.to_numeric(grp["surveyed_m2"], errors="coerce")
        grp["per_m2"] = np.where(a > 0, grp["total"] / a, np.nan)
    return grp

# ─────────────────────────────────────────────────────────────
# MAP RENDERER
# ─────────────────────────────────────────────────────────────
def color_val(v, vmin, vmax):
    if pd.isna(v): return "#5b8bd9"
    t = 0.5 if vmax == vmin else max(0, min(1, (float(v) - float(vmin)) / (float(vmax) - float(vmin))))
    stops = [(0, (49, 130, 206)), (0.33, (78, 201, 176)), (0.66, (245, 149, 52)), (1, (214, 69, 65))]
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]; t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return "#{:02x}{:02x}{:02x}".format(*[round(c0[j] + f * (c1[j] - c0[j])) for j in range(3)])
    return "#d64541"

def render_map(df, lat, lon, label_col, popup_cols, metric_col, height=600):
    if df is None or len(df) == 0: st.info("No coordinate data available."); return
    d = df.copy()
    d[lat] = pd.to_numeric(d[lat], errors="coerce")
    d[lon] = pd.to_numeric(d[lon], errors="coerce")
    d = d[d[lat].notna() & d[lon].notna()]
    if len(d) == 0: st.info("No rows with valid GPS coordinates."); return
    vals = pd.to_numeric(d[metric_col], errors="coerce") if metric_col in d.columns else pd.Series([0] * len(d))
    vmin, vmax = float(vals.min()), float(vals.max())
    recs = []
    for _, r in d.iterrows():
        popup = "<br>".join([
            f"<b>{html.escape(str(c).replace('_', ' ').strip().title())}</b>: {html.escape(str(r.get(c, '')))}"
            for c in popup_cols if c in d.columns
        ])
        recs.append({
            "lat": float(r[lat]), "lon": float(r[lon]),
            "lbl": str(r[label_col]) if label_col in d.columns else "",
            "popup": popup,
            "color": color_val(r.get(metric_col, np.nan), vmin, vmax)
        })
    clat, clon = float(d[lat].mean()), float(d[lon].mean())
    html_src = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{{height:{height}px;width:100%;margin:0;padding:0;font-family:'Source Sans 3',sans-serif;}}
.legend{{position:absolute;bottom:18px;right:18px;z-index:9999;background:rgba(255,255,255,0.97);padding:12px 16px;border-radius:2px;border:1px solid #d4ccc0;font-size:12px;}}
</style></head><body><div id="map"></div>
<div class="legend">
<div style="font-weight:700;margin-bottom:7px;color:{SI_GREEN};font-size:11px;text-transform:uppercase;letter-spacing:0.8px;">Trash Burden</div>
<div style="width:140px;height:8px;border-radius:2px;background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);"></div>
<div style="display:flex;justify-content:space-between;margin-top:4px;color:#6b6b6b;font-size:11px;"><span>Lower</span><span>Higher</span></div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map').setView([{clat},{clon}],13);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{attribution:'OpenStreetMap | CARTO',maxZoom:20}}).addTo(map);
const data={json.dumps(recs)};const bounds=[];
data.forEach(m=>{{
const mk=L.circleMarker([m.lat,m.lon],{{radius:9,color:'rgba(26,26,26,0.45)',weight:1.5,fillColor:m.color,fillOpacity:0.9}}).addTo(map);
if(m.popup) mk.bindPopup(m.popup,{{maxWidth:260}});
if(m.lbl) mk.bindTooltip(m.lbl,{{permanent:false,direction:'top',offset:[0,-10]}});
bounds.push([m.lat,m.lon]);
}});
if(bounds.length>1) map.fitBounds(bounds,{{padding:[28,28]}});
</script></body></html>"""
    components.html(html_src, height=height + 10)

# ─────────────────────────────────────────────────────────────
# APP STARTUP
# ─────────────────────────────────────────────────────────────
inject_css()
auth_ui()

prof = st.session_state.get("user_profile") or {}
PAGES = ["Overview", "Data Entry", "Figures", "Map", "Data Table", "Export"]
if "page" not in st.session_state: st.session_state["page"] = "Overview"

# HEADER
st.markdown(f"""
<div class="si-header"><div class="si-header-inner">
  <div style="display:flex;align-items:center;gap:14px;">
    <img src="{LOGO_WHITE}" class="si-logo">
    <div>
      <div class="si-header-title">Santa Cruz River Trash Survey</div>
      <div class="si-header-sub">Sonoran Institute — River Restoration Program</div>
    </div>
  </div>
  <div class="si-user"><strong>{prof.get('full_name', '')}</strong>{prof.get('position_title', '')}</div>
</div></div>""", unsafe_allow_html=True)

# NAV
active_page = st.session_state["page"]
nav_html = '<div class="si-nav"><div class="si-nav-inner">'
for p in PAGES:
    cls = "si-nav-item active" if active_page == p else "si-nav-item"
    nav_html += f'<span class="{cls}" data-page="{p}">{p}</span>'
nav_html += '</div></div>'
st.markdown(nav_html, unsafe_allow_html=True)

nav_cols = st.columns(len(PAGES))
for i, p in enumerate(PAGES):
    with nav_cols[i]:
        if st.button(p, key=f"nb_{p}", help=p):
            st.session_state["page"] = p
            st.rerun()

components.html(f"""
<script>
(function() {{
  function clickNav() {{
    const items = window.parent.document.querySelectorAll('.si-nav-item');
    items.forEach(function(el) {{
      el.addEventListener('click', function() {{
        const pg = el.getAttribute('data-page');
        const btns = window.parent.document.querySelectorAll('button');
        btns.forEach(function(b) {{ if (b.title === pg) b.click(); }});
      }});
    }});
  }}
  if (document.readyState === 'complete') {{ clickNav(); }}
  else {{ window.addEventListener('load', clickNav); }}
}})();
</script>""", height=0)

page = st.session_state["page"]

# LOAD DATA
with st.spinner("Loading data…"):
    try:
        ev_df, long_df, site_df, weights = load_data()
    except Exception as e:
        st.error(f"Could not load data from database: {e}")
        st.stop()

# ─────────────────────────────────────────────────────────────
# OVERVIEW
# ─────────────────────────────────────────────────────────────
if page == "Overview":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">Santa Cruz River Trash Monitoring</div>', unsafe_allow_html=True)
    st.markdown('<div class="si-lead">Longitudinal trash survey data collected by Sonoran Institute staff and volunteers along the Santa Cruz River corridor, Tucson, Arizona. Program led by <strong>Luke Cole</strong>.</div>', unsafe_allow_html=True)

    total_items  = int(long_df["count_for_totals"].sum())
    total_events = long_df["event_id"].nunique()
    n_sites      = long_df["site_label_plot"].nunique() if "site_label_plot" in long_df.columns else 0
    d_min = long_df["date_plot"].min(); d_max = long_df["date_plot"].max()
    span = f"{d_min.strftime('%b %Y')} – {d_max.strftime('%b %Y')}" if pd.notna(d_min) and pd.notna(d_max) else "—"

    st.markdown(f"""
    <div class="si-metrics">
      <div class="si-metric"><div class="si-metric-label">Total Items Recorded</div><div class="si-metric-value">{total_items:,}</div><div class="si-metric-note">all survey events</div></div>
      <div class="si-metric"><div class="si-metric-label">Survey Events</div><div class="si-metric-value">{total_events:,}</div><div class="si-metric-note">field visits</div></div>
      <div class="si-metric"><div class="si-metric-label">Survey Sites</div><div class="si-metric-value">{n_sites:,}</div><div class="si-metric-note">unique locations</div></div>
      <div class="si-metric"><div class="si-metric-label">Survey Period</div><div class="si-metric-value" style="font-size:1.1rem;padding-top:4px;">{span}</div><div class="si-metric-note">date range</div></div>
    </div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="si-card"><div class="si-card-title">Total Items Over Time</div><div class="si-card-sub">Monthly totals across all survey locations</div>', unsafe_allow_html=True)
        ts = long_df.dropna(subset=["date_plot"]).groupby(pd.Grouper(key="date_plot", freq="MS"))["count_for_totals"].sum().reset_index()
        if len(ts) > 0:
            fig = px.bar(ts, x="date_plot", y="count_for_totals", color_discrete_sequence=[SI_GREEN])
            styled_fig(fig, "Month", "Items Recorded"); st_chart(fig, key="ov1")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="si-card"><div class="si-card-title">Most Frequently Recorded Items</div><div class="si-card-sub">Top 12 items by total count</div>', unsafe_allow_html=True)
        if "trash_item" in long_df.columns:
            top = long_df.groupby("trash_item")["count_for_totals"].sum().sort_values(ascending=False).head(12).reset_index().sort_values("count_for_totals")
            fig = px.bar(top, x="count_for_totals", y="trash_item", orientation="h", color_discrete_sequence=[SI_BLUE])
            styled_fig(fig, "Count", None); st_chart(fig, key="ov2")
        st.markdown('</div>', unsafe_allow_html=True)

    c3, c4 = st.columns([1, 2])
    with c3:
        st.markdown('<div class="si-card"><div class="si-card-title">By Material Category</div>', unsafe_allow_html=True)
        if "trash_group" in long_df.columns:
            grp = long_df.groupby("trash_group")["count_for_totals"].sum().reset_index().sort_values("count_for_totals", ascending=False).head(10)
            fig = px.pie(grp, values="count_for_totals", names="trash_group", color_discrete_sequence=PALETTE, hole=0.42)
            fig.update_traces(textposition="outside", textinfo="percent+label", textfont_size=11)
            styled_fig(fig, height=300); fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10))
            st_chart(fig, key="ov3")
        st.markdown('</div>', unsafe_allow_html=True)

    with c4:
        st.markdown('<div class="si-card"><div class="si-card-title">Items by Location</div><div class="si-card-sub">Top 15 survey sites by total items</div>', unsafe_allow_html=True)
        if "site_label_plot" in long_df.columns:
            by_site = long_df.groupby("site_label_plot")["count_for_totals"].sum().sort_values(ascending=False).head(15).reset_index().sort_values("count_for_totals")
            fig = px.bar(by_site, x="count_for_totals", y="site_label_plot", orientation="h", color_discrete_sequence=["#c0622f"])
            styled_fig(fig, "Total Items", None, height=300); st_chart(fig, key="ov4")
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# DATA ENTRY
# ─────────────────────────────────────────────────────────────
elif page == "Data Entry":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">New Survey Entry</div>', unsafe_allow_html=True)
    st.markdown('<div class="si-lead">Record trash survey data directly into the database. Data is saved immediately and will appear in all charts and tables.</div>', unsafe_allow_html=True)

    with st.form("survey_form", clear_on_submit=False):
        st.markdown('<div class="si-form-sec"><div class="si-form-sec-title">Event Information</div>', unsafe_allow_html=True)
        ec1, ec2, ec3, ec4 = st.columns(4)
        event_id    = ec1.text_input("Event ID", placeholder="e.g. 250")
        survey_date = ec2.date_input("Survey Date", value=date.today())
        area_m2     = ec3.number_input("Plot Area (m²)", min_value=0.0, value=10.0, step=0.5)
        rec_opts    = [""] + TEAM_MEMBERS + ["Other — type below"]
        recorder    = ec4.selectbox("Recorder", rec_opts)

        ec5, ec6 = st.columns([2, 2])
        all_sites = sorted(long_df["site_label_plot"].dropna().astype(str).unique().tolist()) if "site_label_plot" in long_df.columns else []
        site_opts = [""] + sorted(set(SANTA_CRUZ_SITES + all_sites))
        site_sel  = ec5.selectbox("Survey Location", site_opts)
        site_new  = ec6.text_input("Or enter a new location name")
        rec_other = ""
        if recorder == "Other — type below": rec_other = st.text_input("Recorder full name")
        recorder_final = rec_other.strip() if rec_other.strip() else (recorder if recorder else "")
        site_final = site_new.strip() if site_new.strip() else site_sel
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="si-form-sec"><div class="si-form-sec-title">Trash Item Counts</div>', unsafe_allow_html=True)
        counts = {}
        for group_name, items in TRASH_GROUPS.items():
            st.markdown(f'<div class="si-group-label">{group_name}</div>', unsafe_allow_html=True)
            n = min(4, len(items))
            cols = st.columns(n)
            for i, item in enumerate(items):
                with cols[i % n]:
                    counts[item] = st.number_input(item, min_value=0, value=0, step=1, key=f"c_{group_name}_{item}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="si-form-sec"><div class="si-form-sec-title">Field Notes</div>', unsafe_allow_html=True)
        st.text_area("Observations or notable findings", height=90)
        st.markdown('</div>', unsafe_allow_html=True)

        total_preview = sum(counts.values())
        st.markdown(f'<div class="total-bar">Total items counted in this entry: {total_preview:,}</div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("Save Survey Entry to Database", use_container_width=True)

    if submitted:
        if not event_id.strip():
            st.error("Event ID is required.")
        elif not site_final:
            st.error("Survey location is required.")
        else:
            try:
                save_entry(int(event_id.strip()), survey_date, float(area_m2), site_final, recorder_final, counts)
                st.success(f"✓ Entry saved — Event {event_id} · {site_final} · {survey_date.strftime('%B %d, %Y')} · {total_preview:,} items.")
            except Exception as e:
                st.error(f"Could not save entry: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# FIGURES
# ─────────────────────────────────────────────────────────────
elif page == "Figures":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">Analytical Figures</div>', unsafe_allow_html=True)

    df = long_df.copy()
    df["count_for_totals"] = pd.to_numeric(df["count_for_totals"], errors="coerce").fillna(0)
    if "date_plot" in df.columns:
        df["year"]       = df["date_plot"].dt.year
        df["month_num"]  = df["date_plot"].dt.month
        df["month_name"] = pd.Categorical(df["date_plot"].dt.strftime("%b"),
            categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], ordered=True)

    ev_totals = build_event_totals(df)
    ss = build_site_stats(df) if all(c in df.columns for c in ["point_id", "replicate_no"]) else pd.DataFrame()

    FIGS = [
        "Items Over Time", "Rolling Average (3-Month)", "Yearly Totals",
        "Month-by-Year Comparison", "Average Per Event",
        "Most Common Items", "By Material Category",
        "Event Distribution", "Items Per m²", "Weight Over Time",
        "Sites — Mean (N to S)", "Sites — Variability", "Sites — Range",
        "Sites — Total", "Top 10 Cleanest", "Top 10 Heaviest", "All Sites Ranked",
    ]

    fl, fr = st.columns([1, 3])
    with fl:
        st.markdown(f'<div style="background:white;border:1px solid {SI_SAND_DARK};border-radius:2px;padding:16px 14px;">', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{TEXT_MUTED};margin-bottom:10px;">Select Figure</div>', unsafe_allow_html=True)
        figure = st.radio("", FIGS, label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)

    with fr:
        st.markdown(f'<div class="si-card"><div class="si-card-title">{figure}</div>', unsafe_allow_html=True)

        if figure == "Items Over Time":
            ts = df.dropna(subset=["date_plot"]).groupby(pd.Grouper(key="date_plot", freq="MS"))["count_for_totals"].sum().reset_index()
            fig = px.bar(ts, x="date_plot", y="count_for_totals", color_discrete_sequence=[SI_GREEN])
            styled_fig(fig, "Month", "Items"); st_chart(fig, key="f1")

        elif figure == "Rolling Average (3-Month)":
            ts = df.dropna(subset=["date_plot"]).groupby(pd.Grouper(key="date_plot", freq="MS"))["count_for_totals"].sum().reset_index()
            ts["rolling"] = ts["count_for_totals"].rolling(3, min_periods=1).mean()
            fig = go.Figure()
            fig.add_bar(x=ts["date_plot"], y=ts["count_for_totals"], name="Monthly", marker_color=SI_GREEN, opacity=0.22)
            fig.add_scatter(x=ts["date_plot"], y=ts["rolling"], name="3-Month Avg", line=dict(color=SI_GREEN, width=2.5), mode="lines+markers")
            styled_fig(fig, "Month", "Items"); st_chart(fig, key="f2")

        elif figure == "Yearly Totals":
            yr = df.dropna(subset=["year"]).groupby("year")["count_for_totals"].sum().reset_index()
            yr["year"] = yr["year"].astype(str)
            fig = px.bar(yr, x="year", y="count_for_totals", color_discrete_sequence=[SI_GREEN], text="count_for_totals")
            fig.update_traces(textposition="outside")
            styled_fig(fig, "Year", "Items"); st_chart(fig, key="f3")

        elif figure == "Month-by-Year Comparison":
            md = df.dropna(subset=["year", "month_num"]).groupby(["year", "month_num", "month_name"], observed=False)["count_for_totals"].sum().reset_index()
            md["year_str"] = md["year"].astype(str)
            fig = px.bar(md, x="month_name", y="count_for_totals", color="year_str", barmode="group",
                category_orders={"month_name": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]},
                color_discrete_sequence=PALETTE)
            styled_fig(fig, "Month", "Items"); st_chart(fig, key="f4")

        elif figure == "Average Per Event":
            ev2 = ev_totals.dropna(subset=["date_plot"]).groupby(pd.Grouper(key="date_plot", freq="MS"))["total"].mean().reset_index(name="avg")
            fig = px.line(ev2, x="date_plot", y="avg", markers=True, color_discrete_sequence=[SI_BLUE])
            styled_fig(fig, "Month", "Avg Items / Event"); st_chart(fig, key="f5")

        elif figure == "Most Common Items":
            top = df.groupby("trash_item")["count_for_totals"].sum().sort_values(ascending=False).head(25).reset_index().sort_values("count_for_totals")
            fig = px.bar(top, x="count_for_totals", y="trash_item", orientation="h", color_discrete_sequence=[SI_GREEN])
            styled_fig(fig, "Count", None, height=max(480, 26 * len(top))); st_chart(fig, key="f6")

        elif figure == "By Material Category":
            grp = df.groupby("trash_group")["count_for_totals"].sum().sort_values(ascending=False).reset_index().sort_values("count_for_totals")
            fig = px.bar(grp, x="count_for_totals", y="trash_group", orientation="h", color_discrete_sequence=[SI_BLUE])
            styled_fig(fig, "Count", None, height=max(360, 28 * len(grp))); st_chart(fig, key="f7")

        elif figure == "Event Distribution":
            fig = px.histogram(ev_totals, x="total", nbins=20, color_discrete_sequence=[SI_GREEN])
            styled_fig(fig, "Items per Event", "Events"); st_chart(fig, key="f8")

        elif figure == "Items Per m²":
            if "per_m2" in ev_totals.columns:
                trend = ev_totals.dropna(subset=["date_plot", "per_m2"]).groupby(pd.Grouper(key="date_plot", freq="MS"))["per_m2"].mean().reset_index(name="avg")
                fig = px.line(trend, x="date_plot", y="avg", markers=True, color_discrete_sequence=[SI_GREEN])
                styled_fig(fig, "Month", "Items / m²"); st_chart(fig, key="f9")
            else:
                st.info("No surveyed area data available.")

        elif figure == "Weight Over Time":
            if len(weights) > 0:
                dated = weights.dropna(subset=["weight_oz", "date_plot"])
                if len(dated) > 0:
                    trend = dated.groupby(pd.Grouper(key="date_plot", freq="MS"))["weight_oz"].sum().reset_index()
                    fig = px.bar(trend, x="date_plot", y="weight_oz", color_discrete_sequence=[SI_GREEN])
                    styled_fig(fig, "Month", "Weight (oz)"); st_chart(fig, key="f10")
                else:
                    st.info("No dated weight data.")
            else:
                st.info("No weight data found.")

        elif figure in ["Sites — Mean (N to S)", "Sites — Variability", "Sites — Range", "Sites — Total"]:
            if len(ss) == 0:
                st.info("Site statistics require point_id and replicate data.")
            else:
                cm = {"Sites — Mean (N to S)": "mean", "Sites — Variability": "sd",
                      "Sites — Range": "range", "Sites — Total": "total"}
                xcol = cm[figure]; show = ss.copy()
                if xcol == "sd": show[xcol] = show[xcol].fillna(0)
                fig = px.bar(show, x=xcol, y="display", orientation="h", color_discrete_sequence=[SI_GREEN])
                styled_fig(fig, xcol.title(), None, height=max(480, 28 * len(show)))
                fig.update_yaxes(categoryorder="array", categoryarray=show["display"].tolist(), autorange="reversed")
                st_chart(fig, key=f"fs_{figure}")

        elif figure in ["Top 10 Cleanest", "Top 10 Heaviest"]:
            if len(ss) == 0:
                st.info("Site statistics unavailable.")
            else:
                show = (ss.nsmallest(10, "mean") if "Cleanest" in figure else ss.nlargest(10, "mean"))
                col = SI_BLUE if "Cleanest" in figure else "#c0622f"
                fig = px.bar(show, x="mean", y="display", orientation="h", color_discrete_sequence=[col])
                styled_fig(fig, "Avg Items / Plot", None, height=max(360, 36 * len(show)))
                fig.update_yaxes(categoryorder="array", categoryarray=show["display"].tolist(), autorange="reversed")
                st_chart(fig, key=f"fs_{figure}")

        elif figure == "All Sites Ranked":
            if len(ss) == 0:
                st.info("Site statistics unavailable.")
            else:
                show = ss.sort_values(["mean", "point_id"]).reset_index(drop=True)
                show["rank"] = (show.index + 1).astype(str) + ". " + show["site_label"]
                fig = px.bar(show, x="mean", y="rank", orientation="h", color_discrete_sequence=[SI_GREEN])
                styled_fig(fig, "Avg Items / Plot", None, height=max(560, 28 * len(show)))
                fig.update_yaxes(categoryorder="array", categoryarray=show["rank"].tolist(), autorange="reversed")
                st_chart(fig, key="fs_ranked")

        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# MAP
# ─────────────────────────────────────────────────────────────
elif page == "Map":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">Spatial Distribution</div>', unsafe_allow_html=True)
    st.markdown('<div class="si-lead">GPS coordinates of survey sites along the Santa Cruz River corridor.</div>', unsafe_allow_html=True)

    view = st.radio("View", ["Survey Sites", "Individual Events"], horizontal=True)
    if view == "Survey Sites":
        ss = build_site_stats(long_df) if all(c in long_df.columns for c in ["point_id", "replicate_no"]) else pd.DataFrame()
        if len(ss) > 0 and "lat" in ss.columns:
            ss = ss[ss["lat"].notna() & ss["lon"].notna()]
            if len(ss) > 0:
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Sites Mapped", len(ss))
                mc2.metric("Avg Items / Plot", round(float(ss["mean"].mean()), 1))
                mc3.metric("Sites with Full Triplicates", int(ss["ok_trip"].sum()))
                render_map(ss, "lat", "lon", "display", ["site_label", "n_plots", "mean", "sd", "total"], "mean")
            else:
                st.info("No coordinate data found for survey sites.")
        else:
            ev = long_df.groupby(["event_id", "site_label_plot", "date_plot", "lat_plot", "lon_plot"],
                                  dropna=False)["count_for_totals"].sum().reset_index()
            ev = ev[ev["lat_plot"].notna() & ev["lon_plot"].notna()]
            if len(ev) == 0:
                st.info("No GPS coordinates found in the database yet.")
            else:
                render_map(ev, "lat_plot", "lon_plot", "site_label_plot",
                           ["event_id", "site_label_plot", "count_for_totals"], "count_for_totals")
    else:
        ev = long_df.groupby(["event_id", "site_label_plot", "date_plot", "lat_plot", "lon_plot"],
                              dropna=False)["count_for_totals"].sum().reset_index()
        ev = ev[ev["lat_plot"].notna() & ev["lon_plot"].notna()]
        if len(ev) == 0:
            st.info("No events with coordinate data.")
        else:
            st.metric("Events Mapped", len(ev))
            render_map(ev, "lat_plot", "lon_plot", "site_label_plot",
                       ["event_id", "site_label_plot", "count_for_totals"], "count_for_totals")
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# DATA TABLE
# ─────────────────────────────────────────────────────────────
elif page == "Data Table":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">Data Table</div>', unsafe_allow_html=True)

    with st.expander("Filters", expanded=True):
        fc1, fc2, fc3 = st.columns(3)
        all_sites  = sorted(long_df["site_label_plot"].dropna().astype(str).unique().tolist()) if "site_label_plot" in long_df.columns else []
        sel_sites  = fc1.multiselect("Sites", all_sites, default=all_sites)
        all_groups = sorted(long_df["trash_group"].dropna().astype(str).unique().tolist()) if "trash_group" in long_df.columns else []
        sel_groups = fc2.multiselect("Material Categories", all_groups, default=all_groups)
        mn = long_df["date_plot"].min(); mx = long_df["date_plot"].max()
        dr = fc3.date_input("Date Range", value=(mn.date(), mx.date())) if pd.notna(mn) and pd.notna(mx) else None

    f = long_df.copy()
    if sel_sites: f = f[f["site_label_plot"].isin(sel_sites)]
    else: f = f.iloc[0:0]
    if sel_groups and "trash_group" in f.columns: f = f[f["trash_group"].isin(sel_groups)]
    if dr and isinstance(dr, (tuple, list)) and len(dr) == 2:
        s, e = dr
        f = f[f["date_plot"].notna() & (f["date_plot"].dt.date >= s) & (f["date_plot"].dt.date <= e)]

    cols = [c for c in ["event_id", "date_plot", "site_label_plot", "trash_group", "trash_item",
                          "count_for_totals", "surveyed_m2", "recorder"] if c in f.columns]
    sc = [c for c in ["date_plot", "event_id"] if c in cols]
    st.caption(f"{len(f):,} rows")
    st_df(f[cols].sort_values(sc).head(5000), height=540)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────
elif page == "Export":
    st.markdown('<div class="si-body">', unsafe_allow_html=True)
    st.markdown('<div class="si-h1">Export Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="si-lead">Download formatted CSV files for analysis, reporting, or sharing with partners.</div>', unsafe_allow_html=True)

    exports = {
        "Long Format — All Records": (
            long_df[[c for c in ["event_id", "date_plot", "site_label_plot", "trash_group",
                                   "trash_item", "count_for_totals", "surveyed_m2", "recorder"] if c in long_df.columns]],
            "sonoran_SCR_trash_long.csv",
            "One row per item category per event. Best for analysis in R, Python, or Excel."
        ),
        "Event Totals": (
            build_event_totals(long_df),
            "sonoran_SCR_trash_events.csv",
            "One row per survey event with total item count and density (items/m²)."
        ),
    }

    for label, (df_exp, fname, desc) in exports.items():
        st.markdown('<div class="si-card">', unsafe_allow_html=True)
        ec1, ec2 = st.columns([3, 1])
        with ec1:
            st.markdown(f'<div class="si-card-title">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:13px;color:{TEXT_MUTED};margin-bottom:6px;">{desc}</div>', unsafe_allow_html=True)
            if df_exp is not None and len(df_exp) > 0:
                st.caption(f"{len(df_exp):,} rows · {len(df_exp.columns)} columns")
        with ec2:
            if df_exp is not None and len(df_exp) > 0:
                st.download_button("Download CSV", data=df_exp.to_csv(index=False).encode(),
                                   file_name=fname, mime="text/csv", use_container_width=True)
        if df_exp is not None and len(df_exp) > 0:
            with st.expander("Preview first 50 rows"):
                st_df(df_exp.head(50), height=200)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="si-footer"><div class="si-footer-inner">
  <div style="display:flex;align-items:center;gap:14px;">
    <img src="{LOGO_WHITE}" style="height:30px;">
    <div style="color:rgba(255,255,255,0.65);font-size:12px;line-height:1.7;">
      <strong style="color:white;display:block;">Sonoran Institute</strong>
      5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711 · (520) 290-0828
    </div>
  </div>
  <div style="color:rgba(255,255,255,0.45);font-size:11px;text-align:right;line-height:1.8;">
    <a href="https://sonoraninstitute.org/card/santacruz/" style="color:rgba(255,255,255,0.6);text-decoration:none;">Santa Cruz River Program</a><br>
    Internal data management system — Cloud version
  </div>
</div></div>""", unsafe_allow_html=True)

with st.expander("Account", expanded=False):
    st.write(f"Signed in as **{prof.get('full_name', '')}** ({prof.get('username', '')})")
    if st.button("Sign Out"):
        st.session_state["authenticated"] = False
        st.session_state["user_profile"] = None
        st.rerun()
    if st.button("Refresh Data"):
        load_data.clear()
        st.rerun()
