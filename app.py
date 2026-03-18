# ══════════════════════════════════════════════════════════════════
# Santa Cruz River Trash Survey Dashboard  v5.0
# Sonoran Institute — River Restoration Program
# ══════════════════════════════════════════════════════════════════
import json, html, re, hashlib, secrets
from datetime import datetime, date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

@st.cache_resource
def get_sb() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ──────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────
LOGO_W = "https://sonoraninstitute.org/wp-content/themes/sonoran-institute-2016/assets/img/si_logo_white_2018.png"

RIVER_SEGMENTS = {
    "North Reach":   ["Santa Cruz River North of CoCerro","Between an outfall and Camino del Cerro",
                      "between an outfall and Camino del Cerro","Santa Cruz River at Camino del Cerro",
                      "Silverlake Bridge on Santa Cruz"],
    "Central Reach": ["W side of Cushing St. bridge, north of the bridge at outfall","outfall CW Cushing, North side",
                      "Midway between Cushing and Congress, northern site","Midway between Cushing and Congress, southern site",
                      "Midway Curshing and congress","South of Trail's end wash"],
    "South Reach":   ["South of Speedway (St. Mary's) (West)","Speedway and St. Mary",
                      "Santa Cruz river, Drexel and Irvington","Santa Cruz river, Drexel and irvington","drexel"],
    "Rillito":       ["Rillito at Country Club","Arcadia wash","Arcadia Wash between speedway"],
}
SEG_ORDER  = ["North Reach","Central Reach","South Reach","Rillito","Other"]
SEG_COLORS = {"North Reach":"#2980b9","Central Reach":"#27ae60","South Reach":"#e67e22","Rillito":"#8e44ad","Other":"#7f8c8d"}
SEG_LIGHT  = {"North Reach":"#d6eaf8","Central Reach":"#d5f5e3","South Reach":"#fdebd0","Rillito":"#e8daef","Other":"#f0f0f0"}

TRASH_GROUPS = {
    "Cups":           ["Styrofoam (Polar Pop)","Styrofoam (Qt)","Styrofoam (Other)","Plastic","Paper"],
    "Beer":           ["Bottles","Cans"],
    "Liquor":         ["Plastic Bottles","Glass"],
    "Soda":           ["Bottles","Cans"],
    "Water":          ["Bottles"],
    "Sports Drinks":  ["Bottles","Cans"],
    "Juice":          ["Bottles","Cans"],
    "Food Packaging": ["Food Wrappers (Candy, Etc.)","Non-Cup Styrofoam","Non-Cup Plastic",
                       "Non-Cup Paper (Bags, Boxes)","Straws","6-Pack Rings",
                       "Plates And Bowls Plastic","Cans, Milk Jugs, Mixes","Plates, Styrofoam","Utensils","Misc"],
    "Nicotine":       ["Cigs, Cigars, Lighters, Dip, Packs"],
    "Toiletries":     ["Toiletries","Packaging"],
    "Rx, Drugs":      ["Rx And Drug Packaging","Syringes, Paraphernalia"],
    "Toys, Games":    ["Balls, Games","Cd, Dvd, Electronic Packaging","School/Office Supplies","Id Cards, Credit Cards","Batteries"],
    "Paper Litter":   ["News, Books, Magazines","Advertising, Signs, Cards"],
    "Clothing":       ["Clothes, Shoes, Hats","Ppe","Misc. Fabric"],
    "Auto":           ["Car Parts (Small)","Car Parts (Large)","Tires"],
    "Construction":   ["Small Items","Large Items"],
    "Appliances":     ["Bikes, Bike Parts","Furniture/Cushions/Pillows","Shopping Carts","Carpet","Rope/Line","Buckets","Appliances"],
    "Plastic Bags":   ["Plastic Bags"],
    "Misc":           ["Sm. Debris (Ex. Metal, Plastic Scraps)","Lg. Debris (Ex. Garbage Cans)"],
}

TEAM = ["Luke Cole","Sofia Angkasa","Kimberly Stanley","Marie Olson","S. Griset",
        "Soroush Hedayah","Vata Aflatoone","Kimberly Baeza","Joan Woodward",
        "Mark Krieski","Jamie Irby","Marsha Colbert","Axhel Munoz","Christine Hehenga",
        "Saige Thompson","Stephanie Winick","Damon Shorty","Julia Olson",
        "Isabella Feldmann","KyeongHee Kim","Joe Cuffori","Brian Jones"]

PAGES = ["Overview","Map","Trends","Categories","Locations","Data Table","Data Entry","Export"]

C = dict(
    forest="#13291a", green="#1e4d1e", sage="#2d6a2d", mint="#5da832",
    cream="#faf7f0", sand="#f2ede2", sand2="#e8e1d0", sand3="#d8ceba",
    gold="#c9820e", amber="#e8a620", earth="#8b4513", brick="#b5451b",
    sky="#1a5276", water="#2471a3",
    text="#18180f", med="#3a3a28", muted="#686854", divider="#cec6b0", white="#ffffff",
)
PAL = [C["green"],C["water"],C["brick"],C["amber"],C["sage"],"#6c4f8a","#2e8b8b",C["mint"],"#888877",C["earth"],"#c0392b","#16a085"]

st.set_page_config(page_title="SCR Trash Survey · Sonoran Institute", page_icon="🌊",
                   layout="wide", initial_sidebar_state="collapsed")
PC = {"displaylogo":False,"modeBarButtonsToRemove":["lasso2d","select2d","autoScale2d","pan2d"]}

