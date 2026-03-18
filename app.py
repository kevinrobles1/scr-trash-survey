# ══════════════════════════════════════════════════════════════════
# Santa Cruz River Trash Survey Dashboard
# Sonoran Institute — River Restoration Program
# Cloud Version 3.0 · Supabase Backend
# ══════════════════════════════════════════════════════════════════
import json, html, re, hashlib, secrets
from datetime import datetime, date
 
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    "North Reach":   ["Santa Cruz River North of CoCerro","Between an outfall and Camino del Cerro","Santa Cruz River at Camino del Cerro","Silverlake Bridge on Santa Cruz"],
    "Central Reach": ["W side of Cushing St. bridge, north of the bridge at outfall","outfall CW Cushing, North side","Midway between Cushing and Congress, northern site","Midway between Cushing and Congress, southern site","South of Trail's end wash"],
    "South Reach":   ["South of Speedway (St. Mary's) (West)","Speedway and St. Mary","Santa Cruz river, Drexel and Irvington"],
    "Rillito":       ["Rillito at Country Club","Arcadia wash"],
}
SEG_ORDER  = ["North Reach","Central Reach","South Reach","Rillito"]
SEG_COLORS = {"North Reach":"#2980b9","Central Reach":"#27ae60","South Reach":"#e67e22","Rillito":"#8e44ad","Other":"#7f8c8d"}
SEG_LIGHT  = {"North Reach":"#d6eaf8","Central Reach":"#d5f5e3","South Reach":"#fdebd0","Rillito":"#e8daef","Other":"#eaecee"}
 
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
 
TEAM = ["Luke Cole","Sofia Angkasa","Kimberly Stanley","Marie Olson","S. Griset",
        "Soroush Hedayah","Vata Aflatoone","Kimberly Baeza","Joan Woodward",
        "Mark Krieski","Jamie Irby","Marsha Colbert","Axhel Munoz","Christine Hehenga"]
 
SEASONS = {1:"Winter",2:"Winter",3:"Spring",4:"Spring",5:"Spring",6:"Summer",
           7:"Summer",8:"Summer",9:"Fall",10:"Fall",11:"Fall",12:"Winter"}
 
PAGES = ["Overview","Map","Figures","Statistics","Data Entry","Data Table","Export"]
 
# ──────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SCR Trash Survey · Sonoran Institute",
    page_icon="🌊", layout="wide",
    initial_sidebar_state="collapsed",
)
PLOTLY_CFG = {"displaylogo":False,"modeBarButtonsToRemove":["lasso2d","select2d","autoScale2d","pan2d"]}
 
# ──────────────────────────────────────────────────────────────────
# DESIGN SYSTEM
# ──────────────────────────────────────────────────────────────────
C = dict(
    forest="#13291a", green="#1e4d1e", sage="#2d6a2d", mint="#5da832",
    gold="#c9820e", amber="#e8a620", cream="#faf7f0", sand="#f2ede2",
    sand2="#e8e1d0", sand3="#d8ceba", earth="#8b4513", brick="#b5451b",
    sky="#1a5276", water="#2471a3", text="#18180f", med="#3a3a28",
    muted="#686854", divider="#cec6b0", white="#ffffff",
)
PAL = [C["green"],C["water"],C["brick"],C["amber"],C["sage"],
       "#6c4f8a","#2e8b8b","#b5451b","#888877",C["mint"]]
 
