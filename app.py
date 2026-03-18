# ══════════════════════════════════════════════════════════════════
# Santa Cruz River Trash Survey Dashboard  v4.0
# Sonoran Institute — River Restoration Program
# Supabase backend · Native Streamlit navigation (no hacks)
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

# ──────────────────────────────────────────────────────────────────
# SUPABASE
# ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_sb() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ──────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────
LOGO_W = "https://sonoraninstitute.org/wp-content/themes/sonoran-institute-2016/assets/img/si_logo_white_2018.png"

RIVER_SEGMENTS = {
    "North Reach":   ["Santa Cruz River North of CoCerro","Between an outfall and Camino del Cerro","between an outfall and Camino del Cerro","Santa Cruz River at Camino del Cerro","Silverlake Bridge on Santa Cruz"],
    "Central Reach": ["W side of Cushing St. bridge, north of the bridge at outfall","outfall CW Cushing, North side","Midway between Cushing and Congress, northern site","Midway between Cushing and Congress, southern site","Midway Curshing and congress","South of Trail's end wash"],
    "South Reach":   ["South of Speedway (St. Mary's) (West)","Speedway and St. Mary","Santa Cruz river, Drexel and Irvington","Santa Cruz river, Drexel and irvington","drexel"],
    "Rillito":       ["Rillito at Country Club","Arcadia wash","Arcadia Wash between speedway"],
}
SEG_ORDER  = ["North Reach","Central Reach","South Reach","Rillito","Other"]
SEG_COLORS = {"North Reach":"#2980b9","Central Reach":"#27ae60","South Reach":"#e67e22","Rillito":"#8e44ad","Other":"#7f8c8d"}
SEG_LIGHT  = {"North Reach":"#d6eaf8","Central Reach":"#d5f5e3","South Reach":"#fdebd0","Rillito":"#e8daef","Other":"#f0f0f0"}

TRASH_GROUPS = {
    "Cups":          ["Styrofoam (Polar Pop)","Styrofoam (Qt)","Styrofoam (other)","Plastic","Paper"],
    "Beer":          ["Bottles","Cans"],
    "Liquor":        ["Plastic bottles","Glass"],
    "Soda":          ["Bottles","Cans"],
    "Water":         ["Bottles"],
    "Sports drinks": ["Bottles","Cans"],
    "Juice":         ["Bottles","Cans"],
    "Food packaging":["Food wrappers (candy, etc.)","Non-cup styrofoam","Non-cup plastic","Non-cup paper (bags, boxes)","Straws","6-pack rings","Plates and bowls plastic","Cans, milk jugs, mixes","Plates, styrofoam","Utensils","Misc"],
    "Nicotine":      ["cigs, cigars, lighters, dip, packs"],
    "Toiletries":    ["Toiletries","Packaging"],
    "Rx, drugs":     ["Rx and drug packaging","Syringes, paraphernalia"],
    "Toys, games":   ["Balls, games","CD, DVD, electronic packaging","School/office supplies","ID cards, credit cards","Batteries"],
    "Paper litter":  ["News, books, magazines","Advertising, signs, cards"],
    "Clothing":      ["Clothes, shoes, hats","PPE","Misc. fabric"],
    "Auto":          ["Car parts (small)","Car parts (large)","Tires"],
    "Construction":  ["Small items","Large items"],
    "Appliances":    ["Bikes, bike parts","Furniture/cushions/pillows","Shopping carts","Carpet","Rope/line","Buckets","Appliances"],
    "Plastic bags":  ["Plastic bags"],
    "Misc":          ["Sm. debris (ex. metal, plastic scraps)","Lg. debris (ex. garbage cans)"],
}

TEAM = [
    "Luke Cole","Sofia Angkasa","Kimberly Stanley","Marie Olson","S. Griset",
    "Soroush Hedayah","Vata Aflatoone","Kimberly Baeza","Joan Woodward",
    "Mark Krieski","Jamie Irby","Marsha Colbert","Axhel Munoz","Christine Hehenga",
    "Saige Thompson","Stephanie Winick","Damon Shorty","Julia Olson",
    "Isabella Feldmann","KyeongHee Kim","Joe Cuffori","Brian Jones",
]

PAGES = ["🏠 Overview","🗺 Map","📈 Trends","📦 Categories","📍 Locations","📋 Data Table","✏️ Data Entry","⬇️ Export"]

C = dict(
    forest="#13291a", green="#1e4d1e", sage="#2d6a2d", mint="#5da832",
    cream="#faf7f0", sand="#f2ede2", sand2="#e8e1d0", sand3="#d8ceba",
    gold="#c9820e", amber="#e8a620", earth="#8b4513", brick="#b5451b",
    sky="#1a5276", water="#2471a3",
    text="#18180f", med="#3a3a28", muted="#686854", divider="#cec6b0", white="#ffffff",
)
PAL = [C["green"],C["water"],C["brick"],C["amber"],C["sage"],"#6c4f8a","#2e8b8b",C["mint"],"#888877",C["earth"]]

st.set_page_config(
    page_title="SCR Trash Survey · Sonoran Institute",
    page_icon="🌊", layout="wide",
    initial_sidebar_state="collapsed",
)
PLOTLY_CFG = {"displaylogo":False,"modeBarButtonsToRemove":["lasso2d","select2d","autoScale2d","pan2d"]}