# ──────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown('<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">', unsafe_allow_html=True)
    st.markdown(f"""<style>
html,body,[class*="css"]{{font-family:'DM Sans',sans-serif;color:{C["text"]};}}
.stApp{{background:{C["sand"]};}}
.block-container{{padding:0!important;max-width:100%!important;}}
[data-testid="stSidebar"],[data-testid="collapsedControl"]{{display:none!important;}}

/* ── HEADER ── */
.hdr{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 60%,{C["sage"]} 100%);
      border-bottom:2px solid {C["mint"]};box-shadow:0 4px 28px rgba(0,0,0,.25);}}
.hdr-in{{max-width:1480px;margin:0 auto;padding:14px 44px;
         display:flex;align-items:center;justify-content:space-between;}}
.hdr-brand{{display:flex;align-items:center;gap:18px;}}
.hdr-logo{{height:42px;}}
.hdr-name{{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;
           color:#fff;line-height:1.2;letter-spacing:-.01em;}}
.hdr-sub{{font-size:9.5px;color:rgba(255,255,255,.45);letter-spacing:2px;
          text-transform:uppercase;margin-top:3px;font-family:'DM Mono',monospace;}}
.hdr-user{{font-size:13px;color:rgba(255,255,255,.7);line-height:1.6;text-align:right;}}
.hdr-user strong{{color:#fff;font-size:14px;display:block;font-weight:600;}}
.hdr-pill{{display:inline-flex;align-items:center;gap:5px;background:rgba(93,168,50,.2);
           border:1px solid rgba(93,168,50,.4);border-radius:20px;padding:2px 10px;
           font-size:10px;color:{C["mint"]};font-family:'DM Mono',monospace;
           letter-spacing:.5px;margin-top:3px;}}
.hdr-dot{{width:6px;height:6px;background:{C["mint"]};border-radius:50%;
          animation:pulse 2s infinite;display:inline-block;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.4;}}}}

/* ── NAV — uses components.html iframe for perfect rendering ── */
.nav-outer{{background:{C["forest"]};position:sticky;top:0;z-index:200;
            border-bottom:1px solid rgba(255,255,255,.08);
            box-shadow:0 3px 14px rgba(0,0,0,.35);}}

/* Hide the actual Streamlit radio group — nav is rendered via iframe */
.nav-radio-hide div[role="radiogroup"]{{
    position:absolute!important;opacity:0!important;
    pointer-events:none!important;height:0!important;overflow:hidden!important;
}}

/* ── BODY ── */
.body{{max-width:1480px;margin:0 auto;padding:36px 44px 100px;}}
.pg-title{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:700;
           color:{C["green"]};letter-spacing:-.02em;line-height:1.15;margin-bottom:6px;}}
.pg-lead{{font-size:14px;color:{C["muted"]};line-height:1.8;max-width:780px;margin-bottom:28px;}}
.sec-hd{{font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:600;
          color:{C["text"]};margin-bottom:2px;letter-spacing:-.01em;}}
.sec-sub{{font-size:11.5px;color:{C["muted"]};margin-bottom:14px;line-height:1.6;}}
.tbl-note{{font-size:12px;color:{C["muted"]};line-height:1.7;padding:10px 0 2px;
           border-top:1px solid {C["sand3"]};margin-top:10px;font-style:italic;}}

/* ── KPI GRID ── */
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px;}}
.kpi-grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}}
.kpi{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
      padding:20px 22px 16px;position:relative;overflow:hidden;
      box-shadow:0 2px 10px rgba(0,0,0,.04);transition:box-shadow .2s,transform .2s;}}
.kpi:hover{{box-shadow:0 8px 28px rgba(0,0,0,.1);transform:translateY(-2px);}}
.kpi::after{{content:'';position:absolute;top:0;left:0;right:0;height:3px;
             background:linear-gradient(90deg,{C["green"]},{C["mint"]});}}
.kpi-lbl{{font-size:9.5px;text-transform:uppercase;letter-spacing:1.8px;
          color:{C["muted"]};font-weight:700;margin-bottom:9px;font-family:'DM Mono',monospace;}}
.kpi-val{{font-family:'Cormorant Garamond',serif;font-size:2.3rem;font-weight:700;
          color:{C["green"]};line-height:1;letter-spacing:-.02em;}}
.kpi-val.sm{{font-size:1.25rem;padding-top:6px;line-height:1.3;}}
.kpi-note{{font-size:11px;color:{C["muted"]};margin-top:5px;}}

/* ── CARDS ── */
.card{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
       padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.04);}}
.card-hd{{display:flex;align-items:flex-start;justify-content:space-between;
          padding-bottom:12px;margin-bottom:16px;border-bottom:1px solid {C["sand3"]};}}

/* ── STAT STRIP ── */
.stat-strip{{display:flex;gap:0;background:#fff;border:1px solid {C["sand3"]};
             border-radius:10px;overflow:hidden;margin-bottom:24px;
             box-shadow:0 2px 10px rgba(0,0,0,.04);}}
.stat-item{{flex:1;padding:18px 16px;border-right:1px solid {C["sand3"]};text-align:center;}}
.stat-item:last-child{{border-right:none;}}
.stat-v{{font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:700;
         color:{C["green"]};display:block;line-height:1.1;}}
.stat-l{{font-size:9.5px;color:{C["muted"]};font-family:'DM Mono',monospace;
         text-transform:uppercase;letter-spacing:.8px;margin-top:3px;display:block;}}

/* ── FORM ── */
.form-sec{{background:#fff;border:1px solid {C["divider"]};
           border-left:4px solid {C["green"]};border-radius:0 10px 10px 0;
           padding:22px 26px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,.04);}}
.form-sec-title{{font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:600;
                 color:{C["green"]};margin-bottom:14px;padding-bottom:10px;
                 border-bottom:1px solid {C["sand3"]};}}
.grp-hdr{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
          color:{C["green"]};margin:18px 0 8px;padding-bottom:5px;
          border-bottom:2px solid {C["sand3"]};font-family:'DM Mono',monospace;}}
.live-total{{background:linear-gradient(135deg,{C["green"]}10,{C["mint"]}07);
             border:1px solid {C["green"]}25;border-radius:8px;padding:14px 20px;
             display:flex;align-items:center;gap:14px;margin:14px 0;}}
.live-total-n{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:700;color:{C["green"]};}}
.live-total-l{{font-size:12px;color:{C["muted"]};}}

/* ── INPUTS ── */
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,
.stDateInput>div>div,.stTextInput>div>div,.stNumberInput>div>div,.stTextArea>div>div{{
  background:#fff!important;border:1.5px solid {C["sand3"]}!important;
  border-radius:7px!important;font-size:13.5px!important;
  font-family:'DM Sans',sans-serif!important;transition:border-color .15s!important;}}
div[data-baseweb="select"]>div:focus-within,div[data-baseweb="input"]>div:focus-within{{
  border-color:{C["sage"]}!important;box-shadow:0 0 0 3px rgba(93,168,50,.1)!important;}}
label{{font-size:12px!important;font-weight:600!important;color:{C["med"]}!important;letter-spacing:.3px!important;}}

/* ── BUTTONS ── */
.stButton>button{{font-family:'DM Sans',sans-serif!important;font-size:12.5px!important;
  font-weight:600!important;padding:8px 18px!important;border-radius:7px!important;
  border:1.5px solid {C["sand3"]}!important;background:#fff!important;
  color:{C["med"]}!important;transition:all .15s!important;}}
.stButton>button:hover{{background:{C["green"]}!important;border-color:{C["green"]}!important;
  color:#fff!important;box-shadow:0 4px 14px rgba(30,77,30,.4)!important;}}
.stDownloadButton>button{{background:{C["green"]}!important;color:#fff!important;
  border-color:{C["green"]}!important;border-radius:7px!important;font-weight:600!important;}}

/* ── TABLE ── */
div[data-testid="stDataFrame"]{{border:1px solid {C["sand3"]};border-radius:8px;overflow:hidden;}}

/* ── FILTER EXPANDER ── */
.streamlit-expanderHeader{{font-family:'DM Sans',sans-serif!important;
  font-size:12.5px!important;font-weight:700!important;color:{C["green"]}!important;
  letter-spacing:.3px!important;}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:{C["sand"]};}}
::-webkit-scrollbar-thumb{{background:{C["sand3"]};border-radius:3px;}}
::-webkit-scrollbar-thumb:hover{{background:{C["sage"]};}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(10px);}}to{{opacity:1;transform:none;}}}}
.fade-up{{animation:fadeUp .35s ease both;}}

/* ── FOOTER ── */
.ftr{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 100%);
      padding:24px 44px;margin-top:80px;border-top:2px solid {C["sage"]};}}
.ftr-in{{max-width:1480px;margin:0 auto;display:flex;align-items:center;
         justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.ftr-copy{{color:rgba(255,255,255,.4);font-size:11px;line-height:1.8;font-family:'DM Mono',monospace;}}
.ftr-a{{color:rgba(255,255,255,.55);text-decoration:none;}}

/* Auth tabs */
div[data-testid="stTabs"]>div:first-child{{background:transparent!important;
  border-bottom:1px solid {C["sand3"]}!important;padding:0!important;gap:0!important;margin-bottom:24px!important;}}
div[data-testid="stTabs"] button[role="tab"]{{font-family:'DM Sans',sans-serif!important;
  font-size:11.5px!important;font-weight:600!important;text-transform:uppercase!important;
  letter-spacing:1px!important;color:{C["muted"]}!important;border-radius:0!important;
  padding:12px 20px 12px 0!important;border-bottom:2px solid transparent!important;background:transparent!important;}}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{{
  color:{C["green"]}!important;border-bottom-color:{C["mint"]}!important;}}
div[data-testid="stTabs"] div[role="tabpanel"]{{background:transparent!important;
  border:none!important;padding:0!important;box-shadow:none!important;}}
</style>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# CHART HELPERS
# ──────────────────────────────────────────────────────────────────
def fb(fig, xt=None, yt=None, h=400, leg=True, title=None):
    fig.update_layout(
        height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=C["text"], size=12),
        margin=dict(l=6,r=6,t=44 if title else 28,b=6),
        title=dict(text=title, font=dict(family="Cormorant Garamond, serif", size=16, color=C["green"]),
                   x=0, xanchor="left", pad=dict(l=0)) if title else None,
        legend=dict(bgcolor="rgba(255,255,255,.95)",bordercolor=C["divider"],borderwidth=1,
                    font=dict(size=11),orientation="h",yanchor="bottom",y=1.02,
                    xanchor="right",x=1) if leg else dict(visible=False),
        xaxis_title=xt, yaxis_title=yt,
    )
    fig.update_xaxes(showgrid=False,zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    fig.update_yaxes(showgrid=True,gridcolor=C["sand2"],zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    return fig

def show(fig, key=None):
    st.plotly_chart(fig, config=PC, use_container_width=True, key=key)

def card_open(title, subtitle=""):
    sub = f'<div class="sec-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="card"><div class="card-hd"><div><div class="sec-hd">{title}</div>{sub}</div></div>', unsafe_allow_html=True)

def card_close(): st.markdown('</div>', unsafe_allow_html=True)

def tbl_note(text):
    st.markdown(f'<div class="tbl-note">{text}</div>', unsafe_allow_html=True)

def section_title(text):
    st.markdown(f'<div style="font-family:Cormorant Garamond,serif;font-size:1.3rem;font-weight:700;color:{C["green"]};margin:28px 0 16px;padding-bottom:10px;border-bottom:2px solid {C["sand3"]};">{text}</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────
def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),100000).hex()

def register(username, password, full_name, position):
    u = username.strip()
    if len(u)<3: return False,"Username must be at least 3 characters."
    if len(password)<6: return False,"Password must be at least 6 characters."
    if not full_name.strip(): return False,"Full name required."
    if not position.strip(): return False,"Position required."
    salt = secrets.token_hex(16)
    try:
        get_sb().table("users").insert({"username":u,"password_hash":_hash(password,salt),
            "salt":salt,"full_name":full_name.strip(),"position_title":position.strip()}).execute()
        return True,"Account created — sign in."
    except Exception as e:
        return False,("Username taken." if "unique" in str(e).lower() or "duplicate" in str(e).lower() else str(e))

def login(username, password):
    try:
        r = get_sb().table("users").select("*").eq("username",username.strip()).execute()
        if not r.data: return False,None
        row = r.data[0]
        if secrets.compare_digest(row["password_hash"],_hash(password,row["salt"])):
            return True,{"user_id":row["user_id"],"username":row["username"],
                         "full_name":row.get("full_name",row["username"]),
                         "position_title":row.get("position_title","Team Member")}
        return False,None
    except: return False,None

def auth_gate():
    for k,v in [("auth",False),("prof",None)]:
        if k not in st.session_state: st.session_state[k]=v
    if st.session_state["auth"]: return

    st.markdown(f"""<style>
    .stApp,.stApp>div,.block-container{{background:{C["cream"]}!important;padding:0!important;max-width:100%!important;}}
    [data-testid="column"]:last-of-type,[data-testid="column"]:last-of-type>div,
    [data-testid="column"]:last-of-type>div>div,[data-testid="column"]:last-of-type>div>div>div,
    [data-testid="column"]:last-of-type [data-testid="stVerticalBlock"]{{background:{C["cream"]}!important;}}
    [data-testid="column"]:last-of-type{{padding:72px 52px!important;}}
    [data-testid="column"]:last-of-type label{{color:{C["med"]}!important;font-size:12.5px!important;font-weight:600!important;}}
    [data-testid="column"]:last-of-type input{{background:white!important;color:{C["text"]}!important;border:1.5px solid {C["sand3"]}!important;border-radius:5px!important;}}
    [data-testid="column"]:last-of-type .stButton>button{{background:white!important;color:{C["text"]}!important;border:1.5px solid {C["sand3"]}!important;border-radius:5px!important;font-weight:600!important;}}
    [data-testid="column"]:last-of-type .stButton>button:hover{{background:{C["green"]}!important;color:white!important;border-color:{C["green"]}!important;}}
    .auth-ey{{font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:3px;text-transform:uppercase;color:{C["mint"]};margin-bottom:14px;}}
    .auth-ttl{{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:700;color:{C["text"]};letter-spacing:-.02em;line-height:1.1;margin-bottom:8px;}}
    .auth-sub{{font-size:13px;color:{C["muted"]};line-height:1.75;margin-bottom:32px;}}
    .auth-ftr{{margin-top:24px;padding-top:16px;border-top:1px solid {C["sand3"]};font-size:11px;color:{C["muted"]};font-family:'DM Mono',monospace;display:flex;align-items:center;gap:8px;}}
    </style>""", unsafe_allow_html=True)

    lc, rc = st.columns([1.1, 0.9])
    with lc:
        components.html(f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,700;1,700&family=DM+Sans:wght@400;600&family=DM+Mono:wght@400&display=swap" rel="stylesheet">
        <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        body{{background:linear-gradient(165deg,{C["forest"]} 0%,#0b1a0e 45%,#162b1a 100%);
             min-height:100vh;padding:52px;display:flex;flex-direction:column;
             justify-content:space-between;position:relative;overflow:hidden;font-family:'DM Sans',sans-serif;}}
        body::before{{content:'';position:absolute;inset:0;
             background-image:radial-gradient(circle at 1px 1px,rgba(93,168,50,.06) 1px,transparent 0);
             background-size:28px 28px;}}
        body::after{{content:'';position:absolute;bottom:-160px;right:-160px;width:500px;height:500px;
             background:radial-gradient(circle,rgba(93,168,50,.14) 0%,transparent 65%);border-radius:50%;}}
        .brand{{display:flex;align-items:center;gap:14px;position:relative;z-index:2;}}
        .brand img{{height:40px;opacity:.9;}}
        .bn{{font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:700;color:rgba(255,255,255,.88);line-height:1.25;}}
        .bs{{font-family:'DM Mono',monospace;font-size:8px;color:rgba(255,255,255,.3);letter-spacing:2.5px;text-transform:uppercase;margin-top:3px;}}
        .hero{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:44px 0 36px;position:relative;z-index:2;}}
        .ey{{display:flex;align-items:center;gap:12px;margin-bottom:20px;}}
        .eyl{{width:36px;height:1px;background:#5da832;}}
        .eyt{{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#5da832;}}
        h1{{font-family:'Cormorant Garamond',serif;font-size:3.4rem;font-weight:700;line-height:1.06;color:white;letter-spacing:-.03em;margin-bottom:20px;}}
        h1 em{{font-style:italic;color:#5da832;}}
        .desc{{font-size:14px;color:rgba(255,255,255,.45);line-height:1.85;max-width:380px;margin-bottom:40px;}}
        .stats{{display:flex;gap:0;}}
        .st{{padding:0 28px 0 0;}}
        .st:first-child{{padding-left:0;}}
        .st+.st{{border-left:1px solid rgba(255,255,255,.1);padding-left:28px;}}
        .sv{{font-family:'Cormorant Garamond',serif;font-size:1.9rem;font-weight:700;color:white;line-height:1;}}
        .sl{{font-family:'DM Mono',monospace;font-size:9px;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:1.5px;margin-top:5px;}}
        .foot{{position:relative;z-index:2;font-family:'DM Mono',monospace;font-size:10px;color:rgba(255,255,255,.2);line-height:1.9;}}
        </style></head><body>
        <div class="brand"><img src="{LOGO_W}"><div><div class="bn">Sonoran Institute</div><div class="bs">River Restoration Program</div></div></div>
        <div class="hero">
          <div class="ey"><div class="eyl"></div><div class="eyt">Tucson, Arizona</div></div>
          <h1>Santa Cruz River<br><em>Trash Survey</em></h1>
          <div class="desc">Longitudinal monitoring of litter and debris along the Santa Cruz River corridor and tributaries. Plot-based surveys across multiple sites and reaches.</div>
          <div class="stats">
            <div class="st"><div class="sv">395+</div><div class="sl">Events Logged</div></div>
          </div>
        </div>
        <div class="foot">Program Director: Luke Cole<br>sonoraninstitute.org</div>
        </body></html>""", height=900, scrolling=False)

    with rc:
        st.markdown(f"""<div class="auth-ey">Authorized Personnel Only</div>
        <div class="auth-ttl">Sign in to<br>your account</div>
        <div class="auth-sub">Access the Santa Cruz River data dashboard,<br>field entry tools, and analysis reports.</div>""", unsafe_allow_html=True)
        t1,t2 = st.tabs(["Sign In","Create Account"])
        with t1:
            with st.form("_login"):
                un=st.text_input("Username"); pw=st.text_input("Password",type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Sign In",use_container_width=True):
                    ok,prof=login(un,pw)
                    if ok: st.session_state["auth"]=True; st.session_state["prof"]=prof; st.rerun()
                    else: st.error("Invalid username or password.")
        with t2:
            with st.form("_reg"):
                c1,c2=st.columns(2)
                fn=c1.text_input("Full Name"); pos=c2.text_input("Position / Title")
                nu=st.text_input("Username (min 3 characters)")
                c3,c4=st.columns(2)
                p1=c3.text_input("Password (min 6 characters)",type="password")
                p2=c4.text_input("Confirm Password",type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Create Account",use_container_width=True):
                    if p1!=p2: st.error("Passwords don't match.")
                    else:
                        ok,msg=register(nu,p1,fn,pos)
                        (st.success if ok else st.error)(msg)
        st.markdown(f"""<div class="auth-ftr"><span style="width:5px;height:5px;border-radius:50%;background:{C["mint"]};display:inline-block;"></span>Cloud database secured by Supabase</div>""",unsafe_allow_html=True)
    st.stop()

# ──────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    sb=get_sb()
    tc=pd.DataFrame(sb.table("trash_counts").select("event_id,trash_group,trash_item,count_value").execute().data or [])
    se=pd.DataFrame(sb.table("site_events").select("*").execute().data or [])
    wt=pd.DataFrame(sb.table("weights_data").select("event_id,date_recorded,total_weight_oz").execute().data or [])

    if tc.empty: tc=pd.DataFrame(columns=["event_id","trash_group","trash_item","count_value"])
    tc.rename(columns={"count_value":"n"},inplace=True)
    tc["n"]=pd.to_numeric(tc["n"],errors="coerce").fillna(0)

    long=tc.copy()
    if not se.empty and not long.empty:
        cols=[c for c in ["event_id","date_site","site_label","point_id","replicate_no","lat","lon","recorder","surveyed_m2"] if c in se.columns]
        long=long.merge(se[cols],on="event_id",how="left")

    long["date"]=pd.to_datetime(long.get("date_site",pd.NaT),errors="coerce")
    long["site_label"]=long.get("site_label",pd.Series("Unknown",index=long.index)).fillna("Unknown")
    long["lat"]=pd.to_numeric(long.get("lat",np.nan),errors="coerce") if "lat" in long.columns else np.nan
    long["lon"]=pd.to_numeric(long.get("lon",np.nan),errors="coerce") if "lon" in long.columns else np.nan
    long["seg"]=long["site_label"].map({s:seg for seg,sites in RIVER_SEGMENTS.items() for s in sites}).fillna("Other")
    long["trash_group"]=long["trash_group"].fillna("Misc")
    long["trash_item"]=long["trash_item"].fillna("Unknown")
    long["year"]=long["date"].dt.year
    long["month"]=long["date"].dt.month
    long["month_name"]=pd.Categorical(long["date"].dt.strftime("%b"),
        categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],ordered=True)

    if not wt.empty:
        wt["date"]=pd.to_datetime(wt["date_recorded"],errors="coerce")
        wt.rename(columns={"total_weight_oz":"weight_oz"},inplace=True)
    else: wt=pd.DataFrame(columns=["event_id","date","weight_oz"])

    return long, se, wt

def make_et(df):
    if df.empty: return pd.DataFrame()
    g=[c for c in ["event_id","date","site_label","seg","surveyed_m2"] if c in df.columns]
    et=df.groupby(g,dropna=False)["n"].sum().reset_index(name="total")
    if "surveyed_m2" in et.columns:
        a=pd.to_numeric(et["surveyed_m2"],errors="coerce")
        et["per_m2"]=np.where(a>0, et["total"]/a, np.nan)
    return et

# ──────────────────────────────────────────────────────────────────
# FILTERS
# ──────────────────────────────────────────────────────────────────
def render_filters(df, kp="", cats=True):
    all_segs=[s for s in df["seg"].dropna().unique() if s!="Other"] if "seg" in df.columns else []
    all_segs=sorted(all_segs)
    all_sites=sorted(df["site_label"].dropna().unique()) if "site_label" in df.columns else []
    all_grps=sorted(df["trash_group"].dropna().unique()) if "trash_group" in df.columns else []
    mn,mx=df["date"].min(),df["date"].max()
    ncols=4 if cats else 3
    cols=st.columns(ncols)
    with cols[0]: sel_segs=st.multiselect("River Segment",all_segs,default=all_segs,key=f"{kp}_segs")
    with cols[1]: sel_sites=st.multiselect("Location",all_sites,default=all_sites,key=f"{kp}_sites")
    if cats:
        with cols[2]: sel_grps=st.multiselect("Category",all_grps,default=all_grps,key=f"{kp}_grps")
    else: sel_grps=all_grps
    with cols[-1]:
        dr=st.date_input("Date Range",value=(mn.date(),mx.date()),key=f"{kp}_dr") if pd.notna(mn) and pd.notna(mx) else None
    f=df.copy()
    if sel_segs and "seg" in f.columns: f=f[f["seg"].isin(sel_segs+["Other"])]
    if sel_sites and "site_label" in f.columns: f=f[f["site_label"].isin(sel_sites)]
    if sel_grps and "trash_group" in f.columns: f=f[f["trash_group"].isin(sel_grps)]
    if dr and isinstance(dr,(tuple,list)) and len(dr)==2:
        s,e=dr; f=f[f["date"].notna()&(f["date"].dt.date>=s)&(f["date"].dt.date<=e)]
    return f

def stat_strip(df_orig, df_f):
    ni=int(df_f["n"].sum()) if "n" in df_f.columns else 0
    ne=df_f["event_id"].nunique() if "event_id" in df_f.columns else 0
    ns=df_f["site_label"].nunique() if "site_label" in df_f.columns else 0
    pct=100*len(df_f)/max(len(df_orig),1)
    st.markdown(f"""<div class="stat-strip">
    <div class="stat-item"><span class="stat-v">{ni:,}</span><span class="stat-l">Items in View</span></div>
    <div class="stat-item"><span class="stat-v">{ne:,}</span><span class="stat-l">Events</span></div>
    <div class="stat-item"><span class="stat-v">{ns:,}</span><span class="stat-l">Locations</span></div>
    <div class="stat-item"><span class="stat-v">{pct:.0f}%</span><span class="stat-l">Of All Data</span></div>
    </div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# MAP
# ──────────────────────────────────────────────────────────────────
def color_val(v,vmin,vmax):
    if pd.isna(v): return "#5b8bd9"
    t=0.5 if vmax==vmin else max(0,min(1,(float(v)-float(vmin))/(float(vmax)-float(vmin))))
    stops=[(0,(49,130,206)),(0.33,(78,201,176)),(0.66,(245,149,52)),(1,(214,69,65))]
    for i in range(len(stops)-1):
        t0,c0=stops[i]; t1,c1=stops[i+1]
        if t0<=t<=t1:
            f=(t-t0)/(t1-t0) if t1>t0 else 0
            return "#{:02x}{:02x}{:02x}".format(*[round(c0[j]+f*(c1[j]-c0[j])) for j in range(3)])
    return "#d64541"

def render_map(df,lat,lon,label_col,popup_cols,metric_col,seg_col=None,height=560):
    if df is None or len(df)==0: st.info("No coordinate data available."); return
    d=df.copy()
    d[lat]=pd.to_numeric(d[lat],errors="coerce"); d[lon]=pd.to_numeric(d[lon],errors="coerce")
    d=d[d[lat].notna()&d[lon].notna()]
    if len(d)==0: st.info("No rows with valid GPS coordinates."); return
    vals=pd.to_numeric(d[metric_col],errors="coerce") if metric_col in d.columns else pd.Series([0]*len(d))
    vmin,vmax=float(vals.min()),float(vals.max())
    recs=[]
    for _,r in d.iterrows():
        popup="<br>".join([f"<b>{html.escape(str(c).replace('_',' ').strip().title())}</b>: {html.escape(str(r.get(c,'') or ''))}" for c in popup_cols if c in d.columns])
        color=SEG_COLORS.get(str(r.get(seg_col,"Other")),"#888") if seg_col else color_val(r.get(metric_col,np.nan),vmin,vmax)
        recs.append({"lat":float(r[lat]),"lon":float(r[lon]),"lbl":str(r.get(label_col,"")),"popup":popup,"color":color})
    clat,clon=float(d[lat].mean()),float(d[lon].mean())
    leg_html="".join(f'<div class="li"><div class="ld" style="background:{c}"></div>{s}</div>' for s,c in SEG_COLORS.items() if s!="Other") if seg_col else '<div style="width:130px;height:7px;border-radius:2px;background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);margin-bottom:4px;"></div><div style="display:flex;justify-content:space-between;font-size:10px;color:#888;"><span>Low</span><span>High</span></div>'
    leg_title="River Segments" if seg_col else "Trash Burden"
    html_src=f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{{height:{height}px;width:100%;margin:0;padding:0;font-family:'DM Sans',sans-serif;}}
.legend{{position:absolute;bottom:18px;right:18px;z-index:9999;background:rgba(255,255,255,.97);
padding:13px 16px;border-radius:8px;border:1px solid #d4ccc0;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);}}
.lt{{font-weight:700;margin-bottom:9px;color:#1e4d1e;font-size:10px;text-transform:uppercase;letter-spacing:.8px;}}
.li{{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px;}}
.ld{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
.leaflet-popup-content{{font-family:'DM Sans',sans-serif;font-size:13px;line-height:1.65;min-width:190px;}}
</style></head><body>
<div id="map"></div>
<div class="legend"><div class="lt">{leg_title}</div>{leg_html}</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map').setView([{clat},{clon}],12);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{attribution:'© OpenStreetMap · © CARTO',maxZoom:20}}).addTo(map);
const data={json.dumps(recs)};const bounds=[];
data.forEach(m=>{{
const mk=L.circleMarker([m.lat,m.lon],{{radius:9,color:'rgba(255,255,255,.9)',weight:2,fillColor:m.color,fillOpacity:.88}}).addTo(map);
if(m.popup) mk.bindPopup(m.popup,{{maxWidth:280}});
if(m.lbl) mk.bindTooltip('<strong>'+m.lbl+'</strong>',{{permanent:false,direction:'top',offset:[0,-12]}});
bounds.push([m.lat,m.lon]);
}});
if(bounds.length>1) map.fitBounds(bounds,{{padding:[30,30]}});
</script></body></html>"""
    components.html(html_src, height=height+10)

# ──────────────────────────────────────────────────────────────────
# APP START
# ──────────────────────────────────────────────────────────────────
inject_css()
auth_gate()
prof=st.session_state.get("prof") or {}

# HEADER
st.markdown(f"""<div class="hdr"><div class="hdr-in">
  <div class="hdr-brand">
    <img src="{LOGO_W}" class="hdr-logo">
    <div><div class="hdr-name">Santa Cruz River Trash Survey</div>
         <div class="hdr-sub">Sonoran Institute · River Restoration Program</div></div>
  </div>
  <div class="hdr-user"><strong>{prof.get('full_name','')}</strong>{prof.get('position_title','')}
  <div class="hdr-pill"><span class="hdr-dot"></span>&nbsp;Live Database</div></div>
</div></div>""", unsafe_allow_html=True)

# ── NAV BAR via components.html (perfect rendering, no CSS battles) ──
if "page" not in st.session_state: st.session_state["page"] = PAGES[0]
cur = st.session_state["page"]

nav_items = "".join(f"""<div class="ni {'active' if p==cur else ''}" onclick="choose('{p}')">{p}</div>""" for p in PAGES)
components.html(f"""<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:{C["forest"]};font-family:'DM Sans',sans-serif;
      border-bottom:1px solid rgba(255,255,255,.08);
      box-shadow:0 3px 14px rgba(0,0,0,.35);}}
.nav{{max-width:1480px;margin:0 auto;padding:0 44px;display:flex;gap:0;}}
.ni{{padding:14px 20px;font-size:11px;font-weight:700;letter-spacing:1.2px;
     text-transform:uppercase;color:rgba(255,255,255,.6);
     border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap;
     transition:all .15s;}}
.ni:hover{{color:white;background:rgba(255,255,255,.06);border-bottom-color:rgba(255,255,255,.25);}}
.ni.active{{color:#5da832;border-bottom-color:#5da832;background:rgba(93,168,50,.08);}}
</style>
<div class="nav">{nav_items}</div>
<script>
function choose(p){{
  // post message to parent Streamlit
  window.parent.postMessage({{type:'streamlit:setComponentValue',value:p}},'*');
}}
</script>""", height=50, key="nav_html")

# Invisible radio to actually drive Streamlit state from the nav clicks
# We use session state directly — nav clicks go through postMessage → component value
nav_val = st.radio("_nav", PAGES, index=PAGES.index(cur),
                   label_visibility="collapsed", horizontal=True, key="_nav_radio")
if nav_val != cur:
    st.session_state["page"] = nav_val
    st.rerun()
# Also hide the radio
st.markdown("""<style>
div[data-testid="stHorizontalBlock"]:has(div[role="radiogroup"]) {
    height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;
    position:absolute!important;opacity:0!important;pointer-events:none!important;
}
</style>""", unsafe_allow_html=True)

page = st.session_state["page"]

# LOAD DATA
with st.spinner("Loading from database…"):
    try: long, se, wt = load_data()
    except Exception as e: st.error(f"Database error: {e}"); st.stop()

et = make_et(long)

# ══════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Santa Cruz River Trash Monitoring</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pg-lead">Longitudinal trash survey data collected along the Santa Cruz River corridor, Tucson, AZ. Plot-based surveys across {long["site_label"].nunique()} recorded locations spanning the river corridor and tributaries. Program directed by <strong>Luke Cole</strong>, Sonoran Institute.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf = render_filters(long, kp="ov")
    stat_strip(long, lf)

    total_n=int(lf["n"].sum()); n_ev=lf["event_id"].nunique(); n_si=lf["site_label"].nunique()
    n_gr=lf["trash_group"].nunique(); d_min,d_max=lf["date"].min(),lf["date"].max()
    span=f"{d_min.strftime('%b %Y')} – {d_max.strftime('%b %Y')}" if pd.notna(d_min) and pd.notna(d_max) else "—"
    st.markdown(f"""<div class="kpi-grid">
    <div class="kpi"><div class="kpi-lbl">Total Items Recorded</div><div class="kpi-val">{total_n:,}</div><div class="kpi-note">across all survey events</div></div>
    <div class="kpi"><div class="kpi-lbl">Survey Events</div><div class="kpi-val">{n_ev:,}</div><div class="kpi-note">individual field visits</div></div>
    <div class="kpi"><div class="kpi-lbl">Unique Locations</div><div class="kpi-val">{n_si:,}</div><div class="kpi-note">recorded site names</div></div>
    <div class="kpi"><div class="kpi-lbl">Trash Categories</div><div class="kpi-val">{n_gr}</div><div class="kpi-note">item groups tracked</div></div>
    <div class="kpi"><div class="kpi-lbl">Survey Period</div><div class="kpi-val sm">{span}</div><div class="kpi-note">date range</div></div>
    </div>""", unsafe_allow_html=True)

    c1,c2 = st.columns([3,2])
    with c1:
        card_open("Monthly Items Recorded Over Time",
                  "Each bar represents one calendar month. Gray bars indicate months where no surveys were conducted. The dashed gold line shows the 3-month rolling average to reveal long-term trends.")
        ts=lf.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
        if len(ts)>0:
            full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
            ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
            ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0); ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
            fig=go.Figure()
            fig.add_bar(x=ts["date"],y=ts["n"],marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],name="Monthly",opacity=.88)
            fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-Month Rolling Avg",line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
            fb(fig,"Month","Total Items",h=300); show(fig,"ov_ts")
        card_close()
    with c2:
        card_open("Share by Trash Category",
                  "Proportional breakdown of all items recorded across every category. Food Packaging, Clothing, and Misc typically dominate.")
        grp=lf.groupby("trash_group")["n"].sum().sort_values(ascending=False).reset_index()
        if len(grp)>0:
            fig=px.pie(grp,values="n",names="trash_group",hole=.44,color_discrete_sequence=PAL)
            fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=9.5,pull=[.04]+[0]*(len(grp)-1))
            fig.update_layout(height=300,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"ov_pie")
        card_close()

    c3,c4 = st.columns([2,3])
    with c3:
        card_open("Top 15 Most Frequently Recorded Items",
                  "Ranked by cumulative count across all survey events and locations.")
        top=lf.groupby("trash_item")["n"].sum().nlargest(15).reset_index().sort_values("n")
        fig=px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["water"]])
        fb(fig,"Total Count",None,h=420); show(fig,"ov_top")
        card_close()
    with c4:
        card_open("Items by River Segment and Category",
                  "Stacked bar chart showing contribution of each trash category within each known river segment. Only sites with assigned segment labels are shown.")
        if "seg" in lf.columns:
            sg=lf[lf["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            sg["seg"]=pd.Categorical(sg["seg"],SEG_ORDER,ordered=True); sg=sg.sort_values("seg")
            fig=px.bar(sg,x="seg",y="n",color="trash_group",barmode="stack",color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER})
            fb(fig,"River Segment","Total Items",h=420); show(fig,"ov_seg")
        card_close()

    section_title("Category Summary Table")
    st.markdown('<div class="sec-sub">Total items, number of individual records, and average count per record for each trash category. Sorted by total count descending.</div>', unsafe_allow_html=True)
    summary=lf.groupby("trash_group")["n"].agg(Total="sum",Records="count",Average="mean").reset_index()
    summary["% of Total"]=(100*summary["Total"]/max(summary["Total"].sum(),1)).round(1)
    summary=summary.sort_values("Total",ascending=False).round(1).reset_index(drop=True)
    summary.index=range(1,len(summary)+1)
    summary.columns=["Category","Total Items","# Records","Avg per Record","% of Total"]
    st.dataframe(summary, use_container_width=True, height=380)
    tbl_note("Each row represents one trash category group. 'Records' = number of individual count entries in the database for that category. 'Avg per Record' = mean count per single data entry, not per survey event.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# MAP
# ══════════════════════════════════════════════════════════════════
elif page == "Map":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Survey Site Map</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">GPS locations of survey sites along the Santa Cruz River corridor. Click any marker to view site details. Only sites with latitude/longitude data in the database will appear on the map.</div>', unsafe_allow_html=True)

    map_mode=st.radio("Map view",["By River Segment","By Trash Burden","Individual Events"],horizontal=True)

    site_agg=long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),lat=("lat","mean"),lon=("lon","mean")).reset_index()
    site_agg["avg_per_event"]=(site_agg["total"]/site_agg["events"]).round(1)
    wc=site_agg[site_agg["lat"].notna()&site_agg["lon"].notna()]

    m1,m2,m3,m4=st.columns(4)
    m1.metric("Sites with GPS",len(wc)); m2.metric("Total Sites in DB",len(site_agg))
    m3.metric("Events Mapped",int(wc["events"].sum()))
    m4.metric("Grand Avg Items/Site",f"{site_agg['avg_per_event'].mean():.1f}" if len(site_agg)>0 else "—")

    if map_mode=="By River Segment":
        render_map(wc,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total",seg_col="seg")
    elif map_mode=="By Trash Burden":
        render_map(wc,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total")
    else:
        ev_geo=et[et["lat"].notna()&et["lon"].notna()] if "lat" in et.columns else pd.DataFrame()
        if len(ev_geo)>0: render_map(ev_geo,"lat","lon","site_label",["event_id","site_label","date","total"],"total",seg_col="seg")
        else: st.info("No individual event coordinates in database.")

    section_title("Sites with GPS Coordinates")
    st.markdown('<div class="sec-sub">All survey locations that have latitude/longitude data. Sorted by total items recorded descending.</div>', unsafe_allow_html=True)
    disp=wc[["site_label","seg","total","events","avg_per_event","lat","lon"]].copy()
    disp.columns=["Site Name","River Segment","Total Items","# Events","Avg Items/Event","Latitude","Longitude"]
    disp=disp.sort_values("Total Items",ascending=False).round(2).reset_index(drop=True)
    disp.index=range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=420)
    tbl_note("Latitude and longitude values are averaged from all records for that site. 'Avg Items/Event' = total items ÷ number of survey events at that location.")

    section_title("All Sites — Including Those Without GPS")
    st.markdown('<div class="sec-sub">Complete list of all recorded locations in the database, with or without coordinates.</div>', unsafe_allow_html=True)
    all_sites_tbl=long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique")).reset_index()
    all_sites_tbl["avg"]=(all_sites_tbl["total"]/all_sites_tbl["events"]).round(1)
    all_sites_tbl=all_sites_tbl.sort_values("total",ascending=False).reset_index(drop=True)
    all_sites_tbl.index=range(1,len(all_sites_tbl)+1)
    all_sites_tbl.columns=["Location","River Segment","Total Items","# Events","Avg Items/Event"]
    st.dataframe(all_sites_tbl, use_container_width=True, height=480)
    tbl_note(f"Showing all {len(all_sites_tbl)} unique location names recorded in the database. Many may have slight spelling variations (e.g. 'Drexel and Irvington' vs 'Drexel and irvington') which cause them to appear as separate entries.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TRENDS
# ══════════════════════════════════════════════════════════════════
elif page == "Trends":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Temporal Trends</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">How trash levels have changed over time — monthly, annual, and seasonal patterns across the full survey record. Use the filter to narrow by location, segment, or date range.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="tr", cats=False)
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)

    c1,c2=st.columns(2)
    with c1:
        card_open("Monthly Item Count — Full Survey Record",
                  "Green bars = survey conducted. Gray bars = no survey that month. Dashed gold line = 3-month rolling average to smooth out variability.")
        ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
        full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
        ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
        ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0); ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
        fig=go.Figure()
        fig.add_bar(x=ts["date"],y=ts["n"],marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],name="Monthly")
        fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-Mo Rolling Avg",line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
        fb(fig,"Month","Total Items",h=320); show(fig,"tr_ts")
        card_close()
    with c2:
        card_open("Annual Totals by Survey Year",
                  "Total items recorded across all events within each calendar year. Labels show exact totals above each bar.")
        yr=df.dropna(subset=["year"]).groupby("year")["n"].sum().reset_index(); yr["year"]=yr["year"].astype(str)
        fig=px.bar(yr,x="year",y="n",color_discrete_sequence=[C["green"]],text="n")
        fig.update_traces(texttemplate="%{text:,}",textposition="outside")
        fb(fig,"Year","Total Items",h=320); show(fig,"tr_yr")
        card_close()

    c3,c4=st.columns(2)
    with c3:
        card_open("Month-by-Month Comparison Across Years",
                  "Each cluster of bars shows the same calendar month across different survey years. Useful for identifying seasonal patterns and year-over-year changes.")
        md=df.dropna(subset=["year","month"]).groupby(["year","month","month_name"],observed=False)["n"].sum().reset_index()
        md["year_str"]=md["year"].astype(str)
        fig=px.bar(md,x="month_name",y="n",color="year_str",barmode="group",
            category_orders={"month_name":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]},
            color_discrete_sequence=PAL)
        fb(fig,"Month","Total Items",h=320); show(fig,"tr_mby")
        card_close()
    with c4:
        card_open("Average Items Per Survey Event Over Time",
                  "Monthly average of total items found per individual field visit. Dotted line = grand mean across the full record. Useful for detecting whether survey intensity is changing.")
        ef=make_et(lf)
        if not ef.empty and "date" in ef.columns:
            ev2=ef.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["total"].mean().reset_index(name="avg")
            fig=px.line(ev2,x="date",y="avg",markers=True,color_discrete_sequence=[C["water"]])
            fig.add_hline(y=ev2["avg"].mean(),line_dash="dot",line_color=C["earth"],annotation_text=f"Grand mean: {ev2['avg'].mean():.0f}",annotation_font_size=11)
            fb(fig,"Month","Avg Items / Event",h=320); show(fig,"tr_avg")
        card_close()

    c5,c6=st.columns(2)
    with c5:
        card_open("Items by River Segment Over Time",
                  "Quarterly item totals for each named river segment. Shows how trash burden has shifted geographically across survey years.")
        if "seg" in df.columns:
            sg=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(sg,x="date",y="n",color="seg",markers=True,color_discrete_map=SEG_COLORS)
            fb(fig,"Quarter","Items",h=320); show(fig,"tr_seg")
        card_close()
    with c6:
        if not wt.empty and "weight_oz" in wt.columns:
            card_open("Weight of Trash Collected Over Time",
                      "Monthly total weight (oz) across all events where weight data was recorded. Not all events have weight data.")
            dated=wt.dropna(subset=["weight_oz","date"])
            if len(dated)>0:
                wtrend=dated.groupby(pd.Grouper(key="date",freq="MS"))["weight_oz"].sum().reset_index()
                fig=px.bar(wtrend,x="date",y="weight_oz",color_discrete_sequence=[C["earth"]])
                fb(fig,"Month","Weight (oz)",h=320); show(fig,"tr_wt")
            card_close()

    section_title("Annual Summary Table")
    st.markdown('<div class="sec-sub">Aggregate statistics by survey year. Events = number of distinct field visits. Total Items = all counts recorded that year.</div>', unsafe_allow_html=True)
    ann=df.dropna(subset=["year"]).groupby("year").agg(
        total_items=("n","sum"),
        events=("event_id","nunique") if "event_id" in df.columns else ("n","count")
    ).reset_index()
    ann["avg_per_event"]=(ann["total_items"]/ann["events"]).round(1)
    ann["year"]=ann["year"].astype(int)
    ann=ann.sort_values("year",ascending=False).reset_index(drop=True)
    ann.index=range(1,len(ann)+1)
    ann.columns=["Year","Total Items","# Events","Avg Items per Event"]
    st.dataframe(ann, use_container_width=True, height=300)
    tbl_note("'Avg Items per Event' = total items that year ÷ number of distinct survey events. Higher values indicate either more trash found or more thorough counting, or both.")

    section_title("Monthly Breakdown Table")
    st.markdown('<div class="sec-sub">Total items by calendar month across all years combined. Reveals seasonal patterns in trash accumulation or survey coverage.</div>', unsafe_allow_html=True)
    mon=df.dropna(subset=["month_name"]).groupby("month_name",observed=False)["n"].agg(
        total="sum", events=("count")
    ).reset_index()
    mon.columns=["Month","Total Items","# Records"]
    st.dataframe(mon, use_container_width=True, height=300)
    tbl_note("Month-level data combines all survey years. Months with low counts may reflect fewer surveys conducted, not less trash present.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════════════════════════
elif page == "Categories":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Trash Categories</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Detailed breakdown of all recorded items by category group and individual type. Food Packaging is consistently the dominant category, followed by Clothing and Misc debris.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="cat")
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)
    total_all=df["n"].sum()

    c1,c2=st.columns([2,3])
    with c1:
        card_open("Total Items by Category Group",
                  "Horizontal bar chart of cumulative totals per category, sorted ascending. Food Packaging is typically the largest group due to the high number of item subtypes it contains.")
        ct=df.groupby("trash_group")["n"].sum().sort_values().reset_index()
        fig=px.bar(ct,x="n",y="trash_group",orientation="h",color_discrete_sequence=[C["green"]],text="n")
        fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
        fb(fig,"Total Items",None,h=max(400,28*len(ct))); show(fig,"cat_ct")
        card_close()
    with c2:
        card_open("Top 30 Individual Items — Ranked by Total Count",
                  "Every recorded item type ranked by cumulative count. Items near the bottom are rarely found; items near the top appear most consistently across surveys.")
        top=df.groupby("trash_item")["n"].sum().sort_values(ascending=False).head(30).reset_index().sort_values("n")
        fig=px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["sky"]])
        fb(fig,"Total Count",None,h=max(540,22*len(top))); show(fig,"cat_top")
        card_close()

    c3,c4=st.columns(2)
    with c3:
        card_open("Category Proportions — Percentage of All Items",
                  "Each slice shows that category's share of total items recorded. Hover for exact percentages.")
        ct2=df.groupby("trash_group")["n"].sum().sort_values(ascending=False).reset_index()
        fig=px.pie(ct2,values="n",names="trash_group",color_discrete_sequence=PAL,hole=.42)
        fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=9.5)
        fig.update_layout(height=380,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
        show(fig,"cat_pie")
        card_close()
    with c4:
        card_open("Category Trends — Quarterly Totals (Top 6 Groups)",
                  "Line chart showing how the top 6 trash categories have changed over time by quarter. Reveals shifts in composition — e.g. whether Food Packaging is growing relative to other types.")
        if "date" in df.columns:
            top6=df.groupby("trash_group")["n"].sum().nlargest(6).index.tolist()
            ct3=df[df["trash_group"].isin(top6)].groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ct3,x="date",y="n",color="trash_group",markers=True,color_discrete_sequence=PAL)
            fb(fig,"Quarter","Items",h=380); show(fig,"cat_trend")
        card_close()

    c5,c6=st.columns(2)
    with c5:
        card_open("Category Mix by River Segment",
                  "Stacked horizontal bars showing how category composition differs across river segments. Highlights whether certain segments have distinctly different waste profiles.")
        if "seg" in df.columns:
            sc=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            fig=px.bar(sc,x="n",y="seg",color="trash_group",orientation="h",barmode="stack",color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER[::-1]})
            fb(fig,"Items","Segment",h=320); show(fig,"cat_sxc")
        card_close()
    with c6:
        card_open("Items per Survey Event by Category",
                  "Average number of items recorded per survey event for each category. Higher values indicate items that tend to appear in large numbers when present.")
        avg_cat=df.groupby("trash_group").agg(total=("n","sum"),events=("event_id","nunique")).reset_index()
        avg_cat["avg_per_event"]=(avg_cat["total"]/avg_cat["events"]).round(2)
        avg_cat=avg_cat.sort_values("avg_per_event")
        fig=px.bar(avg_cat,x="avg_per_event",y="trash_group",orientation="h",color_discrete_sequence=[C["brick"]])
        fb(fig,"Avg Items / Event",None,h=max(360,26*len(avg_cat))); show(fig,"cat_avg")
        card_close()

    section_title("Full Item-Level Breakdown")
    st.markdown('<div class="sec-sub">Every individual item type in the database with its total count, percentage of all items, and average per record. Use this table to identify rare vs. common items.</div>', unsafe_allow_html=True)
    item_tbl=df.groupby(["trash_group","trash_item"])["n"].agg(Total="sum",Records="count",Average="mean").reset_index()
    item_tbl["% of Total"]=(100*item_tbl["Total"]/max(total_all,1)).round(2)
    item_tbl=item_tbl.sort_values("Total",ascending=False).round(2).reset_index(drop=True)
    item_tbl.index=range(1,len(item_tbl)+1)
    item_tbl.columns=["Category","Item","Total Count","# Records","Avg per Record","% of Total"]
    st.dataframe(item_tbl, use_container_width=True, height=520)
    tbl_note("'Records' = number of data entries for that specific item. 'Avg per Record' = mean count when that item is recorded (including zeros only if explicitly entered). '% of Total' is relative to the current filter's total item count.")

    section_title("Category Group Summary")
    st.markdown('<div class="sec-sub">Rollup of item-level data to category group level. Ranks each group by total items, showing its relative importance in the survey record.</div>', unsafe_allow_html=True)
    grp_tbl=df.groupby("trash_group")["n"].agg(Total="sum",Records="count",Avg="mean").reset_index()
    grp_tbl["% of Total"]=(100*grp_tbl["Total"]/max(total_all,1)).round(1)
    grp_tbl["Rank"]=grp_tbl["Total"].rank(ascending=False).astype(int)
    grp_tbl=grp_tbl.sort_values("Total",ascending=False).round(2).reset_index(drop=True)
    grp_tbl.index=range(1,len(grp_tbl)+1)
    grp_tbl.columns=["Category","Total Items","# Records","Avg per Record","% of Total","Rank"]
    st.dataframe(grp_tbl, use_container_width=True, height=400)
    tbl_note("Rank 1 = most commonly recorded category by total item count.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# LOCATIONS
# ══════════════════════════════════════════════════════════════════
elif page == "Locations":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Locations & Sites</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Site-level analysis of trash burden across all recorded survey locations. Use this page to identify high-priority sites, compare segments, and understand survey coverage by location.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="loc", cats=False)
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)
    site_st=df.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),
        mean=("n","mean"),mx=("n","max"),mn_v=("n","min"),sd=("n","std")).reset_index()
    site_st["avg_per_event"]=(site_st["total"]/site_st["events"]).round(1)
    site_st["sd"]=site_st["sd"].fillna(0).round(1)
    site_st=site_st.sort_values("total",ascending=False).reset_index(drop=True)

    st.markdown(f"""<div class="stat-strip">
    <div class="stat-item"><span class="stat-v">{len(site_st)}</span><span class="stat-l">Total Locations</span></div>
    <div class="stat-item"><span class="stat-v">{int(site_st['total'].max()):,}</span><span class="stat-l">Max Items at One Site</span></div>
    <div class="stat-item"><span class="stat-v">{site_st['avg_per_event'].mean():.1f}</span><span class="stat-l">Grand Avg / Event</span></div>
    <div class="stat-item"><span class="stat-v">{int(site_st['events'].max())}</span><span class="stat-l">Max Events at One Site</span></div>
    <div class="stat-item"><span class="stat-v">{int(site_st['events'].sum()):,}</span><span class="stat-l">Total Events (filtered)</span></div>
    </div>""", unsafe_allow_html=True)

    c1,c2=st.columns([3,2])
    with c1:
        card_open("Top 30 Locations by Total Items Recorded",
                  "Horizontal bar chart colored by river segment assignment. Locations labeled 'Other' are not assigned to a named segment.")
        t30=site_st.head(30).sort_values("total")
        fig=px.bar(t30,x="total",y="site_label",orientation="h",color="seg" if "seg" in t30.columns else None,color_discrete_map=SEG_COLORS)
        fb(fig,"Total Items",None,h=max(520,22*len(t30))); show(fig,"loc_top")
        card_close()
    with c2:
        card_open("Total Items by River Segment",
                  "Aggregate comparison of total items across the four named river segments. Sites not assigned to a segment are excluded.")
        seg_tot=df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["n"].sum().reset_index()
        fig=px.bar(seg_tot,x="seg",y="n",color="seg",color_discrete_map=SEG_COLORS,category_orders={"seg":SEG_ORDER})
        fb(fig,"Segment","Total Items",h=260,leg=False); show(fig,"loc_seg")
        card_close()

        card_open("Survey Frequency by Segment",
                  "Number of distinct survey events conducted within each named river segment.")
        seg_ev=df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["event_id"].nunique().reset_index(name="events")
        fig=px.bar(seg_ev,x="seg",y="events",color="seg",color_discrete_map=SEG_COLORS)
        fb(fig,"Segment","# Events",h=240,leg=False); show(fig,"loc_segev")
        card_close()

    c3,c4=st.columns(2)
    with c3:
        card_open("Average Items Per Event — Top 20 Locations",
                  "Ranks locations by their per-event average rather than cumulative total. A site visited only once with 200 items ranks higher than a site visited 10 times with 50 items each.")
        top20_avg=site_st.nlargest(20,"avg_per_event").sort_values("avg_per_event")
        fig=px.bar(top20_avg,x="avg_per_event",y="site_label",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
        fb(fig,"Avg Items / Event",None,h=max(420,22*len(top20_avg))); show(fig,"loc_avg")
        card_close()
    with c4:
        card_open("Events per Location — Survey Coverage Distribution",
                  "Histogram showing how many survey events each location has received. Most locations are visited only 1–3 times; a few core sites are surveyed repeatedly.")
        fig=px.histogram(site_st,x="events",nbins=20,color_discrete_sequence=[C["sage"]])
        fig.add_vline(x=site_st["events"].mean(),line_dash="dot",line_color=C["brick"],annotation_text=f"Mean: {site_st['events'].mean():.1f}",annotation_font_size=11)
        fb(fig,"# Events per Location","# Locations",h=320); show(fig,"loc_hist")
        card_close()

    seg_filter=st.selectbox("Filter table by River Segment",["All"]+SEG_ORDER[:-1])

    section_title("Complete Location Statistics Table")
    st.markdown('<div class="sec-sub">All survey locations with full summary statistics. Sort any column by clicking its header.</div>', unsafe_allow_html=True)
    filtered_st=site_st if seg_filter=="All" else site_st[site_st["seg"]==seg_filter]
    disp=filtered_st[["site_label","seg","total","events","avg_per_event","mean","sd","mx","mn_v"]].copy()
    disp.columns=["Location","Segment","Total Items","# Events","Avg/Event","Mean Count","Std Dev","Max","Min"]
    disp=disp.round(1).reset_index(drop=True); disp.index=range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=540)
    tbl_note("'Mean Count' and 'Std Dev' refer to the distribution of individual count records for that location, not event-level totals. 'Avg/Event' is the more interpretable metric for comparing trash burden across sites.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# DATA TABLE
# ══════════════════════════════════════════════════════════════════
elif page == "Data Table":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Data Table</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Browse and explore the complete raw dataset. Every record in the database is shown here. Use the filters to narrow down by segment, location, category, or date range.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=True):
        lf=render_filters(long, kp="dt")
    stat_strip(long,lf)

    section_title("Raw Survey Records")
    st.markdown('<div class="sec-sub">One row per trash item category per survey event. Use column headers to sort. Maximum 5,000 rows displayed.</div>', unsafe_allow_html=True)
    cols=[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in lf.columns]
    rename={"event_id":"Event ID","date":"Date","seg":"Segment","site_label":"Location",
            "trash_group":"Category","trash_item":"Item","n":"Count","surveyed_m2":"Area (m2)","recorder":"Recorder"}
    disp=lf[cols].rename(columns=rename).sort_values(["Date","Event ID"],na_position="last").head(5000)
    disp.index=range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=560)
    tbl_note(f"Showing {min(len(lf),5000):,} of {len(lf):,} rows matching current filters. Each row represents one item type recorded at one survey event. To see all data, export as CSV from the Export page.")

    section_title("Filtered Summary — Category Breakdown")
    st.markdown('<div class="sec-sub">Aggregated view of the filtered records above, grouped by trash category.</div>', unsafe_allow_html=True)
    sum_cat=lf.groupby("trash_group")["n"].agg(Total="sum",Records="count").reset_index()
    sum_cat["% of Filtered Total"]=(100*sum_cat["Total"]/max(sum_cat["Total"].sum(),1)).round(1)
    sum_cat=sum_cat.sort_values("Total",ascending=False).reset_index(drop=True)
    sum_cat.index=range(1,len(sum_cat)+1)
    sum_cat.columns=["Category","Total Items","# Records","% of Filtered Total"]
    st.dataframe(sum_cat, use_container_width=True, height=360)
    tbl_note("This table summarizes the filtered records shown above. Change the filters to update both this table and the raw records.")

    section_title("Filtered Summary — Location Breakdown")
    st.markdown('<div class="sec-sub">Aggregated view of the filtered records grouped by survey location.</div>', unsafe_allow_html=True)
    sum_loc=lf.groupby(["site_label","seg"]).agg(Total=("n","sum"),Events=("event_id","nunique")).reset_index()
    sum_loc["Avg/Event"]=(sum_loc["Total"]/sum_loc["Events"]).round(1)
    sum_loc=sum_loc.sort_values("Total",ascending=False).reset_index(drop=True)
    sum_loc.index=range(1,len(sum_loc)+1)
    sum_loc.columns=["Location","Segment","Total Items","# Events","Avg Items/Event"]
    st.dataframe(sum_loc, use_container_width=True, height=380)
    tbl_note("This table shows the same filtered records aggregated by location. Useful for seeing which sites are most represented in the current filter selection.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# DATA ENTRY
# ══════════════════════════════════════════════════════════════════
elif page == "Data Entry":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">New Survey Entry</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Submit a completed field survey directly into the cloud database. Data is saved immediately and reflected in all charts and tables. Double-check all values before submitting — entries cannot be deleted from this interface.</div>', unsafe_allow_html=True)

    with st.form("survey_form", clear_on_submit=False):
        st.markdown('<div class="form-sec"><div class="form-sec-title">Event Information</div>', unsafe_allow_html=True)
        ec1,ec2,ec3,ec4=st.columns(4)
        event_id=ec1.text_input("Event ID",placeholder="e.g. 396")
        survey_date=ec2.date_input("Survey Date",value=date.today())
        area_m2=ec3.number_input("Plot Area (m²)",min_value=0.0,value=10.0,step=0.5)
        recorder=ec4.selectbox("Recorder",[""] + TEAM + ["Other — type below"])
        ec5,ec6=st.columns([2,2])
        existing=sorted(long["site_label"].dropna().astype(str).unique().tolist())
        site_sel=ec5.selectbox("Survey Location (existing)",[""] + existing)
        site_new=ec6.text_input("Or enter a new location name")
        rec_other=""
        if recorder=="Other — type below": rec_other=st.text_input("Recorder full name")
        st.markdown('</div>', unsafe_allow_html=True)

        recorder_final=rec_other.strip() if rec_other.strip() else (recorder if recorder else "")
        site_final=site_new.strip() if site_new.strip() else site_sel

        st.markdown('<div class="form-sec"><div class="form-sec-title">Trash Item Counts — Enter the count for each item found. Leave at 0 if not present.</div>', unsafe_allow_html=True)
        counts={}
        for grp_name,items in TRASH_GROUPS.items():
            st.markdown(f'<div class="grp-hdr">{grp_name}</div>', unsafe_allow_html=True)
            n=min(4,len(items)); cols=st.columns(n)
            for i,item in enumerate(items):
                with cols[i%n]: counts[item]=st.number_input(item,min_value=0,value=0,step=1,key=f"c_{grp_name}_{item}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-sec"><div class="form-sec-title">Field Notes (optional)</div>', unsafe_allow_html=True)
        st.text_area("Observations, site conditions, notable findings",height=90,placeholder="e.g. Recent flooding, concentrated debris near outfall, unusual items found...")
        st.markdown('</div>', unsafe_allow_html=True)

        total_preview=sum(counts.values())
        st.markdown(f'<div class="live-total"><div class="live-total-n">{total_preview:,}</div><div class="live-total-l">total items counted in this entry</div></div>', unsafe_allow_html=True)
        submitted=st.form_submit_button("Save Survey Entry to Database",use_container_width=True)

    if submitted:
        if not event_id.strip(): st.error("Event ID is required.")
        elif not site_final: st.error("Survey location is required.")
        else:
            try:
                sb=get_sb()
                sb.table("site_events").upsert({"event_id":int(event_id.strip()),"date_site":survey_date.isoformat(),
                    "site_label":site_final,"location_description":site_final,
                    "recorder":recorder_final,"surveyed_m2":float(area_m2) if area_m2 else None}).execute()
                rows=[{"event_id":int(event_id.strip()),"trash_group":g,"trash_item":item,"count_value":float(v)}
                      for g,items in TRASH_GROUPS.items() for item in items if (v:=counts.get(item,0)) and v>0]
                if rows: sb.table("trash_counts").insert(rows).execute()
                load_data.clear()
                st.success(f"Saved — Event {event_id} · {site_final} · {survey_date.strftime('%B %d, %Y')} · {total_preview:,} items")
            except Exception as e: st.error(f"Could not save: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════
elif page == "Export":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Export Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Download clean, formatted datasets from the live database. All three formats are ready to open in Excel, Google Sheets, R, Python, or ArcGIS.</div>', unsafe_allow_html=True)

    long_exp=long[[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in long.columns]].copy()
    long_exp=long_exp.rename(columns={"n":"count","seg":"river_segment","site_label":"location"})

    et_exp=make_et(long)

    site_exp=long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),avg=("n","mean")).reset_index()
    site_exp=site_exp.sort_values("total",ascending=False)

    exports=[
        ("Long Format — Every Record",long_exp,"scr_trash_long_format.csv",
         "One row per item category per survey event. The most complete format — best for custom analysis in R, Python, or Excel pivot tables. Contains every count entry with its associated location, date, and segment.",
         f"{len(long_exp):,} rows · {len(long_exp.columns)} columns"),
        ("Event Totals",et_exp,"scr_trash_event_totals.csv",
         "One row per survey event with total item count and density (items/m² where area data is available). Best for comparing events or plotting overall trends without needing item-level detail.",
         f"{len(et_exp):,} rows · {len(et_exp.columns)} columns"),
        ("Site Summary",site_exp,"scr_trash_site_summary.csv",
         "One row per survey location with total items, number of events, and average. Best for spatial analysis, prioritizing cleanup sites, or importing into GIS software.",
         f"{len(site_exp):,} rows · {len(site_exp.columns)} columns"),
    ]
    for label,df_exp,fname,desc,sz in exports:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        ec1,ec2=st.columns([3,1])
        with ec1:
            st.markdown(f'<div class="sec-hd">{label}</div><div class="sec-sub">{desc}</div>', unsafe_allow_html=True)
            st.caption(sz)
        with ec2:
            if df_exp is not None and len(df_exp)>0:
                st.download_button("Download CSV",data=df_exp.to_csv(index=False).encode(),
                    file_name=fname,mime="text/csv",use_container_width=True,key=f"dl_{fname}")
        if df_exp is not None and len(df_exp)>0:
            with st.expander("Preview first 30 rows"):
                st.dataframe(df_exp.head(30), use_container_width=True, height=220)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────
st.markdown(f"""<div class="ftr"><div class="ftr-in">
  <div style="display:flex;align-items:center;gap:16px;">
    <img src="{LOGO_W}" style="height:30px;opacity:.8;">
    <div class="ftr-copy"><strong style="color:rgba(255,255,255,.7);display:block;">Sonoran Institute</strong>
    5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711 · (520) 290-0828</div>
  </div>
  <div class="ftr-copy" style="text-align:right;">
    <a href="https://sonoraninstitute.org/card/santacruz/" class="ftr-a">Santa Cruz River Program</a><br>
    Dashboard v5.0 · Cloud Edition
  </div>
</div></div>""", unsafe_allow_html=True)

with st.expander("Account"):
    st.write(f"Signed in as **{prof.get('full_name','')}** ({prof.get('username','')})")
    c1,c2=st.columns(2)
    with c1:
        if st.button("Refresh Data"): load_data.clear(); st.rerun()
    with c2:
        if st.button("Sign Out"):
            st.session_state["auth"]=False; st.session_state["prof"]=None; st.rerun()