def css():
    st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">""", unsafe_allow_html=True)
    st.markdown(f"""<style>
/* ── BASE ── */
html,body,[class*="css"]{{font-family:'DM Sans',sans-serif;color:{C["text"]};}}
.stApp{{background:{C["sand"]};}}
.block-container{{padding:0!important;max-width:100%!important;}}
[data-testid="stSidebar"],[data-testid="collapsedControl"]{{display:none!important;}}
 
/* ── HEADER ── */
.hdr{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 55%,{C["sage"]} 100%);
      border-bottom:2px solid {C["mint"]};box-shadow:0 4px 32px rgba(0,0,0,.22);}}
.hdr-in{{max-width:1480px;margin:0 auto;padding:14px 44px;
         display:flex;align-items:center;justify-content:space-between;}}
.hdr-brand{{display:flex;align-items:center;gap:18px;}}
.hdr-logo{{height:44px;}}
.hdr-name{{font-family:'Cormorant Garamond',serif;font-size:1.22rem;font-weight:700;
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
          animation:pulse 2s infinite;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.4;}}}}
 
/* ── NAV ── */
.nav{{background:{C["forest"]};position:sticky;top:0;z-index:200;
      border-bottom:1px solid rgba(255,255,255,.06);}}
.nav-in{{max-width:1480px;margin:0 auto;padding:0 44px;display:flex;gap:1px;}}
.nav-btn{{padding:13px 20px;font-size:11px;font-weight:600;letter-spacing:1px;
          text-transform:uppercase;color:rgba(255,255,255,.45);
          border-bottom:3px solid transparent;cursor:pointer;white-space:nowrap;
          transition:all .18s;font-family:'DM Sans',sans-serif;}}
.nav-btn:hover{{color:rgba(255,255,255,.85);background:rgba(255,255,255,.04);
               border-bottom-color:rgba(255,255,255,.2);}}
.nav-btn.on{{color:{C["mint"]};border-bottom-color:{C["mint"]};
             background:{C["mint"]}0d;}}
 
/* ── BODY ── */
.body{{max-width:1480px;margin:0 auto;padding:40px 44px 100px;}}
 
/* ── TYPOGRAPHY ── */
.pg-title{{font-family:'Cormorant Garamond',serif;font-size:2.1rem;font-weight:700;
           color:{C["green"]};letter-spacing:-.02em;line-height:1.15;margin-bottom:6px;}}
.pg-lead{{font-size:14.5px;color:{C["muted"]};line-height:1.8;max-width:780px;margin-bottom:32px;}}
.sec-title{{font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:600;
            color:{C["text"]};margin-bottom:2px;}}
.sec-sub{{font-size:11.5px;color:{C["muted"]};margin-bottom:14px;}}
.mono{{font-family:'DM Mono',monospace;}}
 
/* ── METRIC CARDS ── */
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:32px;}}
.kpi-grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:32px;}}
.kpi{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;padding:20px 22px 16px;
      position:relative;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.04);
      transition:box-shadow .2s,transform .2s;}}
.kpi:hover{{box-shadow:0 8px 32px rgba(0,0,0,.1);transform:translateY(-1px);}}
.kpi::after{{content:'';position:absolute;top:0;left:0;right:0;height:3px;
             background:linear-gradient(90deg,{C["green"]},{C["mint"]});}}
.kpi-lbl{{font-size:9.5px;text-transform:uppercase;letter-spacing:1.8px;
          color:{C["muted"]};font-weight:700;margin-bottom:9px;
          font-family:'DM Mono',monospace;}}
.kpi-val{{font-family:'Cormorant Garamond',serif;font-size:2.3rem;font-weight:700;
          color:{C["green"]};line-height:1;letter-spacing:-.02em;}}
.kpi-val.sm{{font-size:1.2rem;padding-top:7px;}}
.kpi-note{{font-size:11px;color:{C["muted"]};margin-top:5px;}}
.kpi-delta{{position:absolute;top:16px;right:16px;font-size:10px;
            font-family:'DM Mono',monospace;padding:2px 8px;border-radius:20px;}}
.kpi-delta.up{{background:{C["mint"]}18;color:{C["sage"]};border:1px solid {C["mint"]}30;}}
.kpi-delta.down{{background:#e74c3c18;color:#c0392b;border:1px solid #e74c3c30;}}
 
/* ── CARDS ── */
.card{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
       padding:24px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.04);}}
.card-hd{{display:flex;align-items:flex-start;justify-content:space-between;
          padding-bottom:14px;margin-bottom:18px;border-bottom:1px solid {C["sand3"]};}}
.card-hd-left .sec-title{{margin-bottom:2px;}}
 
/* ── SEGMENT CHIPS ── */
.chip{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:10px;
       font-weight:700;letter-spacing:.8px;text-transform:uppercase;
       font-family:'DM Mono',monospace;margin:2px;}}
.chip-north{{background:{SEG_LIGHT["North Reach"]};color:{SEG_COLORS["North Reach"]};border:1px solid {SEG_COLORS["North Reach"]}55;}}
.chip-central{{background:{SEG_LIGHT["Central Reach"]};color:{SEG_COLORS["Central Reach"]};border:1px solid {SEG_COLORS["Central Reach"]}55;}}
.chip-south{{background:{SEG_LIGHT["South Reach"]};color:{SEG_COLORS["South Reach"]};border:1px solid {SEG_COLORS["South Reach"]}55;}}
.chip-rillito{{background:{SEG_LIGHT["Rillito"]};color:{SEG_COLORS["Rillito"]};border:1px solid {SEG_COLORS["Rillito"]}55;}}
 
/* ── FIGURE MENU ── */
.fig-menu{{background:#fff;border:1px solid {C["sand3"]};border-radius:10px;
           padding:16px 14px;box-shadow:0 2px 10px rgba(0,0,0,.04);position:sticky;top:62px;}}
.fig-menu-cat{{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:2px;
               color:{C["muted"]};margin:14px 0 6px;font-family:'DM Mono',monospace;
               padding-bottom:5px;border-bottom:1px solid {C["sand3"]};}}
.fig-menu-cat:first-child{{margin-top:0;}}
.fig-btn{{display:block;width:100%;text-align:left;padding:7px 10px;border-radius:6px;
          font-size:12px;font-weight:500;color:{C["med"]};cursor:pointer;
          transition:all .15s;border:none;background:transparent;}}
.fig-btn:hover{{background:{C["sand"]};color:{C["green"]};}}
.fig-btn.on{{background:{C["green"]}12;color:{C["green"]};font-weight:600;
             border-left:3px solid {C["green"]};padding-left:7px;}}
 
/* ── STAT STRIP ── */
.stat-strip{{display:flex;gap:24px;flex-wrap:wrap;background:{C["green"]}08;
             border:1px solid {C["green"]}20;border-radius:8px;padding:14px 20px;
             margin-bottom:20px;}}
.stat-item{{text-align:center;}}
.stat-v{{font-family:'Cormorant Garamond',serif;font-size:1.4rem;font-weight:700;
         color:{C["green"]};display:block;}}
.stat-l{{font-size:10px;color:{C["muted"]};font-family:'DM Mono',monospace;
         text-transform:uppercase;letter-spacing:.8px;}}
 
/* ── FORM ── */
.form-sec{{background:#fff;border:1px solid {C["divider"]};
           border-left:4px solid {C["green"]};border-radius:0 10px 10px 0;
           padding:22px 26px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,.04);}}
.form-sec-title{{font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:600;
                 color:{C["green"]};margin-bottom:16px;padding-bottom:10px;
                 border-bottom:1px solid {C["sand3"]};}}
.grp-hdr{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
          color:{C["green"]};margin:18px 0 8px;padding-bottom:5px;
          border-bottom:2px solid {C["sand3"]};font-family:'DM Mono',monospace;}}
.live-total{{background:linear-gradient(135deg,{C["green"]}10,{C["mint"]}07);
             border:1px solid {C["green"]}25;border-radius:8px;padding:12px 18px;
             display:flex;align-items:center;gap:14px;margin:14px 0;}}
.live-total-n{{font-family:'Cormorant Garamond',serif;font-size:2rem;
               font-weight:700;color:{C["green"]};}}
.live-total-l{{font-size:12px;color:{C["muted"]};}}
 
/* ── INFO BANNER ── */
.banner{{background:{C["sky"]}0f;border:1px solid {C["sky"]}30;
         border-left:4px solid {C["sky"]};border-radius:0 8px 8px 0;
         padding:11px 15px;margin-bottom:18px;font-size:13px;color:{C["sky"]};}}
.banner-warn{{background:{C["amber"]}0f;border-color:{C["amber"]}30;
              border-left-color:{C["amber"]};color:{C["earth"]};}}
 
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
.stDownloadButton>button:hover{{background:{C["sage"]}!important;}}
 
/* ── TABLE ── */
div[data-testid="stDataFrame"]{{border:1px solid {C["sand3"]};border-radius:8px;overflow:hidden;}}
 
/* ── HIDE PHANTOM NAV ── */
.stTabs [data-baseweb="tab-list"]{{display:none!important;}}
.nav-btn-row{{margin:0!important;padding:0!important;
  height:0!important;overflow:hidden!important;}}
 
/* ── FOOTER ── */
.ftr{{background:{C["forest"]};padding:24px 44px;margin-top:80px;
      border-top:2px solid {C["sage"]};}}
.ftr-in{{max-width:1480px;margin:0 auto;display:flex;align-items:center;
         justify-content:space-between;flex-wrap:wrap;gap:16px;}}
.ftr-copy{{color:rgba(255,255,255,.35);font-size:11px;line-height:1.8;
           font-family:'DM Mono',monospace;}}
.ftr-a{{color:rgba(255,255,255,.5);text-decoration:none;}}
.ftr-a:hover{{color:{C["mint"]};}}
 
/* ── SCROLLBAR ── */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:{C["sand"]};}}
::-webkit-scrollbar-thumb{{background:{C["sand3"]};border-radius:3px;}}
::-webkit-scrollbar-thumb:hover{{background:{C["sage"]};}}
 
/* ── ANIMATIONS ── */
@keyframes fadeUp{{from{{opacity:0;transform:translateY(12px);}}to{{opacity:1;transform:none;}}}}
.fade-up{{animation:fadeUp .4s ease both;}}
</style>""", unsafe_allow_html=True)
 