# ──────────────────────────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">""", unsafe_allow_html=True)
    st.markdown(f"""<style>
html,body,[class*="css"]{{font-family:'DM Sans',sans-serif;color:{C["text"]};}}
.stApp{{background:{C["sand"]};}}
.block-container{{padding:0!important;max-width:100%!important;}}
[data-testid="stSidebar"],[data-testid="collapsedControl"]{{display:none!important;}}

/* ── HEADER ── */
.hdr{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 55%,{C["sage"]} 100%);
      border-bottom:2px solid {C["mint"]};box-shadow:0 4px 32px rgba(0,0,0,.22);}}
.hdr-in{{max-width:1480px;margin:0 auto;padding:15px 44px;
         display:flex;align-items:center;justify-content:space-between;}}
.hdr-brand{{display:flex;align-items:center;gap:18px;}}
.hdr-logo{{height:42px;}}
.hdr-name{{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;
           color:#fff;line-height:1.2;letter-spacing:-.01em;}}
.hdr-sub{{font-size:9.5px;color:rgba(255,255,255,.45);letter-spacing:2px;
          text-transform:uppercase;margin-top:3px;font-family:'DM Mono',monospace;}}
.hdr-right{{text-align:right;}}
.hdr-user{{font-size:13px;color:rgba(255,255,255,.7);line-height:1.6;}}
.hdr-user strong{{color:#fff;font-size:14px;display:block;font-weight:600;}}
.hdr-pill{{display:inline-flex;align-items:center;gap:5px;background:{C["mint"]}20;
           border:1px solid {C["mint"]}44;border-radius:20px;padding:2px 10px;
           font-size:10px;color:{C["mint"]};font-family:'DM Mono',monospace;
           letter-spacing:.5px;margin-top:3px;}}
.hdr-dot{{width:6px;height:6px;background:{C["mint"]};border-radius:50%;
          animation:pulse 2s infinite;display:inline-block;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.4;}}}}

/* ── NAV — native Streamlit radio styled as nav bar ── */
.nav-wrap{{background:{C["forest"]};position:sticky;top:0;z-index:200;
           border-bottom:1px solid rgba(255,255,255,.06);}}
.nav-wrap > div > div > div[data-testid="stHorizontalBlock"]{{
    max-width:1480px!important;margin:0 auto!important;padding:0 40px!important;
    gap:0!important;
}}
div[role="radiogroup"]{{display:flex;gap:0;flex-wrap:nowrap;background:{C["forest"]};
                        padding:0!important;border:none!important;}}
div[role="radiogroup"] label{{
    padding:13px 18px!important;font-size:11px!important;font-weight:600!important;
    letter-spacing:1px!important;text-transform:uppercase!important;
    color:rgba(255,255,255,.45)!important;border-bottom:3px solid transparent!important;
    cursor:pointer!important;white-space:nowrap!important;transition:all .18s!important;
    font-family:'DM Sans',sans-serif!important;background:transparent!important;
    border-radius:0!important;margin:0!important;
}}
div[role="radiogroup"] label:hover{{
    color:rgba(255,255,255,.85)!important;
    background:rgba(255,255,255,.04)!important;
    border-bottom-color:rgba(255,255,255,.2)!important;
}}
div[role="radiogroup"] label[data-selected="true"],
div[role="radiogroup"] [aria-checked="true"] ~ label,
div[role="radiogroup"] input:checked + label,
div[role="radiogroup"] input[type=radio]:checked + div {{
    color:{C["mint"]}!important;
    border-bottom-color:{C["mint"]}!important;
    background:rgba(93,168,50,.08)!important;
}}
div[role="radiogroup"] [data-baseweb="radio"] > label{{
    color:rgba(255,255,255,.45)!important;
}}
div[role="radiogroup"] input{{display:none!important;}}
div[role="radiogroup"] [data-baseweb="radio"]{{background:transparent!important;}}
/* hide the radio dot */
div[role="radiogroup"] span[data-testid="stMarkdownContainer"]{{display:none!important;}}
div[role="radiogroup"] > label > div:first-child{{display:none!important;}}
/* active state via Streamlit's selection */
div[role="radiogroup"] label[aria-pressed="true"]{{
    color:{C["mint"]}!important;
    border-bottom-color:{C["mint"]}!important;
    background:rgba(93,168,50,.08)!important;
}}

/* ── BODY ── */
.body{{max-width:1480px;margin:0 auto;padding:36px 44px 100px;}}

/* ── TYPOGRAPHY ── */
.pg-title{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:700;
           color:{C["green"]};letter-spacing:-.02em;line-height:1.15;margin-bottom:6px;}}
.pg-lead{{font-size:14px;color:{C["muted"]};line-height:1.8;max-width:760px;margin-bottom:28px;}}
.sec-title{{font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:600;
            color:{C["text"]};margin-bottom:2px;}}
.sec-sub{{font-size:11.5px;color:{C["muted"]};margin-bottom:14px;}}

/* ── KPI GRID ── */
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px;}}
.kpi-grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px;}}
.kpi{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
      padding:20px 22px 16px;position:relative;overflow:hidden;
      box-shadow:0 2px 10px rgba(0,0,0,.04);transition:box-shadow .2s,transform .2s;}}
.kpi:hover{{box-shadow:0 8px 32px rgba(0,0,0,.1);transform:translateY(-2px);}}
.kpi::after{{content:'';position:absolute;top:0;left:0;right:0;height:3px;
             background:linear-gradient(90deg,{C["green"]},{C["mint"]});}}
.kpi-lbl{{font-size:9.5px;text-transform:uppercase;letter-spacing:1.8px;
          color:{C["muted"]};font-weight:700;margin-bottom:9px;
          font-family:'DM Mono',monospace;}}
.kpi-val{{font-family:'Cormorant Garamond',serif;font-size:2.3rem;font-weight:700;
          color:{C["green"]};line-height:1;letter-spacing:-.02em;}}
.kpi-val.sm{{font-size:1.25rem;padding-top:6px;line-height:1.3;}}
.kpi-note{{font-size:11px;color:{C["muted"]};margin-top:5px;}}

/* ── CARDS ── */
.card{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
       padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.04);}}
.card-hd{{display:flex;align-items:flex-start;justify-content:space-between;
          padding-bottom:14px;margin-bottom:18px;border-bottom:1px solid {C["sand3"]};}}

/* ── SECTION DIVIDER ── */
.sec-divider{{border:none;border-top:1px solid {C["sand3"]};margin:28px 0;}}

/* ── DATA TABLE ── */
div[data-testid="stDataFrame"]{{border:1px solid {C["sand3"]};border-radius:8px;overflow:hidden;}}

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
.live-total-n{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;
               font-weight:700;color:{C["green"]};}}
.live-total-l{{font-size:12px;color:{C["muted"]};}}

/* ── INPUTS ── */
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,
.stDateInput>div>div,.stTextInput>div>div,.stNumberInput>div>div,.stTextArea>div>div{{
  background:#fff!important;border:1.5px solid {C["sand3"]}!important;
  border-radius:7px!important;font-size:13.5px!important;
  font-family:'DM Sans',sans-serif!important;transition:border-color .15s!important;}}
div[data-baseweb="select"]>div:focus-within,div[data-baseweb="input"]>div:focus-within{{
  border-color:{C["sage"]}!important;box-shadow:0 0 0 3px {C["mint"]}1a!important;}}
label{{font-size:12px!important;font-weight:600!important;
       color:{C["med"]}!important;letter-spacing:.3px!important;}}

/* ── BUTTONS ── */
.stButton>button{{font-family:'DM Sans',sans-serif!important;font-size:12.5px!important;
  font-weight:600!important;padding:8px 18px!important;border-radius:7px!important;
  border:1.5px solid {C["sand3"]}!important;background:#fff!important;
  color:{C["med"]}!important;transition:all .15s!important;}}
.stButton>button:hover{{background:{C["green"]}!important;border-color:{C["green"]}!important;
  color:#fff!important;box-shadow:0 4px 14px {C["green"]}40!important;}}
.stDownloadButton>button{{background:{C["green"]}!important;color:#fff!important;
  border-color:{C["green"]}!important;border-radius:7px!important;font-weight:600!important;
  box-shadow:0 2px 8px {C["green"]}30!important;}}

/* ── SEGMENT CHIPS ── */
.chip{{display:inline-block;padding:2px 9px;border-radius:20px;font-size:10px;
       font-weight:700;letter-spacing:.8px;text-transform:uppercase;
       font-family:'DM Mono',monospace;margin:2px;}}
.chip-north{{background:{SEG_LIGHT["North Reach"]};color:{SEG_COLORS["North Reach"]};border:1px solid {SEG_COLORS["North Reach"]}55;}}
.chip-central{{background:{SEG_LIGHT["Central Reach"]};color:{SEG_COLORS["Central Reach"]};border:1px solid {SEG_COLORS["Central Reach"]}55;}}
.chip-south{{background:{SEG_LIGHT["South Reach"]};color:{SEG_COLORS["South Reach"]};border:1px solid {SEG_COLORS["South Reach"]}55;}}
.chip-rillito{{background:{SEG_LIGHT["Rillito"]};color:{SEG_COLORS["Rillito"]};border:1px solid {SEG_COLORS["Rillito"]}55;}}

/* ── STAT STRIP ── */
.stat-strip{{display:flex;gap:0;background:#fff;border:1px solid {C["sand3"]};
             border-radius:10px;overflow:hidden;margin-bottom:24px;
             box-shadow:0 2px 10px rgba(0,0,0,.04);}}
.stat-item{{flex:1;padding:18px 20px;border-right:1px solid {C["sand3"]};text-align:center;}}
.stat-item:last-child{{border-right:none;}}
.stat-v{{font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:700;
         color:{C["green"]};display:block;line-height:1.1;}}
.stat-l{{font-size:9.5px;color:{C["muted"]};font-family:'DM Mono',monospace;
         text-transform:uppercase;letter-spacing:.8px;margin-top:3px;display:block;}}

/* ── BANNER ── */
.banner{{background:{C["sky"]}0f;border:1px solid {C["sky"]}30;
         border-left:4px solid {C["sky"]};border-radius:0 8px 8px 0;
         padding:11px 15px;margin-bottom:18px;font-size:13px;color:{C["sky"]};}}

/* ── FOOTER ── */
.ftr{{background:linear-gradient(165deg,{C["forest"]} 0%,{C["green"]} 100%);
      padding:24px 44px;margin-top:80px;border-top:2px solid {C["sage"]};}}
.ftr-in{{max-width:1480px;margin:0 auto;display:flex;align-items:center;
         justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.ftr-copy{{color:rgba(255,255,255,.4);font-size:11px;line-height:1.8;
           font-family:'DM Mono',monospace;}}
.ftr-a{{color:rgba(255,255,255,.5);text-decoration:none;}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:{C["sand"]};}}
::-webkit-scrollbar-thumb{{background:{C["sand3"]};border-radius:3px;}}
::-webkit-scrollbar-thumb:hover{{background:{C["sage"]};}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(10px);}}to{{opacity:1;transform:none;}}}}
.fade-up{{animation:fadeUp .35s ease both;}}
</style>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# CHART HELPERS
# ──────────────────────────────────────────────────────────────────
def fig_base(fig, xt=None, yt=None, h=400, leg=True):
    fig.update_layout(
        height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=C["text"], size=12),
        margin=dict(l=6,r=6,t=36,b=6),
        legend=dict(bgcolor="rgba(255,255,255,.95)",bordercolor=C["divider"],borderwidth=1,
                    font=dict(size=11),orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1) if leg else dict(visible=False),
        xaxis_title=xt, yaxis_title=yt,
    )
    fig.update_xaxes(showgrid=False,zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    fig.update_yaxes(showgrid=True,gridcolor=C["sand2"],zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    return fig

def show(fig, key=None):
    st.plotly_chart(fig, config=PLOTLY_CFG, use_container_width=True, key=key)

def card(title, subtitle=""):
    sub = f'<div class="sec-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="card"><div class="card-hd"><div><div class="sec-title">{title}</div>{sub}</div></div>', unsafe_allow_html=True)

def card_end():
    st.markdown('</div>', unsafe_allow_html=True)

def empty_notice(msg="No data available."):
    st.info(msg)

# ──────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────
def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),100000).hex()

def register(username, password, full_name, position):
    u=username.strip()
    if len(u)<3: return False,"Username must be at least 3 characters."
    if len(password)<6: return False,"Password must be at least 6 characters."
    if not full_name.strip(): return False,"Full name required."
    if not position.strip(): return False,"Position required."
    salt=secrets.token_hex(16)
    try:
        get_sb().table("users").insert({"username":u,"password_hash":_hash(password,salt),
            "salt":salt,"full_name":full_name.strip(),"position_title":position.strip()}).execute()
        return True,"Account created — sign in."
    except Exception as e:
        return False,("Username taken." if "unique" in str(e).lower() or "duplicate" in str(e).lower() else str(e))

def login(username, password):
    try:
        r=get_sb().table("users").select("*").eq("username",username.strip()).execute()
        if not r.data: return False,None
        row=r.data[0]
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
    [data-testid="column"]:last-of-type .stButton>button{{background:white!important;color:{C["text"]}!important;border:1.5px solid {C["sand3"]}!important;border-radius:5px!important;font-weight:600!important;transition:all .15s!important;}}
    [data-testid="column"]:last-of-type .stButton>button:hover{{background:{C["green"]}!important;color:white!important;border-color:{C["green"]}!important;}}
    .auth-eyebrow{{font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:3px;text-transform:uppercase;color:{C["mint"]};margin-bottom:14px;}}
    .auth-title{{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:700;color:{C["text"]};letter-spacing:-.02em;line-height:1.1;margin-bottom:8px;}}
    .auth-sub{{font-size:13px;color:{C["muted"]};line-height:1.75;margin-bottom:32px;}}
    .auth-footer{{margin-top:24px;padding-top:16px;border-top:1px solid {C["sand3"]};font-size:11px;color:{C["muted"]};font-family:'DM Mono',monospace;display:flex;align-items:center;gap:8px;}}
    div[data-testid="stTabs"]>div:first-child{{background:transparent!important;border-bottom:1px solid {C["sand3"]}!important;padding:0!important;gap:0!important;margin-bottom:24px!important;}}
    div[data-testid="stTabs"] button[role="tab"]{{font-family:'DM Sans',sans-serif!important;font-size:11.5px!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:1px!important;color:{C["muted"]}!important;border-radius:0!important;padding:12px 20px 12px 0!important;border-bottom:2px solid transparent!important;background:transparent!important;}}
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{{color:{C["green"]}!important;border-bottom-color:{C["mint"]}!important;}}
    div[data-testid="stTabs"] div[role="tabpanel"]{{background:transparent!important;border:none!important;padding:0!important;box-shadow:none!important;}}
    </style>""", unsafe_allow_html=True)

    left_col, right_col = st.columns([1.1, 0.9])
    with left_col:
        components.html(f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,700;1,700&family=DM+Sans:wght@400;600&family=DM+Mono:wght@400&display=swap" rel="stylesheet">
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
        .brand-name{{font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:700;color:rgba(255,255,255,.88);line-height:1.25;}}
        .brand-sub{{font-family:'DM Mono',monospace;font-size:8px;color:rgba(255,255,255,.3);letter-spacing:2.5px;text-transform:uppercase;margin-top:3px;}}
        .hero{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:44px 0 36px;position:relative;z-index:2;}}
        .eyebrow{{display:flex;align-items:center;gap:12px;margin-bottom:20px;}}
        .eyebrow-line{{width:36px;height:1px;background:#5da832;}}
        .eyebrow-text{{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#5da832;}}
        .headline{{font-family:'Cormorant Garamond',serif;font-size:3.4rem;font-weight:700;line-height:1.06;color:white;letter-spacing:-.03em;margin-bottom:20px;}}
        .headline em{{font-style:italic;color:#5da832;}}
        .desc{{font-size:14px;color:rgba(255,255,255,.45);line-height:1.85;max-width:380px;margin-bottom:40px;}}
        .stats{{display:flex;gap:0;}}
        .stat{{padding:0 28px 0 0;}}
        .stat:first-child{{padding-left:0;}}
        .stat+.stat{{border-left:1px solid rgba(255,255,255,.1);padding-left:28px;}}
        .stat-num{{font-family:'Cormorant Garamond',serif;font-size:1.9rem;font-weight:700;color:white;line-height:1;letter-spacing:-.02em;}}
        .stat-lbl{{font-family:'DM Mono',monospace;font-size:9px;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:1.5px;margin-top:5px;}}
        .foot{{position:relative;z-index:2;font-family:'DM Mono',monospace;font-size:10px;color:rgba(255,255,255,.2);line-height:1.9;}}
        </style></head><body>
        <div class="brand"><img src="{LOGO_W}"><div><div class="brand-name">Sonoran Institute</div><div class="brand-sub">River Restoration Program</div></div></div>
        <div class="hero">
          <div class="eyebrow"><div class="eyebrow-line"></div><div class="eyebrow-text">Tucson, Arizona</div></div>
          <div class="headline">Santa Cruz River<br><em>Trash Survey</em></div>
          <div class="desc">Longitudinal monitoring of litter and debris along the Santa Cruz River corridor and tributaries. Plot-based surveys across multiple sites and reaches.</div>
          <div class="stats">
            <div class="stat"><div class="stat-num">395+</div><div class="stat-lbl">Events Logged</div></div>
          </div>
        </div>
        <div class="foot">Program Director: Luke Cole<br>sonoraninstitute.org</div>
        </body></html>""", height=900, scrolling=False)

    with right_col:
        st.markdown(f"""
        <div class="auth-eyebrow">Authorized Personnel Only</div>
        <div class="auth-title">Sign in to<br>your account</div>
        <div class="auth-sub">Access the Santa Cruz River data dashboard,<br>field entry tools, and analysis reports.</div>
        """, unsafe_allow_html=True)
        t1,t2 = st.tabs(["Sign In","Create Account"])
        with t1:
            with st.form("_login"):
                un=st.text_input("Username")
                pw=st.text_input("Password",type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Sign In →",use_container_width=True):
                    ok,prof=login(un,pw)
                    if ok:
                        st.session_state["auth"]=True; st.session_state["prof"]=prof; st.rerun()
                    else: st.error("Invalid username or password.")
        with t2:
            with st.form("_reg"):
                c1,c2=st.columns(2)
                fn=c1.text_input("Full Name"); pos=c2.text_input("Position / Title")
                nu=st.text_input("Username (min 3 chars)")
                c3,c4=st.columns(2)
                p1=c3.text_input("Password (min 6 chars)",type="password")
                p2=c4.text_input("Confirm Password",type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Create Account",use_container_width=True):
                    if p1!=p2: st.error("Passwords don't match.")
                    else:
                        ok,msg=register(nu,p1,fn,pos)
                        (st.success if ok else st.error)(msg)
        st.markdown(f"""<div class="auth-footer"><span style="width:5px;height:5px;border-radius:50%;background:{C["mint"]};display:inline-block;"></span>Cloud database · Secured by Supabase</div>""",unsafe_allow_html=True)
    st.stop()

# ──────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load():
    sb=get_sb()
    se_raw=sb.table("site_events").select("*").execute().data or []
    tc_raw=sb.table("trash_counts").select("event_id,trash_group,trash_item,count_value").execute().data or []
    wt_raw=sb.table("weights_data").select("event_id,date_recorded,total_weight_oz").execute().data or []

    se=pd.DataFrame(se_raw)
    tc=pd.DataFrame(tc_raw) if tc_raw else pd.DataFrame(columns=["event_id","trash_group","trash_item","count_value"])
    wt=pd.DataFrame(wt_raw) if wt_raw else pd.DataFrame(columns=["event_id","date_recorded","total_weight_oz"])

    tc.rename(columns={"count_value":"n"},inplace=True)
    tc["n"]=pd.to_numeric(tc["n"],errors="coerce").fillna(0)

    long=tc.copy()
    if not se.empty and not long.empty:
        cols=[c for c in ["event_id","date_site","site_label","point_id","replicate_no","lat","lon","recorder","surveyed_m2"] if c in se.columns]
        long=long.merge(se[cols],on="event_id",how="left")

    long["date"]=pd.to_datetime(long.get("date_site",pd.NaT),errors="coerce")
    long["site_label"]=long.get("site_label",pd.Series("Unknown",index=long.index)).fillna("Unknown")
    for col,new in [("lat","lat"),("lon","lon")]:
        long[new]=pd.to_numeric(long.get(col,np.nan),errors="coerce") if col in long.columns else np.nan
    long["seg"]=long["site_label"].map({s:seg for seg,sites in RIVER_SEGMENTS.items() for s in sites}).fillna("Other")
    long["trash_group"]=long["trash_group"].fillna("Misc")
    long["trash_item"]=long["trash_item"].fillna("Unknown")

    if not wt.empty:
        wt["date"]=pd.to_datetime(wt["date_recorded"],errors="coerce")
        wt.rename(columns={"total_weight_oz":"weight_oz"},inplace=True)

    return long, se, wt

def ev_totals(long):
    if long.empty: return pd.DataFrame()
    g=[c for c in ["event_id","date","site_label","seg","surveyed_m2"] if c in long.columns]
    et=long.groupby(g,dropna=False)["n"].sum().reset_index(name="total")
    if "surveyed_m2" in et.columns:
        a=pd.to_numeric(et["surveyed_m2"],errors="coerce")
        et["per_m2"]=np.where(a>0,et["total"]/a,np.nan)
    return et

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
        seg=str(r.get(seg_col,"Other")) if seg_col else "Other"
        color=SEG_COLORS.get(seg,"#888") if seg_col else color_val(r.get(metric_col,np.nan),vmin,vmax)
        recs.append({"lat":float(r[lat]),"lon":float(r[lon]),"lbl":str(r[label_col]) if label_col in d.columns else "","popup":popup,"color":color})
    clat,clon=float(d[lat].mean()),float(d[lon].mean())
    leg_html="".join(f'<div class="li"><div class="ld" style="background:{c}"></div>{s}</div>' for s,c in SEG_COLORS.items() if s!="Other") if seg_col else ""
    html_src=f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{{height:{height}px;width:100%;margin:0;padding:0;font-family:'DM Sans',sans-serif;}}
.legend{{position:absolute;bottom:20px;right:20px;z-index:9999;background:rgba(255,255,255,.97);
padding:14px 18px;border-radius:8px;border:1px solid #d4ccc0;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);}}
.legend-title{{font-weight:700;margin-bottom:10px;color:#1e4d1e;font-size:11px;text-transform:uppercase;letter-spacing:.8px;}}
.li{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px;}}
.ld{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
.leaflet-popup-content{{font-family:'DM Sans',sans-serif;font-size:13px;line-height:1.6;min-width:200px;}}
</style></head><body>
<div id="map"></div>
<div class="legend"><div class="legend-title">{"River Segments" if seg_col else "Trash Burden"}</div>
{leg_html if seg_col else '<div style="width:140px;height:8px;border-radius:2px;background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);margin-bottom:4px;"></div><div style="display:flex;justify-content:space-between;font-size:11px;color:#6b6b6b;"><span>Lower</span><span>Higher</span></div>'}
</div>
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
if(bounds.length>1) map.fitBounds(bounds,{{padding:[32,32]}});
</script></body></html>"""
    components.html(html_src, height=height+10)

# ──────────────────────────────────────────────────────────────────
# APP START
# ──────────────────────────────────────────────────────────────────
inject_css()
auth_gate()

prof=st.session_state.get("prof") or {}

# ── HEADER ──────────────────────────────────────────────────────
st.markdown(f"""
<div class="hdr"><div class="hdr-in">
  <div class="hdr-brand">
    <img src="{LOGO_W}" class="hdr-logo">
    <div><div class="hdr-name">Santa Cruz River Trash Survey</div>
         <div class="hdr-sub">Sonoran Institute · River Restoration Program</div></div>
  </div>
  <div class="hdr-right">
    <div class="hdr-user"><strong>{prof.get('full_name','')}</strong>{prof.get('position_title','')}</div>
    <div class="hdr-pill"><span class="hdr-dot"></span>&nbsp;Live Database</div>
  </div>
</div></div>""", unsafe_allow_html=True)

# ── NATIVE RADIO NAV ─────────────────────────────────────────────
st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
page = st.radio("nav", PAGES, horizontal=True, label_visibility="collapsed",
                key="page_nav")
st.markdown('</div>', unsafe_allow_html=True)

# ── LOAD DATA ────────────────────────────────────────────────────
with st.spinner("Loading from database…"):
    try:
        long, se, wt = load()
    except Exception as e:
        st.error(f"Database error: {e}"); st.stop()

et = ev_totals(long)

# ══════════════════════════════════════════════════════════════════
# ── OVERVIEW ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
if page == PAGES[0]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Santa Cruz River Trash Monitoring</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pg-lead">Longitudinal trash survey data collected along the Santa Cruz River corridor, Tucson, AZ. Plot-based surveys across {long["site_label"].nunique()} recorded locations. Program directed by <strong>Luke Cole</strong>, Sonoran Institute.</div>', unsafe_allow_html=True)

    # KPI strip
    total_n = int(long["n"].sum())
    n_events = long["event_id"].nunique()
    n_sites = long["site_label"].nunique()
    n_groups = long["trash_group"].nunique()
    d_min, d_max = long["date"].min(), long["date"].max()
    span = f"{d_min.strftime('%b %Y')} – {d_max.strftime('%b %Y')}" if pd.notna(d_min) and pd.notna(d_max) else "—"
    st.markdown(f"""<div class="kpi-grid">
    <div class="kpi"><div class="kpi-lbl">Total Items Recorded</div><div class="kpi-val">{total_n:,}</div><div class="kpi-note">all surveys combined</div></div>
    <div class="kpi"><div class="kpi-lbl">Survey Events</div><div class="kpi-val">{n_events:,}</div><div class="kpi-note">individual field visits</div></div>
    <div class="kpi"><div class="kpi-lbl">Unique Locations</div><div class="kpi-val">{n_sites:,}</div><div class="kpi-note">recorded site names</div></div>
    <div class="kpi"><div class="kpi-lbl">Trash Categories</div><div class="kpi-val">{n_groups}</div><div class="kpi-note">item groups tracked</div></div>
    <div class="kpi"><div class="kpi-lbl">Survey Period</div><div class="kpi-val sm">{span}</div><div class="kpi-note">date range</div></div>
    </div>""", unsafe_allow_html=True)

    # Row 1: timeline + donut
    c1, c2 = st.columns([3, 2])
    with c1:
        card("Items Recorded Over Time", "Monthly totals — gray bars = no survey that month")
        if "date" in long.columns:
            ts = long.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
            full = pd.date_range(ts["date"].min(), ts["date"].max(), freq="MS")
            ts = ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
            ts["gap"] = ts["n"].isna(); ts["n"] = ts["n"].fillna(0)
            ts["roll"] = ts["n"].rolling(3,min_periods=1).mean()
            fig = go.Figure()
            fig.add_bar(x=ts["date"], y=ts["n"], marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]], name="Monthly")
            fig.add_scatter(x=ts["date"], y=ts["roll"], name="3-mo avg", line=dict(color=C["amber"],width=2.5,dash="dot"), mode="lines")
            fig_base(fig,"Month","Items",h=300); show(fig,"ov_ts")
        card_end()
    with c2:
        card("Trash by Category", "Share of all recorded items")
        if "trash_group" in long.columns:
            grp = long.groupby("trash_group")["n"].sum().sort_values(ascending=False).head(10).reset_index()
            fig = px.pie(grp,values="n",names="trash_group",hole=.46,color_discrete_sequence=PAL)
            fig.update_traces(textposition="outside",textinfo="percent+label",textfont_size=10,pull=[.04]+[0]*9)
            fig.update_layout(height=300,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,margin=dict(l=10,r=10,t=10,b=10),font=dict(family="DM Sans"))
            show(fig,"ov_pie")
        card_end()

    # Row 2: top items + by location
    c3, c4 = st.columns([2, 3])
    with c3:
        card("Top 15 Most Common Items", "All-time total count")
        top = long.groupby("trash_item")["n"].sum().nlargest(15).reset_index().sort_values("n")
        fig = px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["water"]])
        fig_base(fig,"Count",None,h=400); show(fig,"ov_top")
        card_end()
    with c4:
        card("Items by River Segment", "Total items stacked by category across known reaches")
        if "seg" in long.columns and "trash_group" in long.columns:
            sg2 = long[long["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            sg2["seg"] = pd.Categorical(sg2["seg"],SEG_ORDER,ordered=True)
            fig = px.bar(sg2,x="seg",y="n",color="trash_group",barmode="stack",
                color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER})
            fig_base(fig,"Segment","Items",h=400); show(fig,"ov_seg")
        card_end()

    # Summary table
    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">📋 Quick Summary Table — Items by Category</div>', unsafe_allow_html=True)
    summary = long.groupby("trash_group")["n"].agg(Total="sum", Events=("count"), Avg=("mean")).reset_index()
    summary.columns = ["Category","Total Items","# Records","Avg per Record"]
    summary = summary.sort_values("Total Items",ascending=False).round(1)
    summary.index = range(1, len(summary)+1)
    st.dataframe(summary, use_container_width=True, height=360)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── MAP ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[1]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Survey Site Map</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">GPS locations of survey sites along the Santa Cruz River corridor. Click any marker for site details. Colors indicate river segment (left) or trash burden (right).</div>', unsafe_allow_html=True)

    map_mode = st.radio("Map view", ["By River Segment","By Trash Burden","All Events"], horizontal=True)

    # Build site-level aggregates
    site_agg = long.groupby(["site_label","seg"]).agg(
        total=("n","sum"), events=("event_id","nunique"),
        lat=("lat","mean"), lon=("lon","mean")
    ).reset_index()
    site_agg["avg_per_event"] = (site_agg["total"] / site_agg["events"]).round(1)

    m1,m2,m3,m4 = st.columns(4)
    with_coords = site_agg[site_agg["lat"].notna() & site_agg["lon"].notna()]
    m1.metric("Sites Mapped", len(with_coords))
    m2.metric("Total Sites in DB", len(site_agg))
    m3.metric("Events Mapped", int(with_coords["events"].sum()))
    m4.metric("Avg Items / Site", f"{site_agg['avg_per_event'].mean():.1f}" if len(site_agg)>0 else "—")

    if map_mode == "By River Segment":
        render_map(with_coords,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total",seg_col="seg")
    elif map_mode == "By Trash Burden":
        render_map(with_coords,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total",seg_col=None)
    else:
        ev_geo = et[et["lat"].notna() & et["lon"].notna()] if "lat" in et.columns else pd.DataFrame()
        if len(ev_geo)>0:
            render_map(ev_geo,"lat","lon","site_label",["event_id","site_label","date","total"],"total",seg_col="seg")
        else:
            st.info("Individual event coordinates not available in database.")

    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">📋 All Sites with Coordinates</div>', unsafe_allow_html=True)
    disp = with_coords[["site_label","seg","total","events","avg_per_event","lat","lon"]].copy()
    disp.columns = ["Site Name","River Segment","Total Items","# Events","Avg Items/Event","Latitude","Longitude"]
    disp = disp.sort_values("Total Items",ascending=False).reset_index(drop=True)
    disp.index = range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=400)
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── TRENDS ─────────────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[2]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Temporal Trends</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">How trash levels have changed over time — monthly, yearly, and seasonal patterns across the full survey record.</div>', unsafe_allow_html=True)

    df = long.copy()
    df["n"] = pd.to_numeric(df["n"],errors="coerce").fillna(0)
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["month_name"] = pd.Categorical(df["date"].dt.strftime("%b"),
        categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],ordered=True)

    # Row 1
    c1, c2 = st.columns(2)
    with c1:
        card("Monthly Items — Full Record", "Gray = no survey; gold line = 3-month rolling average")
        ts = df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
        full = pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
        ts = ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
        ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0); ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
        fig=go.Figure()
        fig.add_bar(x=ts["date"],y=ts["n"],marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],name="Monthly",opacity=.85)
        fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-mo avg",line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
        fig_base(fig,"Month","Items",h=320); show(fig,"tr_ts")
        card_end()
    with c2:
        card("Annual Totals by Year")
        yr = df.dropna(subset=["year"]).groupby("year")["n"].sum().reset_index()
        yr["year"] = yr["year"].astype(str)
        fig = px.bar(yr,x="year",y="n",color_discrete_sequence=[C["green"]],text="n")
        fig.update_traces(texttemplate="%{text:,}",textposition="outside")
        fig_base(fig,"Year","Total Items",h=320); show(fig,"tr_yr")
        card_end()

    # Row 2
    c3, c4 = st.columns(2)
    with c3:
        card("Month-by-Month Across Years", "Side-by-side comparison of same month across different years")
        md = df.dropna(subset=["year","month"]).groupby(["year","month","month_name"],observed=False)["n"].sum().reset_index()
        md["year_str"] = md["year"].astype(str)
        fig = px.bar(md,x="month_name",y="n",color="year_str",barmode="group",
            category_orders={"month_name":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]},
            color_discrete_sequence=PAL)
        fig_base(fig,"Month","Items",h=320); show(fig,"tr_mby")
        card_end()
    with c4:
        card("Average Items Per Survey Event", "Mean items per visit each month — dotted line = overall average")
        if not et.empty and "date" in et.columns:
            ev2 = et.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["total"].mean().reset_index(name="avg")
            fig = px.line(ev2,x="date",y="avg",markers=True,color_discrete_sequence=[C["water"]])
            fig.add_hline(y=ev2["avg"].mean(),line_dash="dot",line_color=C["earth"],
                annotation_text=f"Overall avg: {ev2['avg'].mean():.0f}",annotation_font_size=11)
            fig_base(fig,"Month","Avg Items / Event",h=320); show(fig,"tr_avg")
        card_end()

    # Weight
    if not wt.empty and "weight_oz" in wt.columns:
        card("Weight of Trash Collected Over Time (oz)", "Total weight recorded per month where data is available")
        dated = wt.dropna(subset=["weight_oz","date"])
        if len(dated)>0:
            wtrend = dated.groupby(pd.Grouper(key="date",freq="MS"))["weight_oz"].sum().reset_index()
            fig = px.bar(wtrend,x="date",y="weight_oz",color_discrete_sequence=[C["earth"]])
            fig_base(fig,"Month","Weight (oz)",h=280); show(fig,"tr_wt")
        card_end()

    # Summary table
    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">📋 Annual Summary Table</div>', unsafe_allow_html=True)
    ann = df.dropna(subset=["year"]).groupby("year")["n"].agg(
        Total="sum", Events=lambda x: long.loc[x.index,"event_id"].nunique() if "event_id" in long.columns else 0,
        Avg_per_event="mean"
    ).reset_index()
    ann.columns = ["Year","Total Items","Events","Avg per Record"]
    ann["Year"] = ann["Year"].astype(int)
    ann = ann.sort_values("Year",ascending=False).round(1).reset_index(drop=True)
    st.dataframe(ann, use_container_width=True, height=320)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── CATEGORIES ──────────────────────────────────────────════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[3]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Trash Categories</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Breakdown of all recorded items by category group and individual item type. Use the tables to explore totals, rankings, and proportions.</div>', unsafe_allow_html=True)

    df = long.copy()
    df["n"] = pd.to_numeric(df["n"],errors="coerce").fillna(0)

    # Row 1
    c1, c2 = st.columns([2,3])
    with c1:
        card("Category Totals", "All-time sum per trash group")
        ct = df.groupby("trash_group")["n"].sum().sort_values().reset_index()
        fig = px.bar(ct,x="n",y="trash_group",orientation="h",color_discrete_sequence=[C["green"]])
        fig_base(fig,"Total Items",None,h=max(380,28*len(ct))); show(fig,"cat_ct")
        card_end()
    with c2:
        card("Top 25 Individual Items", "Ranked by total count across all events")
        top = df.groupby("trash_item")["n"].sum().nlargest(25).reset_index().sort_values("n")
        fig = px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["sky"]])
        fig_base(fig,"Count",None,h=max(500,24*len(top))); show(fig,"cat_top")
        card_end()

    # Row 2
    c3, c4 = st.columns(2)
    with c3:
        card("Category Proportions", "% share of total items")
        ct2 = df.groupby("trash_group")["n"].sum().reset_index()
        fig = px.pie(ct2,values="n",names="trash_group",color_discrete_sequence=PAL,hole=.4)
        fig.update_traces(textposition="outside",textinfo="percent+label",textfont_size=10)
        fig.update_layout(height=380,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
            margin=dict(l=10,r=10,t=10,b=10),font=dict(family="DM Sans"))
        show(fig,"cat_pie")
        card_end()
    with c4:
        card("Category Trends Over Time", "Top 6 categories — quarterly totals")
        if "date" in df.columns:
            top6 = df.groupby("trash_group")["n"].sum().nlargest(6).index.tolist()
            ct3 = df[df["trash_group"].isin(top6)].groupby(
                ["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig = px.line(ct3,x="date",y="n",color="trash_group",markers=True,color_discrete_sequence=PAL)
            fig_base(fig,"Quarter","Items",h=380); show(fig,"cat_trend")
        card_end()

    # Full breakdown table
    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">📋 Full Item-Level Breakdown Table</div>', unsafe_allow_html=True)
    item_tbl = df.groupby(["trash_group","trash_item"])["n"].agg(
        Total="sum", Pct=lambda x: round(100*x.sum()/df["n"].sum(),2) if df["n"].sum()>0 else 0
    ).reset_index()
    item_tbl.columns = ["Category","Item","Total Count","% of All Items"]
    item_tbl = item_tbl.sort_values("Total Count",ascending=False).reset_index(drop=True)
    item_tbl.index = range(1,len(item_tbl)+1)
    st.dataframe(item_tbl, use_container_width=True, height=500)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── LOCATIONS ──────────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[4]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Locations & Sites</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Survey site performance — which locations have the most trash, how often they are surveyed, and how they compare across river segments.</div>', unsafe_allow_html=True)

    df = long.copy()
    df["n"] = pd.to_numeric(df["n"],errors="coerce").fillna(0)

    # Site stats
    site_stats = df.groupby(["site_label","seg"]).agg(
        total=("n","sum"), events=("event_id","nunique"),
        mean=("n","mean"), max=("n","max"), min=("n","min")
    ).reset_index()
    site_stats["avg_per_event"] = (site_stats["total"]/site_stats["events"]).round(1)
    site_stats = site_stats.sort_values("total",ascending=False).reset_index(drop=True)
    site_stats.index = range(1,len(site_stats)+1)

    # KPI strip
    st.markdown(f"""<div class="stat-strip">
    <div class="stat-item"><span class="stat-v">{len(site_stats)}</span><span class="stat-l">Total Locations</span></div>
    <div class="stat-item"><span class="stat-v">{site_stats['total'].max():,.0f}</span><span class="stat-l">Max Items at One Site</span></div>
    <div class="stat-item"><span class="stat-v">{site_stats['avg_per_event'].mean():.1f}</span><span class="stat-l">Grand Avg / Event</span></div>
    <div class="stat-item"><span class="stat-v">{site_stats['events'].max():.0f}</span><span class="stat-l">Max Events at One Site</span></div>
    </div>""", unsafe_allow_html=True)

    # Row 1
    c1, c2 = st.columns([3, 2])
    with c1:
        card("Top 30 Locations by Total Items Recorded")
        top_sites = site_stats.head(30).sort_values("total")
        fig = px.bar(top_sites,x="total",y="site_label",orientation="h",
            color="seg" if "seg" in top_sites.columns else None,
            color_discrete_map=SEG_COLORS)
        fig_base(fig,"Total Items",None,h=max(500,22*len(top_sites))); show(fig,"loc_top")
        card_end()
    with c2:
        card("Items by River Segment", "Segment totals — known sites only")
        seg_tot = df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["n"].sum().reset_index()
        seg_tot["seg"] = pd.Categorical(seg_tot["seg"],SEG_ORDER,ordered=True)
        fig = px.bar(seg_tot,x="seg",y="n",color="seg",color_discrete_map=SEG_COLORS,
            category_orders={"seg":SEG_ORDER})
        fig_base(fig,"Segment","Total Items",h=320,leg=False); show(fig,"loc_seg")

        st.markdown("---")
        card("Survey Frequency by Segment", "Number of events per segment")
        seg_ev = df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["event_id"].nunique().reset_index(name="events")
        fig2 = px.bar(seg_ev,x="seg",y="events",color="seg",color_discrete_map=SEG_COLORS)
        fig_base(fig2,"Segment","# Events",h=240,leg=False); show(fig2,"loc_segev")
        card_end()

    # Segment × category heatmap concept
    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">📋 All Locations — Full Statistics Table</div>', unsafe_allow_html=True)
    disp = site_stats.copy()
    disp.columns = ["Location","River Segment","Total Items","# Events","Mean per Record","Max in One Record","Min in One Record","Avg Items/Event"]
    disp = disp.round(1)
    st.dataframe(disp, use_container_width=True, height=540)

    # Filter by segment
    st.markdown("---")
    st.markdown('<div class="sec-title" style="margin-bottom:12px;">🔍 Filter Locations by River Segment</div>', unsafe_allow_html=True)
    seg_filter = st.selectbox("Select segment", ["All"] + SEG_ORDER[:-1])
    filtered = site_stats if seg_filter == "All" else site_stats[site_stats["seg"]==seg_filter]
    fdisp = filtered[["site_label","seg","total","events","avg_per_event"]].copy()
    fdisp.columns = ["Location","Segment","Total Items","# Events","Avg Items/Event"]
    fdisp = fdisp.reset_index(drop=True); fdisp.index = range(1,len(fdisp)+1)
    st.dataframe(fdisp, use_container_width=True, height=360)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── DATA TABLE ──────────────────────────────────────══════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[5]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Data Table</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Browse, search, and filter the raw survey data. Every record in the database is shown here. Use the filters to narrow down what you see.</div>', unsafe_allow_html=True)

    with st.expander("🔍 Filters", expanded=True):
        fc1,fc2,fc3,fc4 = st.columns(4)
        all_sites = sorted(long["site_label"].dropna().unique())
        all_segs  = sorted(long["seg"].dropna().unique()) if "seg" in long.columns else []
        all_grps  = sorted(long["trash_group"].dropna().unique())
        sel_sites = fc1.multiselect("Locations", all_sites, default=all_sites)
        sel_segs  = fc2.multiselect("Segments", all_segs, default=all_segs)
        sel_grps  = fc3.multiselect("Categories", all_grps, default=all_grps)
        mn,mx = long["date"].min(), long["date"].max()
        dr = fc4.date_input("Date Range", value=(mn.date(),mx.date())) if pd.notna(mn) and pd.notna(mx) else None

    f = long.copy()
    if sel_sites: f = f[f["site_label"].isin(sel_sites)]
    else: f = f.iloc[0:0]
    if sel_segs and "seg" in f.columns: f = f[f["seg"].isin(sel_segs)]
    if sel_grps: f = f[f["trash_group"].isin(sel_grps)]
    if dr and isinstance(dr,(tuple,list)) and len(dr)==2:
        s,e = dr
        f = f[f["date"].notna()&(f["date"].dt.date>=s)&(f["date"].dt.date<=e)]

    # Summary of filtered
    m1,m2,m3 = st.columns(3)
    m1.metric("Rows Shown", f"{min(len(f),5000):,}")
    m2.metric("Total Items in Filter", f"{int(f['n'].sum()):,}")
    m3.metric("Unique Events", f"{f['event_id'].nunique():,}")

    cols = [c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in f.columns]
    rename = {"event_id":"Event ID","date":"Date","seg":"Segment","site_label":"Location",
              "trash_group":"Category","trash_item":"Item","n":"Count","surveyed_m2":"Area (m²)","recorder":"Recorder"}
    disp = f[cols].rename(columns=rename).sort_values(["Date","Event ID"],na_position="last").head(5000)
    disp.index = range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=560)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── DATA ENTRY ──────────────────────────────────════════════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[6]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">New Survey Entry</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Submit a completed field survey directly into the cloud database. Data is saved immediately and appears in all charts. Double-check all values before submitting — entries cannot be deleted from this interface.</div>', unsafe_allow_html=True)

    with st.form("survey_form", clear_on_submit=False):
        st.markdown('<div class="form-sec"><div class="form-sec-title">📋 Event Information</div>', unsafe_allow_html=True)
        ec1,ec2,ec3,ec4 = st.columns(4)
        event_id    = ec1.text_input("Event ID", placeholder="e.g. 396")
        survey_date = ec2.date_input("Survey Date", value=date.today())
        area_m2     = ec3.number_input("Plot Area (m²)", min_value=0.0, value=10.0, step=0.5)
        rec_opts    = [""] + TEAM + ["Other — type below"]
        recorder    = ec4.selectbox("Recorder", rec_opts)
        ec5,ec6 = st.columns([2,2])
        existing_sites = sorted(long["site_label"].dropna().astype(str).unique().tolist())
        all_site_opts  = [""] + existing_sites
        site_sel  = ec5.selectbox("Survey Location (existing)", all_site_opts)
        site_new  = ec6.text_input("Or type a new location name")
        rec_other = ""
        if recorder == "Other — type below":
            rec_other = st.text_input("Recorder full name")
        st.markdown('</div>', unsafe_allow_html=True)

        recorder_final = rec_other.strip() if rec_other.strip() else (recorder if recorder else "")
        site_final = site_new.strip() if site_new.strip() else site_sel

        st.markdown('<div class="form-sec"><div class="form-sec-title">🗑️ Trash Item Counts — Enter count for each item (0 if not found)</div>', unsafe_allow_html=True)
        counts = {}
        for group_name, items in TRASH_GROUPS.items():
            st.markdown(f'<div class="grp-hdr">{group_name}</div>', unsafe_allow_html=True)
            n = min(4,len(items))
            cols = st.columns(n)
            for i,item in enumerate(items):
                with cols[i%n]:
                    counts[item] = st.number_input(item, min_value=0, value=0, step=1, key=f"c_{group_name}_{item}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-sec"><div class="form-sec-title">📝 Field Notes (optional)</div>', unsafe_allow_html=True)
        st.text_area("Observations, site conditions, notable findings", height=90,
            placeholder="e.g. Recent flooding, concentrated litter near outfall, unusual debris...")
        st.markdown('</div>', unsafe_allow_html=True)

        total_preview = sum(counts.values())
        st.markdown(f'<div class="live-total"><div class="live-total-n">{total_preview:,}</div><div class="live-total-l">total items counted in this entry</div></div>', unsafe_allow_html=True)
        submitted = st.form_submit_button("💾 Save Survey Entry to Database", use_container_width=True)

    if submitted:
        if not event_id.strip(): st.error("Event ID is required.")
        elif not site_final: st.error("Survey location is required.")
        else:
            try:
                sb = get_sb()
                sb.table("site_events").upsert({
                    "event_id":int(event_id.strip()),"date_site":survey_date.isoformat(),
                    "site_label":site_final,"location_description":site_final,
                    "recorder":recorder_final,"surveyed_m2":float(area_m2) if area_m2 else None,
                }).execute()
                rows=[{"event_id":int(event_id.strip()),"trash_group":g,"trash_item":item,"count_value":float(v)}
                      for g,items in TRASH_GROUPS.items() for item in items if (v:=counts.get(item,0)) and v>0]
                if rows: sb.table("trash_counts").insert(rows).execute()
                load.clear()
                st.success(f"✓ Saved — Event {event_id} · {site_final} · {survey_date.strftime('%B %d, %Y')} · {total_preview:,} items")
            except Exception as e:
                st.error(f"Could not save: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ── EXPORT ──────────────────────────────────════════════════════════
# ══════════════════════════════════════════════════════════════════
elif page == PAGES[7]:
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Export Data</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Download the survey data as CSV files — open in Excel, Google Sheets, R, Python, or ArcGIS. All exports reflect the current live database.</div>', unsafe_allow_html=True)

    # Event totals export
    et_exp = et.copy() if not et.empty else pd.DataFrame()

    # Site summary export
    site_exp = long.groupby(["site_label","seg"]).agg(
        total=("n","sum"), events=("event_id","nunique"),
        avg_per_event=("n","mean")
    ).reset_index().sort_values("total",ascending=False)

    # Long format
    long_exp_cols = [c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in long.columns]
    long_exp = long[long_exp_cols].copy()
    long_exp = long_exp.rename(columns={"n":"count","seg":"river_segment","site_label":"location"})

    exports = [
        ("Long Format — Every Record",
         long_exp,
         "scr_trash_long_format.csv",
         "One row per item category per survey event. Best for detailed analysis, pivot tables, R, Python.",
         f"{len(long_exp):,} rows · {len(long_exp.columns)} columns"),
        ("Event Totals",
         et_exp,
         "scr_trash_event_totals.csv",
         "One row per survey event — total item count, density (items/m²), location, date, segment.",
         f"{len(et_exp):,} rows · {len(et_exp.columns)} columns"),
        ("Site Summary",
         site_exp,
         "scr_trash_site_summary.csv",
         "One row per survey location — total items, number of events, average per event.",
         f"{len(site_exp):,} rows · {len(site_exp.columns)} columns"),
    ]

    for label, df_exp, fname, desc, size_note in exports:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        ec1,ec2 = st.columns([3,1])
        with ec1:
            st.markdown(f'<div class="sec-title">{label}</div><div class="sec-sub">{desc}</div>', unsafe_allow_html=True)
            st.caption(size_note)
        with ec2:
            if df_exp is not None and len(df_exp)>0:
                st.download_button(f"⬇ Download CSV", data=df_exp.to_csv(index=False).encode(),
                    file_name=fname, mime="text/csv", use_container_width=True, key=f"dl_{fname}")
        if df_exp is not None and len(df_exp)>0:
            with st.expander("Preview first 30 rows"):
                st.dataframe(df_exp.head(30), use_container_width=True, height=220)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="ftr"><div class="ftr-in">
  <div style="display:flex;align-items:center;gap:16px;">
    <img src="{LOGO_W}" style="height:30px;opacity:.8;">
    <div class="ftr-copy"><strong style="color:rgba(255,255,255,.7);display:block;">Sonoran Institute</strong>
    5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711 · (520) 290-0828</div>
  </div>
  <div class="ftr-copy" style="text-align:right;">
    <a href="https://sonoraninstitute.org/card/santacruz/" class="ftr-a">Santa Cruz River Program</a><br>
    Cloud Dashboard v4.0
  </div>
</div></div>""", unsafe_allow_html=True)

with st.expander("Account"):
    st.write(f"Signed in as **{prof.get('full_name','')}** ({prof.get('username','')})")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("🔄 Refresh Data"): load.clear(); st.rerun()
    with c2:
        if st.button("Sign Out"):
            st.session_state["auth"]=False; st.session_state["prof"]=None; st.rerun()