# ──────────────────────────────────────────────────────────────────
# CHART HELPERS
# ──────────────────────────────────────────────────────────────────
def fig_base(fig, xt=None, yt=None, h=400, legend_h=True):
    fig.update_layout(
        height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=C["text"], size=12),
        margin=dict(l=6,r=6,t=36,b=6),
        legend=dict(bgcolor="rgba(255,255,255,.95)",bordercolor=C["divider"],
                    borderwidth=1,font=dict(size=11),
                    orientation="h" if legend_h else "v",
                    yanchor="bottom",y=1.02,xanchor="right",x=1),
        xaxis_title=xt, yaxis_title=yt,
    )
    fig.update_xaxes(showgrid=False,zeroline=False,linecolor=C["divider"],
                     tickfont=dict(size=11,color=C["muted"]))
    fig.update_yaxes(showgrid=True,gridcolor=C["sand2"],zeroline=False,
                     linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    return fig
 
def show(fig, key=None): st.plotly_chart(fig, config=PLOTLY_CFG, use_container_width=True, key=key)
 
def empty_notice(msg="No data available."): st.info(msg)
 
# ──────────────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────────────
def _hash(pw, salt): return hashlib.pbkdf2_hmac("sha256",pw.encode(),salt.encode(),100_000).hex()
 
def register(username, password, full_name, position):
    u = username.strip()
    if len(u)<3: return False,"Username must be ≥ 3 chars."
    if len(password)<6: return False,"Password must be ≥ 6 chars."
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
 
    # Full-width header bar
    st.markdown(f"""
    <div style="background:linear-gradient(160deg,{C['forest']},{C['sage']});
    padding:18px 44px;display:flex;align-items:center;gap:16px;
    border-bottom:2px solid {C['mint']};">
      <img src="{LOGO_W}" style="height:40px;">
      <div>
        <div style="font-family:'Cormorant Garamond',serif;font-size:1.25rem;
        font-weight:700;color:#fff;white-space:nowrap;">Santa Cruz River Trash Survey</div>
        <div style="font-size:9px;color:rgba(255,255,255,.45);letter-spacing:2px;
        text-transform:uppercase;font-family:'DM Mono',monospace;margin-top:3px;">
        Sonoran Institute · River Restoration Program</div>
      </div>
    </div>
 
    <style>
    /* Style the tab bar to look like it belongs to the card */
    div[data-testid="stTabs"] > div:first-child {{
        background: {C['forest']} !important;
        border-radius: 0 !important;
        padding: 0 !important;
        gap: 0 !important;
    }}
    div[data-testid="stTabs"] button[role="tab"] {{
        font-family: 'DM Sans', sans-serif !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px !important;
        color: rgba(255,255,255,0.5) !important;
        border-radius: 0 !important;
        padding: 14px 28px !important;
        border-bottom: 3px solid transparent !important;
        background: transparent !important;
    }}
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
        color: {C['mint']} !important;
        border-bottom-color: {C['mint']} !important;
        background: rgba(126,200,80,0.08) !important;
    }}
    div[data-testid="stTabs"] div[role="tabpanel"] {{
        background: white !important;
        border: 1px solid {C['sand3']} !important;
        border-top: none !important;
        border-radius: 0 0 10px 10px !important;
        padding: 32px 36px 36px !important;
        box-shadow: 0 12px 48px rgba(0,0,0,.1) !important;
    }}
    </style>
    """, unsafe_allow_html=True)
 
    # Welcome text above tabs
    st.markdown(f"""
    <div style="background:{C['forest']};padding:28px 36px 0;max-width:560px;
    margin:40px auto 0;">
      <div style="font-family:'Cormorant Garamond',serif;font-size:1.8rem;
      font-weight:700;color:#fff;line-height:1.2;margin-bottom:6px;">Welcome back</div>
      <div style="font-size:13px;color:rgba(255,255,255,0.55);line-height:1.7;margin-bottom:0;">
        Santa Cruz River Program &nbsp;·&nbsp;
        <span style="font-family:'DM Mono',monospace;font-size:11px;color:{C['mint']};">
        Director: Luke Cole</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
 
    _,col,_ = st.columns([1,1.3,1])
    with col:
        t1, t2 = st.tabs(["Sign In", "Create Account"])
        with t1:
            with st.form("_login"):
                un = st.text_input("Username")
                pw = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In →", use_container_width=True):
                    ok, prof = login(un, pw)
                    if ok:
                        st.session_state["auth"] = True
                        st.session_state["prof"] = prof
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
        with t2:
            with st.form("_reg"):
                c1, c2 = st.columns(2)
                fn = c1.text_input("Full Name")
                pos = c2.text_input("Position / Title")
                nu = st.text_input("Username (min 3 characters)")
                c3, c4 = st.columns(2)
                p1 = c3.text_input("Password (min 6 chars)", type="password")
                p2 = c4.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if p1 != p2:
                        st.error("Passwords don't match.")
                    else:
                        ok, msg = register(nu, p1, fn, pos)
                        (st.success if ok else st.error)(msg)
    st.stop()
 
# ──────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load():
    sb = get_sb()
    se_raw = sb.table("site_events").select("*").execute().data or []
    tc_raw = sb.table("trash_counts").select("event_id,trash_group,trash_item,count_value").execute().data or []
    wt_raw = sb.table("weights_data").select("event_id,date_recorded,total_weight_oz").execute().data or []
 
    se = pd.DataFrame(se_raw)
    tc = pd.DataFrame(tc_raw) if tc_raw else pd.DataFrame(columns=["event_id","trash_group","trash_item","count_value"])
    wt = pd.DataFrame(wt_raw) if wt_raw else pd.DataFrame(columns=["event_id","date_recorded","total_weight_oz"])
 
    tc["count_value"] = pd.to_numeric(tc["count_value"],errors="coerce").fillna(0)
    tc.rename(columns={"count_value":"n"},inplace=True)
 
    if not se.empty:
        for c in ["lat","lon","surveyed_m2"]:
            if c in se.columns: se[c]=pd.to_numeric(se[c],errors="coerce")
        if "date_site" in se.columns:
            se["date"]=pd.to_datetime(se["date_site"],errors="coerce")
        se["seg"]=se.get("site_label",pd.Series(dtype=str)).map(
            {s:seg for seg,sites in RIVER_SEGMENTS.items() for s in sites}).fillna("Other")
        keep=[c for c in ["event_id","date","site_label","seg","lat","lon","replicate_no","surveyed_m2","recorder","point_id"] if c in se.columns]
        se=se[keep].drop_duplicates()
 
    # Long joined table
    long = tc.merge(se,on="event_id",how="left") if not se.empty else tc.copy()
    if "date" in long.columns:
        long["date"]=pd.to_datetime(long["date"],errors="coerce")
        long["year"]=long["date"].dt.year
        long["month"]=long["date"].dt.month
        long["month_nm"]=pd.Categorical(long["date"].dt.strftime("%b"),
            categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],ordered=True)
        long["season"]=long["month"].map(SEASONS)
    for col in ["site_label","seg"]:
        if col not in long.columns: long[col]="Unknown"
    long["site_label"]=long["site_label"].fillna("Unknown")
    long["seg"]=long["seg"].fillna("Other")
 
    if not wt.empty:
        wt["date"]=pd.to_datetime(wt["date_recorded"],errors="coerce")
        wt["weight_oz"]=pd.to_numeric(wt["total_weight_oz"],errors="coerce")
    return long, se, wt
 
def save_event(ev_id, ev_date, area, site, recorder, counts):
    sb = get_sb()
    seg = next((seg for seg,sites in RIVER_SEGMENTS.items() if site in sites),"Other")
    sb.table("site_events").upsert({
        "event_id":int(ev_id),"date_site":ev_date.isoformat(),
        "site_label":site,"surveyed_m2":float(area) if area else None,
        "recorder":recorder,"complete":"y",
    }).execute()
    rows=[{"event_id":int(ev_id),"trash_group":g,"trash_item":it,"count_value":float(v)}
          for g,items in TRASH_GROUPS.items() for it in items if (v:=counts.get(it,0))>0]
    if rows: sb.table("trash_counts").insert(rows).execute()
    load.clear()
 
# ──────────────────────────────────────────────────────────────────
# ANALYTICS HELPERS
# ──────────────────────────────────────────────────────────────────
def site_stats(long):
    need={"point_id","event_id","replicate_no","n"}
    if not need.issubset(long.columns): return pd.DataFrame()
    pp=long.groupby(["point_id","event_id","replicate_no"],dropna=False)["n"].sum().reset_index(name="plot_total")
    pp=pp[pp["point_id"].notna()]
    ss=pp.groupby("point_id")["plot_total"].agg(n_plots="count",mean="mean",
        mn="min",mx="max",sd="std",total="sum").reset_index()
    ss["range"]=ss["mx"]-ss["mn"]; ss["cv"]=ss["sd"]/ss["mean"].replace(0,np.nan)*100
    ss["triplicate"]=(ss["n_plots"]==3)
    meta=long.groupby("point_id",dropna=False).agg(
        site_label=("site_label","first"),lat=("lat","mean"),lon=("lon","mean"),
        seg=("seg","first")).reset_index()
    ss=ss.merge(meta,on="point_id",how="left")
    ss=ss.sort_values(["lat","point_id"],ascending=[False,True]).reset_index(drop=True)
    ss["rank"]=np.arange(1,len(ss)+1)
    ss["display"]=ss["rank"].astype(str)+". "+ss["site_label"].fillna(ss["point_id"]).astype(str)
    return ss
 
def ev_totals(long):
    if "event_id" not in long.columns: return pd.DataFrame()
    gcols=[c for c in ["event_id","date","site_label","seg","surveyed_m2"] if c in long.columns]
    et=long.groupby(gcols,dropna=False)["n"].sum().reset_index(name="total")
    if "surveyed_m2" in et.columns:
        a=pd.to_numeric(et["surveyed_m2"],errors="coerce")
        et["per_m2"]=np.where(a>0,et["total"]/a,np.nan)
    return et
 
# ──────────────────────────────────────────────────────────────────
# MAP
# ──────────────────────────────────────────────────────────────────
def cmap(v,vmin,vmax):
    if pd.isna(v): return "#5b8bd9"
    t=max(0,min(1,(0.5 if vmax==vmin else (float(v)-float(vmin))/(float(vmax)-float(vmin)))))
    stops=[(0,(49,130,206)),(0.33,(78,201,176)),(0.66,(245,149,52)),(1,(214,69,65))]
    for i in range(len(stops)-1):
        t0,c0=stops[i]; t1,c1=stops[i+1]
        if t0<=t<=t1:
            f=(t-t0)/(t1-t0) if t1>t0 else 0
            return "#{:02x}{:02x}{:02x}".format(*[round(c0[j]+f*(c1[j]-c0[j])) for j in range(3)])
    return "#d64541"
 
def leaflet_map(df,lat,lon,lbl,popups,metric,seg_col=None,h=580):
    d=df.copy()
    d[lat]=pd.to_numeric(d[lat],errors="coerce"); d[lon]=pd.to_numeric(d[lon],errors="coerce")
    d=d[d[lat].notna()&d[lon].notna()]
    if len(d)==0: st.info("No GPS coordinates available."); return
    vals=pd.to_numeric(d[metric],errors="coerce") if metric in d.columns else pd.Series([0]*len(d))
    vmin,vmax=float(vals.min()),float(vals.max())
    recs=[]
    for _,r in d.iterrows():
        popup="<br>".join([f"<b>{html.escape(str(c).replace('_',' ').title())}</b>: {html.escape(str(r.get(c,''))[:80])}" for c in popups if c in d.columns])
        color=SEG_COLORS.get(str(r.get(seg_col,"Other")),"#888") if seg_col else cmap(r.get(metric,np.nan),vmin,vmax)
        recs.append({"lat":float(r[lat]),"lon":float(r[lon]),
                     "lbl":str(r[lbl]) if lbl in d.columns else "","popup":popup,"color":color,
                     "seg":str(r.get(seg_col,""))})
    clat,clon=float(d[lat].mean()),float(d[lon].mean())
    seg_legend="" if not seg_col else "".join(
        f'<div class="li"><div class="dot" style="background:{c}"></div>{s}</div>'
        for s,c in SEG_COLORS.items() if s!="Other")
    legend_title="River Segments" if seg_col else "Trash Burden"
    legend_body=seg_legend if seg_col else f'<div style="width:160px;height:8px;border-radius:3px;background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);margin:6px 0"></div><div style="display:flex;justify-content:space-between;font-size:11px;color:#666"><span>Lower</span><span>Higher</span></div>'
    src=f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
html,body,#map{{height:{h}px;width:100%;margin:0;font-family:'DM Sans',sans-serif;}}
.legend{{position:absolute;bottom:20px;right:20px;z-index:9999;background:rgba(255,255,255,.97);
padding:14px 18px;border-radius:8px;border:1px solid #d4ccc0;font-size:12px;
box-shadow:0 4px 20px rgba(0,0,0,.12);min-width:170px;}}
.legend-title{{font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:.8px;
color:{C["green"]};margin-bottom:9px;}}
.li{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:12px;}}
.dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
.leaflet-popup-content{{font-family:'DM Sans',sans-serif;font-size:13px;
line-height:1.6;min-width:200px;}}
.leaflet-popup-content b{{color:{C["green"]};}}
</style></head><body><div id="map"></div>
<div class="legend">
<div class="legend-title">{legend_title}</div>
{legend_body}
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map').setView([{clat},{clon}],12);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',
{{attribution:'© OpenStreetMap · © CARTO',maxZoom:20}}).addTo(map);
const data={json.dumps(recs)};const bounds=[];
data.forEach(m=>{{
const mk=L.circleMarker([m.lat,m.lon],{{radius:11,color:'rgba(255,255,255,.85)',
weight:2,fillColor:m.color,fillOpacity:.88}}).addTo(map);
if(m.popup) mk.bindPopup(m.popup,{{maxWidth:290}});
if(m.lbl) mk.bindTooltip('<strong>'+m.lbl+'</strong>',{{permanent:false,direction:'top',offset:[0,-13]}});
bounds.push([m.lat,m.lon]);
}});
if(bounds.length>1) map.fitBounds(bounds,{{padding:[36,36]}});
</script></body></html>"""
    components.html(src, height=h+10)
 
# ──────────────────────────────────────────────────────────────────
# STARTUP
# ──────────────────────────────────────────────────────────────────
css(); auth_gate()
prof=st.session_state.get("prof") or {}
if "page" not in st.session_state: st.session_state["page"]="Overview"
 
# HEADER
st.markdown(f"""<div class="hdr"><div class="hdr-in">
<div class="hdr-brand"><img src="{LOGO_W}" class="hdr-logo">
<div><div class="hdr-name">Santa Cruz River Trash Survey</div>
<div class="hdr-sub">Sonoran Institute · River Restoration Program</div></div></div>
<div class="hdr-right"><div class="hdr-user">
<strong>{prof.get('full_name','')}</strong>{prof.get('position_title','')}</div>
<div class="hdr-pill"><span class="hdr-dot"></span>Live Database</div></div>
</div></div>""", unsafe_allow_html=True)
 
# NAV
pg=st.session_state["page"]
nav="".join(f'<span class="nav-btn{"  on" if p==pg else ""}" data-p="{p}">{p}</span>' for p in PAGES)
st.markdown(f'<div class="nav"><div class="nav-in">{nav}</div></div>', unsafe_allow_html=True)
ncols=st.columns(len(PAGES))
for i,p in enumerate(PAGES):
    with ncols[i]:
        if st.button(p,key=f"_n{p}",help=p): st.session_state["page"]=p; st.rerun()
st.markdown('<style>div[data-testid="stHorizontalBlock"]:has(button[title="Overview"]){height:0!important;overflow:hidden!important;margin:0!important;padding:0!important;}</style>', unsafe_allow_html=True)
components.html("""<script>(function(){function go(){window.parent.document.querySelectorAll('.nav-btn')
.forEach(el=>el.addEventListener('click',()=>{const p=el.getAttribute('data-p');
window.parent.document.querySelectorAll('button').forEach(b=>{if(b.title===p)b.click();});}));}
document.readyState==='complete'?go():window.addEventListener('load',go);})();</script>""",height=0)
 
page=st.session_state["page"]
 
# LOAD DATA
with st.spinner("Loading from database…"):
    try:
        long,se,wt=load()
    except Exception as e:
        st.error(f"Database error: {e}"); st.stop()
 
et=ev_totals(long)
ss=site_stats(long) if all(c in long.columns for c in ["point_id","replicate_no","n"]) else pd.DataFrame()
 
# ══════════════════════════════════════════════════════════════════
# ── OVERVIEW ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
if page=="Overview":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Santa Cruz River Trash Monitoring</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="pg-lead">Longitudinal trash survey data collected along the Santa Cruz River corridor, Tucson, AZ. Triplicate 10×10 m plots sampled at {long["site_label"].nunique()} sites across four river segments. Program directed by <strong>Luke Cole</strong>, Sonoran Institute.</div>',unsafe_allow_html=True)
 
    total_n   = int(long["n"].sum())
    n_events  = long["event_id"].nunique()
    n_sites   = long["site_label"].nunique()
    dmin,dmax = long["date"].min(),long["date"].max() if "date" in long.columns else (pd.NaT,pd.NaT)
    span = f"{dmin.strftime('%b %Y')} – {dmax.strftime('%b %Y')}" if pd.notna(dmin)&pd.notna(dmax) else "—"
    n_segs = long["seg"].nunique() if "seg" in long.columns else 0
    avg_ev = total_n/max(n_events,1)
 
    # year over year delta
    if "year" in long.columns:
        yy=long.groupby("year")["n"].sum()
        yrs=sorted(yy.index.dropna())
        delta_str=""
        if len(yrs)>=2:
            pct=(yy[yrs[-1]]-yy[yrs[-2]])/max(yy[yrs[-2]],1)*100
            delta_str=f"{'▲' if pct>=0 else '▼'} {abs(pct):.0f}% vs {yrs[-2]}"
    else: delta_str=""
 
    st.markdown(f"""<div class="kpi-grid">
<div class="kpi"><div class="kpi-lbl">Total Items</div>
<div class="kpi-val">{total_n:,}</div><div class="kpi-note">all survey events</div>
{"<div class='kpi-delta up'>"+delta_str+"</div>" if delta_str else ""}
</div>
<div class="kpi"><div class="kpi-lbl">Survey Events</div>
<div class="kpi-val">{n_events:,}</div><div class="kpi-note">field visits</div></div>
<div class="kpi"><div class="kpi-lbl">Survey Sites</div>
<div class="kpi-val">{n_sites}</div><div class="kpi-note">{n_segs} river segments</div></div>
<div class="kpi"><div class="kpi-lbl">Avg Items / Event</div>
<div class="kpi-val">{avg_ev:.0f}</div><div class="kpi-note">all-time average</div></div>
<div class="kpi"><div class="kpi-lbl">Survey Period</div>
<div class="kpi-val sm">{span}</div><div class="kpi-note">longitudinal monitoring</div></div>
</div>""",unsafe_allow_html=True)
 
    # Row 1: Timeline + donut
    c1,c2 = st.columns([3,2])
    with c1:
        st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Items Over Time</div><div class="sec-sub">Monthly totals — gray bars indicate no survey conducted that month</div></div></div>',unsafe_allow_html=True)
        if "date" in long.columns:
            ts=long.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
            full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
            ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
            ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0)
            colors=[C["sand3"] if g else C["green"] for g in ts["gap"]]
            fig=go.Figure(go.Bar(x=ts["date"],y=ts["n"],marker_color=colors,
                customdata=ts["gap"],
                hovertemplate="<b>%{x|%b %Y}</b><br>%{customdata[0]}<extra></extra>"))
            # rolling avg
            ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
            fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-mo avg",
                line=dict(color=C["amber"],width=2,dash="dot"),mode="lines")
            fig_base(fig,"Month","Items",h=320); show(fig,"ov_ts")
        st.markdown('</div>',unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">By River Segment</div><div class="sec-sub">Share of all recorded items</div></div></div>',unsafe_allow_html=True)
        if "seg" in long.columns:
            sg=long[long["seg"].isin(SEG_ORDER)].groupby("seg")["n"].sum().reindex(SEG_ORDER).dropna().reset_index()
            sg.columns=["seg","n"]
            fig=px.pie(sg,values="n",names="seg",hole=.48,
                color="seg",color_discrete_map=SEG_COLORS)
            fig.update_traces(textposition="outside",textinfo="percent+label",textfont_size=11,
                pull=[.04,0,0,0])
            fig.update_layout(height=320,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
                margin=dict(l=10,r=10,t=10,b=10),font=dict(family="DM Sans"))
            show(fig,"ov_pie")
        st.markdown('</div>',unsafe_allow_html=True)
 
    # Row 2: Top items + Segment stacked
    c3,c4=st.columns([2,3])
    with c3:
        st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Top 15 Items</div><div class="sec-sub">All-time count</div></div></div>',unsafe_allow_html=True)
        top=long.groupby("trash_item")["n"].sum().nlargest(15).reset_index().sort_values("n")
        fig=px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["sky"]])
        fig_base(fig,"Count",None,h=400); show(fig,"ov_top")
        st.markdown('</div>',unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Category Breakdown by River Segment</div><div class="sec-sub">Stacked comparison across all four reaches</div></div></div>',unsafe_allow_html=True)
        if "trash_group" in long.columns and "seg" in long.columns:
            sg2=long[long["seg"].isin(SEG_ORDER)].groupby(["seg","trash_group"])["n"].sum().reset_index()
            sg2["seg"]=pd.Categorical(sg2["seg"],SEG_ORDER,ordered=True)
            sg2=sg2.sort_values("seg")
            fig=px.bar(sg2,x="seg",y="n",color="trash_group",barmode="stack",
                color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER})
            fig_base(fig,"Segment","Items",h=400); show(fig,"ov_seg")
        st.markdown('</div>',unsafe_allow_html=True)
 
    # Row 3: Heatmap
    st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Survey Intensity Heatmap</div><div class="sec-sub">Total items recorded per site per year — reveals spatial and temporal patterns</div></div></div>',unsafe_allow_html=True)
    if "year" in long.columns:
        heat=long.groupby(["site_label","year"])["n"].sum().reset_index()
        pvt=heat.pivot(index="site_label",columns="year",values="n").fillna(0)
        fig=px.imshow(pvt,color_continuous_scale=["#f2ede2","#5da832","#1e4d1e"],
            labels=dict(color="Items"),aspect="auto")
        fig_base(fig,None,"Site",h=max(300,28*len(pvt)))
        fig.update_xaxes(tickangle=0); show(fig,"ov_heat")
    st.markdown('</div>',unsafe_allow_html=True)
 
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── MAP ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page=="Map":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Spatial Distribution</div>',unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">GPS survey sites along the Santa Cruz River corridor. Sites are color-coded by river reach. Click any marker for details.</div>',unsafe_allow_html=True)
 
    vmode=st.radio("View",["Sites by Segment","Sites by Trash Burden","Individual Events"],horizontal=True)
 
    if vmode=="Sites by Segment":
        if len(ss)>0 and "lat" in ss.columns:
            ss_m=ss[ss["lat"].notna()&ss["lon"].notna()].copy()
            c1,c2,c3,c4=st.columns(4)
            c1.metric("Sites",len(ss_m))
            c2.metric("Avg Items/Plot",f"{ss_m['mean'].mean():.1f}" if len(ss_m)>0 else "—")
            c3.metric("Full Triplicates",int(ss_m["triplicate"].sum()))
            c4.metric("Segments",ss_m["seg"].nunique() if "seg" in ss_m.columns else "—")
            leaflet_map(ss_m,"lat","lon","display",
                ["site_label","seg","n_plots","mean","sd","total"],"mean",seg_col="seg")
            with st.expander("Site Details Table"):
                cols=[c for c in ["display","site_label","seg","n_plots","mean","sd","range","total"] if c in ss_m.columns]
                st.dataframe(ss_m[cols],use_container_width=True)
        else: st.info("Site stats require point_id & replicate data.")
 
    elif vmode=="Sites by Trash Burden":
        if len(ss)>0 and "lat" in ss.columns:
            ss_m=ss[ss["lat"].notna()&ss["lon"].notna()]
            leaflet_map(ss_m,"lat","lon","display",["site_label","n_plots","mean","sd","total"],"mean")
        else: st.info("No site data with coordinates.")
 
    else:
        ev=long.groupby(["event_id","site_label","date","lat","lon","seg"],dropna=False)["n"].sum().reset_index()
        ev=ev[ev["lat"].notna()&ev["lon"].notna()]
        if len(ev)==0: st.info("No events with coordinates.")
        else:
            st.metric("Events Mapped",len(ev))
            leaflet_map(ev,"lat","lon","site_label",["event_id","site_label","date","n"],"n",seg_col="seg")
 
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── FIGURES ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page=="Figures":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Analytical Figures</div>',unsafe_allow_html=True)
 
    FCAT={
        "⏱ Temporal":[
            "Items Over Time","Rolling Average","Yearly Totals","Monthly Comparison",
            "Seasonal Patterns","Cumulative Total","Average Per Event","Items Per m²",
            "Weight Over Time","Events Per Month",
        ],
        "📦 Categories":[
            "Top 25 Items","Category Totals","Category Trends","Segment × Category",
            "Items vs Weight","Category Heatmap",
        ],
        "📍 Sites":[
            "Sites — Mean (N→S)","Sites — Variability","Sites — CV","Sites — Range",
            "Sites — Total","Top 10 Cleanest","Top 10 Highest","Segment Comparison",
            "All Sites Ranked","Per-m² by Site",
        ],
    }
 
    if "fig_sel" not in st.session_state: st.session_state["fig_sel"]="Items Over Time"
    sel=st.session_state["fig_sel"]
 
    ml,mr=st.columns([1,3.8])
    with ml:
        st.markdown('<div class="fig-menu">',unsafe_allow_html=True)
        for cat,figs in FCAT.items():
            st.markdown(f'<div class="fig-menu-cat">{cat}</div>',unsafe_allow_html=True)
            for f in figs:
                cls="fig-btn on" if f==sel else "fig-btn"
                st.markdown(f'<button class="{cls}" onclick="">{f}</button>',unsafe_allow_html=True)
                if st.button(f,key=f"fb_{f}",use_container_width=True):
                    st.session_state["fig_sel"]=f; st.rerun()
        st.markdown('</div>',unsafe_allow_html=True)
 
    with mr:
        df=long.copy()
        df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)
        mean_line=dict(line_dash="dot",line_color=C["brick"],annotation_font_size=11)
 
        st.markdown(f'<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">{sel}</div></div></div>',unsafe_allow_html=True)
 
        # ── TEMPORAL ──────────────────────────────────────────────
        if sel=="Items Over Time":
            ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
            full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
            ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
            ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0)
            fig=go.Figure(go.Bar(x=ts["date"],y=ts["n"],
                marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],
                name="Monthly"))
            ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
            fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-mo rolling avg",
                line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
            fig_base(fig,"Month","Items",h=440); show(fig,"f_ot")
 
        elif sel=="Rolling Average":
            ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
            for w,col in [(3,C["mint"]),(6,C["amber"]),(12,C["brick"])]:
                ts[f"r{w}"]=ts["n"].rolling(w,min_periods=1).mean()
                fig_data=ts
            fig=go.Figure()
            fig.add_bar(x=ts["date"],y=ts["n"],name="Monthly",marker_color=C["green"],opacity=.2)
            for w,col,n in [(3,C["mint"],"3-mo"),(6,C["amber"],"6-mo"),(12,C["brick"],"12-mo")]:
                if len(ts)>=w:
                    fig.add_scatter(x=ts["date"],y=ts[f"r{w}"],name=f"{n} avg",
                        line=dict(color=col,width=2.5),mode="lines")
            fig_base(fig,"Month","Items",h=440); show(fig,"f_roll")
 
        elif sel=="Yearly Totals":
            yr=df.dropna(subset=["year"]).groupby("year")["n"].sum().reset_index()
            yr["yr"]=yr["year"].astype(str)
            fig=px.bar(yr,x="yr",y="n",color_discrete_sequence=[C["green"]],text="n")
            fig.update_traces(textposition="outside",texttemplate="%{text:,}")
            fig_base(fig,"Year","Items",h=400); show(fig,"f_yr")
 
        elif sel=="Monthly Comparison":
            md=df.dropna(subset=["year","month"]).groupby(["year","month_nm"],observed=False)["n"].sum().reset_index()
            md["yr"]=md["year"].astype(str)
            fig=px.bar(md,x="month_nm",y="n",color="yr",barmode="group",
                color_discrete_sequence=PAL,
                category_orders={"month_nm":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]})
            fig_base(fig,"Month","Items",h=420); show(fig,"f_mo")
 
        elif sel=="Seasonal Patterns":
            if "season" in df.columns:
                ss2=df.groupby(["season","trash_group"])["n"].sum().reset_index()
                sord=["Spring","Summer","Fall","Winter"]
                ss2["season"]=pd.Categorical(ss2["season"],sord,ordered=True)
                fig=px.bar(ss2.sort_values("season"),x="season",y="n",color="trash_group",
                    barmode="stack",color_discrete_sequence=PAL,category_orders={"season":sord})
                fig_base(fig,"Season","Items",h=420); show(fig,"f_sea")
            else: empty_notice("Season data not available.")
 
        elif sel=="Cumulative Total":
            ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
            ts["cum"]=ts["n"].cumsum()
            fig=go.Figure()
            fig.add_scatter(x=ts["date"],y=ts["cum"],mode="lines",
                line=dict(color=C["green"],width=3),fill="tozeroy",fillcolor=C["green"]+"18",name="Cumulative")
            fig_base(fig,"Month","Cumulative Items",h=420); show(fig,"f_cum")
 
        elif sel=="Average Per Event":
            e2=et.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["total"].mean().reset_index(name="avg")
            fig=px.line(e2,x="date",y="avg",markers=True,color_discrete_sequence=[C["water"]])
            fig.add_hline(y=e2["avg"].mean(),**mean_line,
                annotation_text=f"Overall avg: {e2['avg'].mean():.0f}")
            fig_base(fig,"Month","Avg Items/Event",h=420); show(fig,"f_ape")
 
        elif sel=="Items Per m²":
            if "per_m2" in et.columns:
                tr=et.dropna(subset=["date","per_m2"]).groupby(pd.Grouper(key="date",freq="MS"))["per_m2"].mean().reset_index(name="avg")
                fig=px.area(tr,x="date",y="avg",color_discrete_sequence=[C["sage"]])
                fig.add_hline(y=tr["avg"].mean(),**mean_line)
                fig_base(fig,"Month","Items/m²",h=420); show(fig,"f_pm2")
            else: empty_notice("No surveyed area data available.")
 
        elif sel=="Weight Over Time":
            if not wt.empty and len(wt)>0:
                wd=wt.dropna(subset=["date","weight_oz"])
                tr=wd.groupby(pd.Grouper(key="date",freq="MS"))["weight_oz"].sum().reset_index()
                fig=px.bar(tr,x="date",y="weight_oz",color_discrete_sequence=[C["earth"]])
                fig_base(fig,"Month","Weight (oz)",h=420); show(fig,"f_wt")
            else: empty_notice("No weight data in database.")
 
        elif sel=="Events Per Month":
            e3=et.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["event_id"].nunique().reset_index(name="events")
            fig=px.bar(e3,x="date",y="events",color_discrete_sequence=[C["water"]])
            fig_base(fig,"Month","Survey Events",h=400); show(fig,"f_epm")
 
        # ── CATEGORIES ────────────────────────────────────────────
        elif sel=="Top 25 Items":
            top=df.groupby("trash_item")["n"].sum().nlargest(25).reset_index().sort_values("n")
            fig=px.bar(top,x="n",y="trash_item",orientation="h",color_discrete_sequence=[C["green"]])
            fig_base(fig,"Count",None,h=max(520,26*len(top))); show(fig,"f_t25")
 
        elif sel=="Category Totals":
            ct=df.groupby("trash_group")["n"].sum().sort_values().reset_index()
            fig=px.bar(ct,x="n",y="trash_group",orientation="h",color_discrete_sequence=[C["sky"]])
            fig_base(fig,"Count",None,h=max(380,28*len(ct))); show(fig,"f_ct")
 
        elif sel=="Category Trends":
            if "date" in df.columns:
                top_grps=df.groupby("trash_group")["n"].sum().nlargest(6).index.tolist()
                ct2=df[df["trash_group"].isin(top_grps)].groupby(
                    ["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
                fig=px.line(ct2,x="date",y="n",color="trash_group",markers=True,
                    color_discrete_sequence=PAL)
                fig_base(fig,"Quarter","Items",h=440); show(fig,"f_ctrd")
            else: empty_notice()
 
        elif sel=="Segment × Category":
            if "seg" in df.columns:
                sc=df[df["seg"].isin(SEG_ORDER)].groupby(["seg","trash_group"])["n"].sum().reset_index()
                fig=px.bar(sc,x="n",y="seg",color="trash_group",orientation="h",barmode="stack",
                    color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER[::-1]})
                fig_base(fig,"Items","Segment",h=360); show(fig,"f_sxc")
            else: empty_notice()
 
        elif sel=="Items vs Weight":
            if not wt.empty and "per_m2" in et.columns:
                merged=et.merge(wt[["event_id","weight_oz"]],on="event_id",how="inner")
                if len(merged)>0:
                    fig=px.scatter(merged,x="total",y="weight_oz",
                        color="seg" if "seg" in merged.columns else None,
                        color_discrete_map=SEG_COLORS,
                        hover_data=["event_id","site_label"] if "site_label" in merged.columns else ["event_id"],
                        trendline="ols")
                    fig_base(fig,"Total Items","Weight (oz)",h=440); show(fig,"f_ivw")
                else: empty_notice("No matched events with weight data.")
            else: empty_notice("Weight data or density data missing.")
 
        elif sel=="Category Heatmap":
            if "trash_group" in df.columns and "site_label" in df.columns:
                ht=df.groupby(["site_label","trash_group"])["n"].sum().reset_index()
                pv=ht.pivot(index="site_label",columns="trash_group",values="n").fillna(0)
                fig=px.imshow(pv,color_continuous_scale=["#f2ede2","#5da832","#1e4d1e"],
                    aspect="auto",labels=dict(color="Items"))
                fig_base(fig,None,"Site",h=max(380,28*len(pv)))
                fig.update_xaxes(tickangle=-35); show(fig,"f_cht")
            else: empty_notice()
 
        # ── SITES ─────────────────────────────────────────────────
        elif sel in ["Sites — Mean (N→S)","Sites — Variability","Sites — CV","Sites — Range","Sites — Total"]:
            if len(ss)==0: empty_notice("Site stats require replicate data.")
            else:
                cmap2={"Sites — Mean (N→S)":"mean","Sites — Variability":"sd",
                       "Sites — CV":"cv","Sites — Range":"range","Sites — Total":"total"}
                xc=cmap2[sel]; sh=ss.copy()
                if xc=="sd": sh[xc]=sh[xc].fillna(0)
                color_col="seg" if "seg" in sh.columns else None
                fig=px.bar(sh,x=xc,y="display",orientation="h",
                    color=sh["seg"] if color_col else None,
                    color_discrete_map=SEG_COLORS)
                fig_base(fig,xc.title() if xc!="cv" else "CV (%)",None,h=max(500,28*len(sh)))
                fig.update_yaxes(categoryorder="array",categoryarray=sh["display"].tolist(),autorange="reversed")
                show(fig,f"f_ss_{sel}")
 
        elif sel in ["Top 10 Cleanest","Top 10 Highest"]:
            if len(ss)==0: empty_notice()
            else:
                sh=ss.nsmallest(10,"mean") if "Cleanest" in sel else ss.nlargest(10,"mean")
                col=C["sky"] if "Cleanest" in sel else C["brick"]
                fig=px.bar(sh,x="mean",y="display",orientation="h",color_discrete_sequence=[col],
                    error_x="sd" if "sd" in sh.columns else None)
                fig_base(fig,"Avg Items/Plot",None,h=max(380,36*len(sh)))
                fig.update_yaxes(categoryorder="total ascending")
                show(fig,f"f_{sel}")
 
        elif sel=="Segment Comparison":
            if len(ss)>0 and "seg" in ss.columns:
                sg=ss[ss["seg"].isin(SEG_ORDER)].groupby("seg").agg(
                    mean_of_means=("mean","mean"),total=("total","sum"),
                    n_sites=("point_id","count"),mean_sd=("sd","mean")).reset_index()
                fig=make_subplots(rows=1,cols=2,subplot_titles=["Mean Items/Plot","Total Items"])
                for i,(col,ylab) in enumerate([("mean_of_means","Avg Items/Plot"),("total","Total Items")]):
                    fig.add_bar(row=1,col=i+1,x=sg["seg"],y=sg[col],
                        marker_color=[SEG_COLORS.get(s,C["green"]) for s in sg["seg"]],
                        showlegend=False)
                fig_base(fig,None,None,h=400); show(fig,"f_segcmp")
            else: empty_notice()
 
        elif sel=="All Sites Ranked":
            if len(ss)==0: empty_notice()
            else:
                sh=ss.sort_values("mean").reset_index(drop=True)
                sh["rnk"]=sh.index+1
                fig=px.bar(sh,x="mean",y="display",orientation="h",
                    color="seg" if "seg" in sh.columns else None,
                    color_discrete_map=SEG_COLORS,
                    error_x="sd" if "sd" in sh.columns else None)
                fig_base(fig,"Avg Items/Plot",None,h=max(620,28*len(sh)))
                fig.update_yaxes(categoryorder="array",categoryarray=sh["display"].tolist(),autorange="reversed")
                show(fig,"f_ar")
 
        elif sel=="Per-m² by Site":
            if "per_m2" in et.columns and "site_label" in et.columns:
                pm=et.dropna(subset=["per_m2"]).groupby("site_label")["per_m2"].mean().sort_values().reset_index()
                fig=px.bar(pm,x="per_m2",y="site_label",orientation="h",
                    color_discrete_sequence=[C["sage"]])
                fig_base(fig,"Avg Items/m²",None,h=max(380,26*len(pm))); show(fig,"f_pm2s")
            else: empty_notice("No per-m² data available.")
 
        st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── STATISTICS ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page=="Statistics":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Statistical Summary</div>',unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Replicate-based analysis. Each site has three 10×10 m plots (triplicates) surveyed per event. These are treated as replicates — not independent observations — and summarized as mean ± SD per plot.</div>',unsafe_allow_html=True)
 
    if len(ss)==0:
        st.warning("Statistical summaries require point_id and replicate_no in site_events.")
    else:
        # Summary strip
        n_trip=int(ss["triplicate"].sum()); pct_trip=n_trip/max(len(ss),1)*100
        grand_mean=float(ss["mean"].mean()); grand_sd=float(ss["mean"].std())
        st.markdown(f"""<div class="stat-strip">
<div class="stat-item"><span class="stat-v">{len(ss)}</span><span class="stat-l">Survey Sites</span></div>
<div class="stat-item"><span class="stat-v">{n_trip} ({pct_trip:.0f}%)</span><span class="stat-l">Full Triplicates</span></div>
<div class="stat-item"><span class="stat-v">{grand_mean:.1f}</span><span class="stat-l">Grand Mean (items/plot)</span></div>
<div class="stat-item"><span class="stat-v">±{grand_sd:.1f}</span><span class="stat-l">SD Across Sites</span></div>
<div class="stat-item"><span class="stat-v">{ss['mean'].median():.1f}</span><span class="stat-l">Median Site Mean</span></div>
<div class="stat-item"><span class="stat-v">{ss['cv'].median():.0f}%</span><span class="stat-l">Median CV</span></div>
</div>""", unsafe_allow_html=True)
 
        c1,c2=st.columns(2)
        with c1:
            st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Mean ± SD by Site (N→S)</div></div></div>',unsafe_allow_html=True)
            sh=ss.copy(); err=sh["sd"].fillna(0)
            fig=go.Figure()
            for seg in SEG_ORDER:
                mask=sh["seg"]==seg if "seg" in sh.columns else pd.Series([True]*len(sh))
                sub=sh[mask]
                fig.add_bar(x=sub["display"],y=sub["mean"],name=seg,
                    error_y=dict(type="data",array=sub["sd"].fillna(0),visible=True),
                    marker_color=SEG_COLORS.get(seg,C["green"]))
            fig_base(fig,"Site","Avg Items/Plot",h=440,legend_h=False)
            fig.update_xaxes(tickangle=-45); show(fig,"st_me")
            st.markdown('</div>',unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Coefficient of Variation by Site</div><div class="sec-sub">High CV = high variability between replicate plots</div></div></div>',unsafe_allow_html=True)
            sh2=ss.dropna(subset=["cv"]).sort_values("cv",ascending=False).head(20)
            fig=px.bar(sh2,x="cv",y="site_label",orientation="h",
                color="seg" if "seg" in sh2.columns else None,
                color_discrete_map=SEG_COLORS)
            fig_base(fig,"CV (%)","Site",h=440); show(fig,"st_cv")
            st.markdown('</div>',unsafe_allow_html=True)
 
        # Distribution
        st.markdown('<div class="card"><div class="card-hd"><div class="card-hd-left"><div class="sec-title">Distribution of Site Means</div><div class="sec-sub">Histogram + box plot showing spread of per-site average item counts</div></div></div>',unsafe_allow_html=True)
        fig=make_subplots(rows=1,cols=2,subplot_titles=["Histogram of Site Means","Box Plot by Segment"])
        fig.add_histogram(row=1,col=1,x=ss["mean"],marker_color=C["green"],nbinsx=12,
            showlegend=False,name="Sites")
        if "seg" in ss.columns:
            for seg in SEG_ORDER:
                sub=ss[ss["seg"]==seg]["mean"].dropna()
                if len(sub)>0:
                    fig.add_box(row=1,col=2,y=sub,name=seg,
                        marker_color=SEG_COLORS.get(seg,C["green"]),boxpoints="all",jitter=0.35)
        fig_base(fig,None,None,h=400); show(fig,"st_dist")
        st.markdown('</div>',unsafe_allow_html=True)
 
        # Full stats table
        st.markdown('<div class="card"><div class="sec-title">Full Site Statistics Table</div><div class="sec-sub">N→S order. Mean and SD are computed across replicate plots within each site.</div>',unsafe_allow_html=True)
        cols=[c for c in ["display","site_label","seg","n_plots","mean","sd","cv","range","mn","mx","total","triplicate"] if c in ss.columns]
        disp=ss[cols].copy()
        for c in ["mean","sd","cv","range"]:
            if c in disp.columns: disp[c]=disp[c].round(1)
        st.dataframe(disp,use_container_width=True,height=420)
        st.download_button("Download Statistics CSV",
            data=disp.to_csv(index=False).encode(),
            file_name="SCR_trash_statistics.csv",mime="text/csv")
        st.markdown('</div>',unsafe_allow_html=True)
 
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── DATA ENTRY ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page=="Data Entry":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">New Survey Entry</div>',unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Record field data directly to the cloud database. Replaces the paper form. Data appears in all charts immediately after saving.</div>',unsafe_allow_html=True)
 
    with st.form("_entry",clear_on_submit=False):
        st.markdown('<div class="form-sec"><div class="form-sec-title">Event Information</div>',unsafe_allow_html=True)
        r1=st.columns(4)
        ev_id=r1[0].text_input("Event ID",placeholder="e.g. 396")
        ev_date=r1[1].date_input("Survey Date",value=date.today())
        area=r1[2].number_input("Plot Area (m²)",min_value=0.0,value=100.0,step=5.0)
        rec_sel=r1[3].selectbox("Recorder",[""]+TEAM+["Other →"])
 
        r2=st.columns([2,2,1])
        site_opts=[""]
        for seg,sites in RIVER_SEGMENTS.items():
            for s in sites: site_opts.append(s)
        existing=[s for s in sorted(long["site_label"].dropna().unique()) if s not in site_opts]
        site_opts+=existing
        site_sel=r2[0].selectbox("Survey Location",site_opts)
        site_new=r2[1].text_input("Or type a new location")
        rep_no=r2[2].number_input("Replicate #",min_value=1,max_value=3,value=1,step=1)
 
        rec_other=""
        if rec_sel=="Other →": rec_other=st.text_input("Recorder full name")
        rec_final=rec_other.strip() if rec_other.strip() else (rec_sel if rec_sel else "")
        site_final=site_new.strip() if site_new.strip() else site_sel
        st.markdown('</div>',unsafe_allow_html=True)
 
        st.markdown('<div class="form-sec"><div class="form-sec-title">Trash Item Counts — enter 0 or leave blank for items not observed</div>',unsafe_allow_html=True)
        counts={}
        for grp,items in TRASH_GROUPS.items():
            st.markdown(f'<div class="grp-hdr">{grp}</div>',unsafe_allow_html=True)
            n=min(4,len(items))
            cols=st.columns(n)
            for i,it in enumerate(items):
                with cols[i%n]:
                    counts[it]=st.number_input(it,min_value=0,value=0,step=1,key=f"_c_{grp}_{it}")
        st.markdown('</div>',unsafe_allow_html=True)
 
        st.markdown('<div class="form-sec"><div class="form-sec-title">Field Notes &amp; Conditions</div>',unsafe_allow_html=True)
        r3=st.columns([2,2])
        conditions=r3[0].selectbox("Site Conditions",["Normal","Post-flood","Dry","Construction nearby","Recent camp clearance","Other"])
        weather=r3[1].selectbox("Weather",["Clear","Partly cloudy","Overcast","Windy","Hot (>100°F)","Rain"])
        notes=st.text_area("Field observations",height=80,
            placeholder="Notable finds, concentrated areas, encampment debris, unusual items…")
        st.markdown('</div>',unsafe_allow_html=True)
 
        tot=sum(counts.values())
        st.markdown(f'<div class="live-total"><div class="live-total-n">{tot:,}</div><div class="live-total-l">total items in this entry<br><span style="font-family:\'DM Mono\',monospace;font-size:11px;color:#aaa;">{sum(1 for v in counts.values() if v>0)} item types with counts &gt; 0</span></div></div>',unsafe_allow_html=True)
        submitted=st.form_submit_button("💾  Save Survey Entry to Database",use_container_width=True)
 
    if submitted:
        if not ev_id.strip(): st.error("Event ID required.")
        elif not site_final: st.error("Location required.")
        else:
            try:
                save_event(int(ev_id.strip()),ev_date,float(area),site_final,rec_final,counts)
                st.success(f"✓ Saved — Event {ev_id} · {site_final} · {ev_date.strftime('%B %-d, %Y')} · {tot:,} items")
            except Exception as e:
                st.error(f"Save failed: {e}")
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── DATA TABLE ────────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════════
elif page=="Data Table":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Data Table</div>',unsafe_allow_html=True)
 
    with st.expander("🔍  Filters",expanded=True):
        fc=st.columns(4)
        all_sites=sorted(long["site_label"].dropna().astype(str).unique())
        sel_sites=fc[0].multiselect("Sites",all_sites,default=all_sites,key="dt_sites")
        all_segs=sorted(long["seg"].dropna().astype(str).unique()) if "seg" in long.columns else []
        sel_segs=fc[1].multiselect("Segments",all_segs,default=all_segs,key="dt_segs")
        all_grps=sorted(long["trash_group"].dropna().astype(str).unique()) if "trash_group" in long.columns else []
        sel_grps=fc[2].multiselect("Categories",all_grps,default=all_grps,key="dt_grps")
        mn=long["date"].min(); mx=long["date"].max()
        dr=fc[3].date_input("Date Range",value=(mn.date(),mx.date()),key="dt_dr") if pd.notna(mn)&pd.notna(mx) else None
 
    f=long.copy()
    if sel_sites: f=f[f["site_label"].isin(sel_sites)]
    else: f=f.iloc[0:0]
    if sel_segs and "seg" in f.columns: f=f[f["seg"].isin(sel_segs)]
    if sel_grps and "trash_group" in f.columns: f=f[f["trash_group"].isin(sel_grps)]
    if dr and isinstance(dr,(tuple,list)) and len(dr)==2:
        s,e=dr; f=f[f["date"].notna()&(f["date"].dt.date>=s)&(f["date"].dt.date<=e)]
 
    show_cols=[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in f.columns]
    sc=[c for c in ["date","event_id"] if c in show_cols]
 
    st.markdown('<div class="card">',unsafe_allow_html=True)
    m1,m2,m3=st.columns(3)
    m1.metric("Rows shown",f"{min(len(f),5000):,}")
    m2.metric("Total items",f"{int(f['n'].sum()):,}")
    m3.metric("Events",f"{f['event_id'].nunique():,}")
    st.dataframe(f[show_cols].sort_values(sc).head(5000),use_container_width=True,height=580)
    st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════
# ── EXPORT ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════
elif page=="Export":
    st.markdown('<div class="body fade-up">',unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Export Data</div>',unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Download formatted datasets for analysis in R, Python, Excel, or ArcGIS. All exports reflect the live database.</div>',unsafe_allow_html=True)
 
    long_exp=long[[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in long.columns]]
    et_exp=et.copy() if len(et)>0 else pd.DataFrame()
 
    exports=[
        ("Long Format — All Records","One row per item per event. Best for R, Python, pivot tables.",
         long_exp,"SCR_trash_long.csv"),
        ("Event Totals","One row per survey event with total items and density.",
         et_exp,"SCR_trash_events.csv"),
    ]
    if len(ss)>0:
        ss_exp=ss[[c for c in ["display","site_label","seg","n_plots","mean","sd","cv","range","total","triplicate","lat","lon"] if c in ss.columns]].copy()
        for c in ["mean","sd","cv","range"]:
            if c in ss_exp.columns: ss_exp[c]=ss_exp[c].round(2)
        exports.append(("Site Statistics (N→S)","Mean ± SD, CV, range per site. Ordered north to south.",
                         ss_exp,"SCR_trash_sites.csv"))
    if not wt.empty:
        exports.append(("Weight Data","Weight of trash collected per event.",
                         wt[["event_id","date","weight_oz"]],"SCR_trash_weights.csv"))
 
    for label,desc,df_e,fname in exports:
        st.markdown('<div class="card">',unsafe_allow_html=True)
        ec1,ec2=st.columns([3,1])
        with ec1:
            st.markdown(f'<div class="sec-title">{label}</div>',unsafe_allow_html=True)
            st.markdown(f'<div class="sec-sub">{desc}</div>',unsafe_allow_html=True)
            if df_e is not None and len(df_e)>0:
                st.caption(f"{len(df_e):,} rows · {len(df_e.columns)} columns")
        with ec2:
            if df_e is not None and len(df_e)>0:
                st.download_button(f"⬇ Download",data=df_e.to_csv(index=False).encode(),
                    file_name=fname,mime="text/csv",use_container_width=True,key=f"dl_{fname}")
        if df_e is not None and len(df_e)>0:
            with st.expander("Preview (50 rows)"):
                st.dataframe(df_e.head(50),use_container_width=True,height=200)
        st.markdown('</div>',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)
 
# ──────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────
st.markdown(f"""<div class="ftr"><div class="ftr-in">
<div style="display:flex;align-items:center;gap:16px;">
<img src="{LOGO_W}" style="height:34px;opacity:.8;">
<div class="ftr-copy"><strong style="color:rgba(255,255,255,.7);display:block;">Sonoran Institute</strong>
5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711 · (520) 290-0828</div></div>
<div class="ftr-copy" style="text-align:right;">
<a href="https://sonoraninstitute.org/card/santacruz/" class="ftr-a">Santa Cruz River Program</a><br>
Internal data system · Cloud v3.0</div>
</div></div>""", unsafe_allow_html=True)
 
with st.expander("⚙ Account & Settings"):
    st.write(f"Signed in as **{prof.get('full_name','')}** · {prof.get('username','')} · {prof.get('position_title','')}")
    c1,c2=st.columns(2)
    with c1:
        if st.button("🔄 Refresh Data"): load.clear(); st.rerun()
    with c2:
        if st.button("Sign Out"):
            st.session_state["auth"]=False; st.session_state["prof"]=None; st.rerun()
