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

# Phantom items accidentally migrated as trash — excluded at load time
PHANTOM_ITEMS = {"Event Id","Date","Surveyed M2","Complete?",
    "Total Items","Total Items/M2","Total Items/m2"}
PHANTOM_GROUPS = {"Ungrouped"}

# Every group:item pair exactly as stored in Supabase (title-cased by migration)
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
                       "Plates And Bowls Plastic","Cans, Milk Jugs, Mixes",
                       "Plates, Styrofoam","Utensils","Misc"],
    "Nicotine":       ["Cigs, Cigars, Lighters, Dip, Packs"],
    "Toiletries":     ["Toiletries","Packaging"],
    "Rx, Drugs":      ["Rx And Drug Packaging","Syringes, Paraphernalia"],
    "Toys, Games":    ["Balls, Games","Cd, Dvd, Electronic Packaging","School/Office Supplies",
                       "Id Cards, Credit Cards","Batteries"],
    "Paper Litter":   ["News, Books, Magazines","Advertising, Signs, Cards"],
    "Clothing":       ["Clothes, Shoes, Hats","Ppe","Misc. Fabric"],
    "Auto":           ["Car Parts (Small)","Car Parts (Large)","Tires"],
    "Construction":   ["Small Items","Large Items"],
    "Appliances":     ["Bikes, Bike Parts","Furniture/Cushions/Pillows","Shopping Carts",
                       "Carpet","Rope/Line","Buckets","Appliances"],
    "Plastic Bags":   ["Plastic Bags"],
    "Misc":           ["Sm. Debris (Ex. Metal, Plastic Scraps)","Lg. Debris (Ex. Garbage Cans)"],
}

# ── ENVIRONMENTAL CLASSIFICATIONS (from Excel analysis tabs) ──
# Recyclable per City of Tucson recycling program
RECYCLABLE_GROUPS  = {"Beer","Liquor","Soda","Water","Sports Drinks","Juice","Paper Litter"}
NON_RECYCLABLE_GROUPS = {"Plastic Bags","Cups","Food Packaging","Nicotine","Toiletries",
    "Rx, Drugs","Toys, Games","Clothing","Auto","Construction","Appliances","Misc"}
# Items that enter waterways during rain events — river health relevance
FLOATABLE_GROUPS   = {"Plastic Bags","Cups","Soda","Water","Sports Drinks","Juice",
    "Food Packaging","Paper Litter"}
NON_FLOATABLE_GROUPS = {"Beer","Liquor","Nicotine","Toiletries","Rx, Drugs","Toys, Games",
    "Clothing","Auto","Construction","Appliances","Misc"}
# Direct public health risk
HEALTH_HAZARD_GROUPS = {"Rx, Drugs","Nicotine","Toiletries"}
# Single-use beverage containers — policy relevance
BEVERAGE_GROUPS    = {"Beer","Liquor","Soda","Water","Sports Drinks","Juice","Cups"}
# Bulk/large debris — removal requires equipment
BULK_DEBRIS_GROUPS = {"Appliances","Construction","Auto"}
# Display order for charts (most to least by real totals)
GROUP_ORDER = ["Food Packaging","Clothing","Plastic Bags","Cups","Misc","Water","Nicotine",
    "Construction","Beer","Liquor","Soda","Toys, Games","Paper Litter","Toiletries",
    "Appliances","Sports Drinks","Juice","Rx, Drugs","Auto"]

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
/* Hide Streamlit cloud toolbar (Share/GitHub/Deploy bar) */
header[data-testid="stHeader"]{{height:0!important;min-height:0!important;display:none!important;}}
#MainMenu{{display:none!important;}}
[data-testid="stToolbar"]{{display:none!important;}}
[data-testid="stDecoration"]{{display:none!important;}}
footer{{display:none!important;}}
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

SECURITY_QUESTIONS = [
    "What is the name of the city where you were born?",
    "What was the name of your first pet?",
    "What is your mother's maiden name?",
    "What was the name of your elementary school?",
    "What was the make and model of your first car?",
    "What is the name of the street you grew up on?",
    "What was your childhood nickname?",
]

def register(username, password, full_name, position, sec_q="", sec_a=""):
    u = username.strip()
    if len(u)<3: return False,"Username must be at least 3 characters."
    if len(password)<6: return False,"Password must be at least 6 characters."
    if not full_name.strip(): return False,"Full name required."
    if not position.strip(): return False,"Position required."
    if not sec_q.strip(): return False,"Please select a security question."
    if len(sec_a.strip())<2: return False,"Security answer must be at least 2 characters."
    salt = secrets.token_hex(16)
    ans_salt = secrets.token_hex(16)
    try:
        get_sb().table("users").insert({
            "username":u,"password_hash":_hash(password,salt),"salt":salt,
            "full_name":full_name.strip(),"position_title":position.strip(),
            "security_question":sec_q.strip(),
            "security_answer_hash":_hash(sec_a.strip().lower(), ans_salt),
            "security_answer_salt":ans_salt,
        }).execute()
        return True,"Account created — sign in."
    except Exception as e:
        return False,("Username taken." if "unique" in str(e).lower() or "duplicate" in str(e).lower() else str(e))

def get_security_question(username):
    """Return the security question for a username, or None."""
    try:
        r = get_sb().table("users").select("security_question").eq("username",username.strip()).execute()
        if r.data and r.data[0].get("security_question"):
            return r.data[0]["security_question"]
        return None
    except: return None

def verify_security_answer(username, answer):
    """Return True if the security answer is correct."""
    try:
        r = get_sb().table("users").select("security_answer_hash,security_answer_salt").eq("username",username.strip()).execute()
        if not r.data: return False
        row = r.data[0]
        stored = row.get("security_answer_hash","")
        ans_salt = row.get("security_answer_salt","")
        if not stored or not ans_salt: return False
        return secrets.compare_digest(stored, _hash(answer.strip().lower(), ans_salt))
    except: return False

def reset_password(username, new_password):
    """Set a new password for a user (called after security answer verified)."""
    if len(new_password)<6: return False,"Password must be at least 6 characters."
    salt = secrets.token_hex(16)
    try:
        get_sb().table("users").update({
            "password_hash":_hash(new_password,salt),"salt":salt
        }).eq("username",username.strip()).execute()
        return True,"Password updated — sign in with your new password."
    except Exception as e: return False,str(e)

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
        t1,t2,t3 = st.tabs(["Sign In","Create Account","Forgot Password"])

        with t1:
            with st.form("_login"):
                un=st.text_input("Username"); pw=st.text_input("Password",type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Sign In",use_container_width=True):
                    ok,prof=login(un,pw)
                    if ok: st.session_state["auth"]=True; st.session_state["prof"]=prof; st.rerun()
                    else: st.error("Invalid username or password. Use the Forgot Password tab if needed.")

        with t2:
            st.markdown(f'<div style="font-size:12px;color:{C["muted"]};margin-bottom:12px;padding:10px 12px;background:{C["sand"]};border-radius:6px;border:1px solid {C["sand3"]};">Your username is how you sign in. Write it down — there is no way to look it up later. Choose something simple like your first name or initials.</div>', unsafe_allow_html=True)
            with st.form("_reg"):
                c1,c2=st.columns(2)
                fn=c1.text_input("Full Name"); pos=c2.text_input("Position / Title")
                nu=st.text_input("Username (min 3 characters — write this down)")
                c3,c4=st.columns(2)
                p1=c3.text_input("Password (min 6 characters)",type="password")
                p2=c4.text_input("Confirm Password",type="password")
                st.markdown("<div style='height:4px'></div>",unsafe_allow_html=True)
                sq=st.selectbox("Security question (for password reset)",["— Select one —"]+SECURITY_QUESTIONS)
                sa=st.text_input("Your answer to the security question",help="Case-insensitive. Example: if the question is about your pet, type the pet's name.")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button("Create Account",use_container_width=True):
                    if p1!=p2: st.error("Passwords don't match.")
                    elif sq=="— Select one —": st.error("Please select a security question.")
                    else:
                        ok,msg=register(nu,p1,fn,pos,sq,sa)
                        (st.success if ok else st.error)(msg)

        with t3:
            st.markdown(f'<div style="font-size:13px;color:{C["muted"]};margin-bottom:16px;line-height:1.7;">To reset your password, enter your username and answer your security question. If you did not set a security question when creating your account, contact the program administrator (Kevin Robles) to reset manually.</div>', unsafe_allow_html=True)
            if "reset_step" not in st.session_state: st.session_state["reset_step"]=1
            if "reset_username" not in st.session_state: st.session_state["reset_username"]=""

            if st.session_state["reset_step"]==1:
                with st.form("_reset1"):
                    r_un=st.text_input("Your username")
                    if st.form_submit_button("Look up my security question",use_container_width=True):
                        if not r_un.strip():
                            st.error("Please enter your username.")
                        else:
                            q=get_security_question(r_un.strip())
                            if q:
                                st.session_state["reset_username"]=r_un.strip()
                                st.session_state["reset_question"]=q
                                st.session_state["reset_step"]=2
                                st.rerun()
                            else:
                                st.error("Username not found, or this account has no security question set. Contact Kevin Robles for a manual reset.")

            elif st.session_state["reset_step"]==2:
                st.markdown(f'<div style="font-size:13px;color:{C["green"]};font-weight:600;margin-bottom:12px;padding:10px 14px;background:{C["sand"]};border-radius:6px;border-left:3px solid {C["green"]};">Security question for <strong>{st.session_state["reset_username"]}</strong>:<br>{st.session_state.get("reset_question","")}</div>', unsafe_allow_html=True)
                with st.form("_reset2"):
                    r_ans=st.text_input("Your answer",help="Not case-sensitive")
                    if st.form_submit_button("Verify answer",use_container_width=True):
                        if verify_security_answer(st.session_state["reset_username"], r_ans):
                            st.session_state["reset_step"]=3
                            st.rerun()
                        else:
                            st.error("Incorrect answer. Try again, or contact Kevin Robles.")
                if st.button("Start over", key="reset_back"):
                    st.session_state["reset_step"]=1; st.rerun()

            elif st.session_state["reset_step"]==3:
                st.success(f"Identity verified for {st.session_state['reset_username']}. Choose a new password.")
                with st.form("_reset3"):
                    np1=st.text_input("New password (min 6 characters)",type="password")
                    np2=st.text_input("Confirm new password",type="password")
                    if st.form_submit_button("Set new password",use_container_width=True):
                        if np1!=np2: st.error("Passwords don't match.")
                        else:
                            ok,msg=reset_password(st.session_state["reset_username"],np1)
                            if ok:
                                st.success(msg)
                                st.session_state["reset_step"]=1
                            else: st.error(msg)

        st.markdown(f"""<div class="auth-ftr"><span style="width:5px;height:5px;border-radius:50%;background:{C["mint"]};display:inline-block;"></span>Cloud database secured by Supabase · Passwords encrypted</div>""",unsafe_allow_html=True)
    st.stop()

# ──────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    sb=get_sb()
    # CRITICAL: Supabase PostgREST caps every query at 1,000 rows by default.
    # trash_counts has ~9,000 rows — without .limit() only 11% of data loads.
    tc=pd.DataFrame(sb.table("trash_counts").select("event_id,trash_group,trash_item,count_value").limit(100000).execute().data or [])
    se=pd.DataFrame(sb.table("site_events").select("*").limit(10000).execute().data or [])
    wt=pd.DataFrame(sb.table("weights_data").select("event_id,date_recorded,total_weight_oz").limit(10000).execute().data or [])

    if tc.empty: tc=pd.DataFrame(columns=["event_id","trash_group","trash_item","count_value"])
    tc.rename(columns={"count_value":"n"},inplace=True)
    tc["n"]=pd.to_numeric(tc["n"],errors="coerce").fillna(0)

    # ── CRITICAL: strip phantom rows from bad migration ──────────
    # 1. Remove rows where trash_item is a spreadsheet column header
    tc=tc[~tc["trash_item"].isin(PHANTOM_ITEMS)].copy()
    # 2. Remap Plastic Bags: stored with group=NULL or group='Ungrouped' 
    #    (no group header in Excel for col 3)
    pb_null  = tc["trash_group"].isna() & (tc["trash_item"]=="Plastic Bags")
    pb_ungrp = tc["trash_group"].isin(PHANTOM_GROUPS) & (tc["trash_item"]=="Plastic Bags")
    tc.loc[pb_null | pb_ungrp, "trash_group"] = "Plastic Bags"
    # 3. Drop any remaining Ungrouped / NULL group rows
    tc=tc[~tc["trash_group"].isin(PHANTOM_GROUPS)].copy()
    tc=tc[tc["trash_group"].notna()].copy()
    # 4. Strip any other phantom items that slipped through
    tc=tc[~tc["trash_item"].isin({"Complete?","Total Items","Total Items/M2","Total Items/m2"})].copy()
    # ─────────────────────────────────────────────────────────────

    # Add environmental classification columns
    tc["recyclable"]=tc["trash_group"].map(lambda g:
        "Recyclable" if g in RECYCLABLE_GROUPS else "Non-Recyclable")
    tc["floatable"]=tc["trash_group"].map(lambda g:
        "Floatable" if g in FLOATABLE_GROUPS else "Non-Floatable")
    tc["beverage"]=tc["trash_group"].isin(BEVERAGE_GROUPS)
    tc["health_hazard"]=tc["trash_group"].isin(HEALTH_HAZARD_GROUPS)
    tc["bulk_debris"]=tc["trash_group"].isin(BULK_DEBRIS_GROUPS)

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
# ──────────────────────────────────────────────────────────────────
# SITE TRIPLICATE STATISTICS (North → South)
# ──────────────────────────────────────────────────────────────────
def build_site_stats_ns(df):
    """
    Build per-site summary ordered North to South by latitude.
    Returns DataFrame with mean, SD, SE, CV, range, n_plots, total.
    These are computed at the PLOT level (one row per event at each site).
    """
    if df.empty or "site_label" not in df.columns: return pd.DataFrame()
    df2 = df.copy()
    df2["n"] = pd.to_numeric(df2["n"], errors="coerce").fillna(0)

    # Event-level totals (one row per event per site)
    ev_site = df2.groupby(["site_label","event_id","seg"],dropna=False)["n"].sum().reset_index(name="plot_total")

    # Site-level stats across events
    ss = ev_site.groupby(["site_label","seg"],dropna=False)["plot_total"].agg(
        n_plots="count", mean="mean", median="median",
        sd="std", total="sum", min_v="min", max_v="max"
    ).reset_index()
    ss["sd"] = ss["sd"].fillna(0)
    ss["se"] = ss["sd"] / np.sqrt(ss["n_plots"].replace(0, np.nan))
    ss["cv"] = np.where(ss["mean"] > 0, ss["sd"] / ss["mean"], np.nan)
    ss["range"] = ss["max_v"] - ss["min_v"]

    # Attach coordinates
    coords = df2.groupby("site_label",dropna=False).agg(lat=("lat","mean"),lon=("lon","mean")).reset_index()
    ss = ss.merge(coords, on="site_label", how="left")

    # North-to-south rank (higher lat = more north = rank 1)
    ss["lat_num"] = pd.to_numeric(ss["lat"], errors="coerce")
    ss_with = ss[ss["lat_num"].notna()].sort_values("lat_num", ascending=False).copy()
    ss_with["north_rank"] = range(1, len(ss_with)+1)
    ss_without = ss[ss["lat_num"].isna()].copy()
    ss_without["north_rank"] = np.nan
    ss = pd.concat([ss_with, ss_without], ignore_index=True)

    ss["site_display"] = ss.apply(lambda r:
        f"{int(r['north_rank'])}. {r['site_label']}" if pd.notna(r["north_rank"]) else r["site_label"], axis=1)
    ss = ss.sort_values(["north_rank","site_label"]).reset_index(drop=True)
    return ss

def fig_note(what, why, read, extra=""):
    """Render a styled interpretation box under a chart."""
    extra_html = f'<p style="color:{C["muted"]};margin:4px 0;font-size:13px;"><strong>Additional context:</strong> {extra}</p>' if extra else ""
    st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["green"]};
    border-radius:0 8px 8px 0;padding:16px 20px;margin:12px 0 20px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
    <div style="font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:600;color:{C["green"]};margin-bottom:10px;">How to read this figure</div>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>What it shows:</strong> {what}</p>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>Why it is useful:</strong> {why}</p>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>How to interpret it:</strong> {read}</p>
    {extra_html}
    </div>""", unsafe_allow_html=True)

def last_updated_insight(df, chart_type="general", site=None, category=None):
    """Show a dynamic 'As of [month year]...' insight line under a chart."""
    if df is None or df.empty or "date" not in df.columns: return
    latest = df["date"].dropna().max()
    if pd.isna(latest): return
    as_of = latest.strftime("%B %Y")
    total = int(df["n"].sum()) if "n" in df.columns else 0

    if chart_type == "monthly":
        recent = df[df["date"].dt.year == latest.year]
        yr_total = int(recent["n"].sum()) if "n" in recent.columns else 0
        msg = f"As of <strong>{as_of}</strong>, a total of <strong>{yr_total:,}</strong> items have been recorded in {latest.year}, with the most recent survey data from {as_of}."
    elif chart_type == "site" and site:
        site_df = df[df["site_label"]==site] if "site_label" in df.columns else df
        site_total = int(site_df["n"].sum()) if "n" in site_df.columns else 0
        site_mean = site_df.groupby("event_id")["n"].sum().mean() if "event_id" in site_df.columns else 0
        msg = f"As of <strong>{as_of}</strong>, <strong>{site}</strong> has recorded <strong>{site_total:,}</strong> total items across {site_df['event_id'].nunique() if 'event_id' in site_df.columns else '—'} survey events, with a mean of <strong>{site_mean:.1f}</strong> items per event."
    elif chart_type == "category" and category:
        cat_df = df[df["trash_group"]==category] if "trash_group" in df.columns else df
        cat_total = int(cat_df["n"].sum()) if "n" in cat_df.columns else 0
        pct = 100*cat_total/max(total,1)
        msg = f"As of <strong>{as_of}</strong>, <strong>{category}</strong> accounts for <strong>{cat_total:,}</strong> items — representing <strong>{pct:.1f}%</strong> of all recorded trash in the database."
    elif chart_type == "annual":
        yr_grp = df.dropna(subset=["year"]).groupby("year")["n"].sum()
        if len(yr_grp)>=2:
            yrs = sorted(yr_grp.index)
            last_yr, prev_yr = yrs[-1], yrs[-2]
            diff = int(yr_grp[last_yr] - yr_grp[prev_yr])
            direction = "increase" if diff>0 else "decrease"
            msg = f"As of <strong>{as_of}</strong>, {int(last_yr)} recorded <strong>{int(yr_grp[last_yr]):,}</strong> items — a <strong>{abs(diff):,}-item {direction}</strong> from {int(prev_yr)} ({int(yr_grp[prev_yr]):,} items)."
        else:
            msg = f"As of <strong>{as_of}</strong>, the database contains <strong>{total:,}</strong> total recorded items."
    else:
        n_sites = df["site_label"].nunique() if "site_label" in df.columns else "—"
        msg = f"As of <strong>{as_of}</strong>, the database contains <strong>{total:,}</strong> recorded items across <strong>{n_sites}</strong> survey locations. Most recent data: {as_of}."

    st.markdown(f'<div style="font-size:12.5px;color:{C["muted"]};padding:8px 14px;background:{C["sand"]};border-radius:6px;border-left:3px solid {C["sage"]};margin:8px 0 16px;line-height:1.7;">{msg}</div>', unsafe_allow_html=True)

def color_legend(title="Trash Burden", mode="gradient"):
    """Render a color legend below a map or chart."""
    if mode == "gradient":
        st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;
        padding:14px 18px;margin:10px 0;display:inline-flex;align-items:center;gap:16px;
        font-size:12px;color:{C["muted"]};box-shadow:0 2px 6px rgba(0,0,0,.04);">
        <strong style="color:{C["text"]};font-size:12px;">{title}:</strong>
        <div style="width:160px;height:10px;border-radius:4px;
        background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);"></div>
        <span>Lower</span><span style="font-size:16px;">→</span><span>Higher</span>
        </div>""", unsafe_allow_html=True)
    else:
        segs = [("North Reach","#2980b9"),("Central Reach","#27ae60"),("South Reach","#e67e22"),("Rillito","#8e44ad")]
        dots = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px;"><span style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block;"></span>{s}</span>' for s,c in segs)
        st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;
        padding:12px 18px;margin:10px 0;font-size:12px;color:{C["text"]};
        box-shadow:0 2px 6px rgba(0,0,0,.04);">
        <strong>River Segments:</strong>&nbsp;&nbsp;{dots}
        </div>""", unsafe_allow_html=True)

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
</script>""", height=50)

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
    n_gr=lf["trash_group"].nunique()  # After query fix: should be 19
    d_min,d_max=lf["date"].min(),lf["date"].max()
    span=f"{d_min.strftime('%b %Y')} – {d_max.strftime('%b %Y')}" if pd.notna(d_min) and pd.notna(d_max) else "—"
    st.markdown(f"""<div class="kpi-grid">
    <div class="kpi"><div class="kpi-lbl">Total Items Recorded</div><div class="kpi-val">{total_n:,}</div><div class="kpi-note">across all survey events</div></div>
    <div class="kpi"><div class="kpi-lbl">Survey Events</div><div class="kpi-val">{n_ev:,}</div><div class="kpi-note">individual field visits</div></div>
    <div class="kpi"><div class="kpi-lbl">Unique Locations</div><div class="kpi-val">{n_si:,}</div><div class="kpi-note">recorded site names</div></div>
    <div class="kpi"><div class="kpi-lbl">Trash Categories</div><div class="kpi-val">{n_gr}</div><div class="kpi-note">of 19 groups · 56 items</div></div>
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
            fb(fig,"Month","Total Items",h=300,title="Monthly Items Recorded"); show(fig,"ov_ts")
        last_updated_insight(lf, chart_type="monthly")
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
        fb(fig,"Total Count",None,h=420,title="Top 15 Items by Total Count"); show(fig,"ov_top")
        card_close()
    with c4:
        card_open("Items by River Segment and Category",
                  "Stacked bar chart showing contribution of each trash category within each known river segment. Only sites with assigned segment labels are shown.")
        if "seg" in lf.columns:
            sg=lf[lf["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            sg["seg"]=pd.Categorical(sg["seg"],SEG_ORDER,ordered=True); sg=sg.sort_values("seg")
            fig=px.bar(sg,x="seg",y="n",color="trash_group",barmode="stack",color_discrete_sequence=PAL,category_orders={"seg":SEG_ORDER})
            fb(fig,"River Segment","Total Items",h=420,title="Items by Segment and Category"); show(fig,"ov_seg")
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
        color_legend("River Segment Colors", mode="segments")
    elif map_mode=="By Trash Burden":
        render_map(wc,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total")
        color_legend("Map Color = Trash Burden (Total Items)", mode="gradient")
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
    color_legend("Map Color = Trash Burden", mode="gradient")
    tbl_note("Latitude and longitude values are averaged from all records for that site. 'Avg Items/Event' = total items ÷ number of survey events at that location. Map circles: blue = lower trash burden, red = higher trash burden.")

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
    st.markdown('<div class="pg-lead">How trash levels have changed over time. Select a figure from the menu below, read the description, then view the chart. Use the filter to narrow by location, segment, or date range.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="tr", cats=False)
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)

    TREND_FIGS = {
        "Monthly Item Count — Full Record": {
            "desc": "Total recorded trash items by calendar month. Green bars = survey conducted. Gray bars = no survey that month. Gold dashed line = 3-month rolling average.",
            "why": "Best figure for seeing the overall timeline of the program and identifying gaps in survey coverage.",
        },
        "Annual Totals by Year": {
            "desc": "Total items recorded within each calendar year, with exact counts labeled above each bar.",
            "why": "Useful for annual reporting and comparing year-over-year changes in overall burden.",
        },
        "Month-by-Month Comparison Across Years": {
            "desc": "Same calendar months compared across different survey years. Each color = one year.",
            "why": "Reveals seasonal patterns and whether a particular month is consistently heavy or light.",
        },
        "Average Items Per Survey Event Over Time": {
            "desc": "Monthly mean of total items per field visit. Dotted line = grand mean across the full record.",
            "why": "Adjusts for varying survey frequency — fairer than raw totals when the number of events per month changes.",
        },
        "Items by River Segment — Quarterly": {
            "desc": "Quarterly item totals for each named river segment. Each color = one segment.",
            "why": "Shows whether segments are tracking together or whether certain reaches are getting heavier or lighter over time.",
        },
        "Weight of Trash Collected Over Time": {
            "desc": "Monthly total weight (oz) for events where weight data was recorded. Not all events have weight data.",
            "why": "Provides a physical mass perspective on the litter burden, complementing the item count view.",
        },
    }

    sel_trend = st.selectbox("Select a figure to display", list(TREND_FIGS.keys()), key="trend_sel")

    # Description card
    fd = TREND_FIGS[sel_trend]
    st.markdown(f'<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["water"]};border-radius:0 8px 8px 0;padding:14px 20px;margin:12px 0 20px;"><div style="font-weight:700;font-size:14px;color:{C["text"]};margin-bottom:4px;">{sel_trend}</div><p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>What it shows:</strong> {fd["desc"]}</p><p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>Why useful:</strong> {fd["why"]}</p></div>', unsafe_allow_html=True)

    if sel_trend == "Monthly Item Count — Full Record":
        ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
        full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
        ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
        ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0); ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
        fig=go.Figure()
        fig.add_bar(x=ts["date"],y=ts["n"],marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],name="Monthly")
        fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-Mo Rolling Avg",line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
        fb(fig,"Month","Total Items",h=460,title="Monthly Item Count — Full Survey Record"); show(fig,"tr_ts")
        last_updated_insight(df, chart_type="monthly")
        fig_note("Total recorded trash items by calendar month across all sites and categories.",
            "Best figure for seeing the broad timeline — peaks, gaps, and overall direction.",
            "Green bars = survey conducted. Gray = no survey that month. Gold line = 3-month rolling average.",
            "Gray bars do not mean zero trash — they mean no survey. Rolling average treats gaps as zero.")

    elif sel_trend == "Annual Totals by Year":
        yr=df.dropna(subset=["year"]).groupby("year")["n"].sum().reset_index(); yr["year"]=yr["year"].astype(str)
        fig=px.bar(yr,x="year",y="n",color_discrete_sequence=[C["green"]],text="n")
        fig.update_traces(texttemplate="%{text:,}",textposition="outside")
        fb(fig,"Year","Total Items",h=420,title="Annual Totals by Survey Year"); show(fig,"tr_yr")
        last_updated_insight(df, chart_type="annual")
        fig_note("Total items across all events within each calendar year.",
            "Useful for year-over-year reporting.",
            "Taller bars = more total recorded items in that year.",
            "Annual totals reflect both trash burden and survey effort — years with more events may show higher counts.")

    elif sel_trend == "Month-by-Month Comparison Across Years":
        md=df.dropna(subset=["year","month"]).groupby(["year","month","month_name"],observed=False)["n"].sum().reset_index()
        md["year_str"]=md["year"].astype(str)
        fig=px.bar(md,x="month_name",y="n",color="year_str",barmode="group",
            category_orders={"month_name":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]},
            color_discrete_sequence=PAL)
        fb(fig,"Month","Total Items",h=460,title="Month-by-Month Comparison Across Years"); show(fig,"tr_mby")
        last_updated_insight(df, chart_type="monthly")
        fig_note("The same calendar months compared across survey years.",
            "Reveals seasonal patterns and year-over-year changes within each month.",
            "Each color = one survey year. Bars in the same month cluster = that month across years.",
            "Missing bars for a year-month combination mean no surveys were conducted in that period.")

    elif sel_trend == "Average Items Per Survey Event Over Time":
        ef=make_et(lf)
        if not ef.empty and "date" in ef.columns:
            ev2=ef.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["total"].mean().reset_index(name="avg")
            fig=px.line(ev2,x="date",y="avg",markers=True,color_discrete_sequence=[C["water"]])
            fig.add_hline(y=ev2["avg"].mean(),line_dash="dot",line_color=C["earth"],
                annotation_text=f"Grand mean: {ev2['avg'].mean():.0f}",annotation_font_size=11)
            fb(fig,"Month","Avg Items / Event",h=420,title="Average Items Per Survey Event — Monthly"); show(fig,"tr_avg")
            last_updated_insight(df, chart_type="general")
            fig_note("Monthly mean of total items per field visit across all sites.",
                "More interpretable than raw totals when survey frequency varies between months.",
                "Points above the dotted line = heavier-than-average months.",
                "Grand mean = average across all months in the full record.")
        else: st.info("No event-level data available.")

    elif sel_trend == "Items by River Segment — Quarterly":
        if "seg" in df.columns:
            sg=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(sg,x="date",y="n",color="seg",markers=True,color_discrete_map=SEG_COLORS)
            fb(fig,"Quarter","Items",h=420,title="Items by River Segment — Quarterly"); show(fig,"tr_seg")
            color_legend("Segment Colors", mode="segments")
            last_updated_insight(df, chart_type="general")
            fig_note("Quarterly totals split by named river segment.",
                "Reveals whether segments track together or diverge over time.",
                "Each line = one segment. Rising = more trash in that reach. Crossing lines = relative burden shifting.",
                "Only sites with assigned segment labels are included.")
        else: st.info("No segment data available.")

    elif sel_trend == "Weight of Trash Collected Over Time":
        if not wt.empty and "weight_oz" in wt.columns:
            dated=wt.dropna(subset=["weight_oz","date"])
            if len(dated)>0:
                wtrend=dated.groupby(pd.Grouper(key="date",freq="MS"))["weight_oz"].sum().reset_index()
                fig=px.bar(wtrend,x="date",y="weight_oz",color_discrete_sequence=[C["earth"]])
                fb(fig,"Month","Weight (oz)",h=420,title="Weight of Trash Collected — Monthly Total"); show(fig,"tr_wt")
                last_updated_insight(wt.rename(columns={"weight_oz":"n"}), chart_type="monthly")
                fig_note("Monthly total weight of trash collected (ounces).",
                    "Provides a physical mass perspective complementing the item count view.",
                    "Taller bars = more weight collected that month.",
                    "Not all survey events have weight data. Months with no bar may have item counts but no weight record.")
        else: st.info("No weight data in the database.")

    section_title("Annual Summary Table")
    st.markdown('<div class="sec-sub">Total items, number of events, and average items per event by calendar year. Sorted most recent first.</div>', unsafe_allow_html=True)
    ann=df.dropna(subset=["year"]).groupby("year").agg(
        total_items=("n","sum"),
        events=("event_id","nunique") if "event_id" in df.columns else ("n","count")
    ).reset_index()
    ann["avg_per_event"]=(ann["total_items"]/ann["events"]).round(1)
    ann["year"]=ann["year"].astype(int)
    ann=ann.sort_values("year",ascending=False).reset_index(drop=True)
    ann.index=range(1,len(ann)+1)
    ann.columns=["Year","Total Items","# Events","Avg Items per Event"]
    st.dataframe(ann, use_container_width=True, height=280)
    tbl_note("'Avg Items per Event' = total items that year ÷ distinct survey events. Higher values indicate heavier events, more thorough counting, or both. Years with fewer events have less reliable averages.")

    section_title("Monthly Breakdown Table")
    st.markdown('<div class="sec-sub">Total items by calendar month across all years combined.</div>', unsafe_allow_html=True)
    mon=df.dropna(subset=["month_name"]).groupby("month_name",observed=False)["n"].agg(total="sum",records="count").reset_index()
    mon.columns=["Month","Total Items","# Records"]
    st.dataframe(mon, use_container_width=True, height=280)
    tbl_note("Months with low totals may reflect fewer surveys, not less trash. Do not interpret as evidence of cleaner months without checking survey coverage.")
    st.markdown('</div>', unsafe_allow_html=True)

elif page == "Categories":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Trash Categories</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Deep analysis of all 19 category groups and 56 individual item types recorded along the Santa Cruz River. Select any figure from the menu — each includes a full description, environmental classification context, and interpretation guide.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="cat")
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)
    total_all=max(df["n"].sum(),1)

    CAT_FIGS = {
        "All 19 Categories — Total Items Ranked":               ("Totals & Overview",  "Every trash category ranked by cumulative item count. Colors encode environmental classification.", "The most important summary figure — use it to explain which categories drive the problem to any audience."),
        "All 56 Individual Items — Total Count Ranked":         ("Totals & Overview",  "Every recorded item type ranked by total count from most to least common across all survey events.", "Pinpoints specific items for prevention campaigns, source identification, and partnership messaging."),
        "Category Share — Proportional Breakdown":              ("Totals & Overview",  "Donut chart showing each category as a percentage of all recorded items.", "Easy to present in reports — shows visually that Food Packaging dominates the composition."),
        "Top 10 Heaviest vs Bottom 9 Lightest Categories":      ("Totals & Overview",  "Side-by-side comparison of the 10 heaviest and 9 lightest categories.", "Shows the skewed distribution — a small number of categories account for the vast majority of items."),
        "Average Items per Survey Event by Category":           ("Totals & Overview",  "Mean items per event for each category, adjusting for number of surveys conducted.", "More meaningful than raw totals when comparing categories with different recording frequencies."),
        "Beverage Containers — Full Breakdown":                 ("Food & Beverage",    "All beverage categories (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Cups) with sub-item detail.", "Beverage containers are a major single-use plastics source. Understanding their composition supports policy work."),
        "Cups — Styrofoam vs Plastic vs Paper":                 ("Food & Beverage",    "Breakdown of Cups into Styrofoam (Polar Pop), Styrofoam (Qt), Styrofoam (Other), Plastic, and Paper.", "Styrofoam cups are non-recyclable, non-biodegradable, and fragment into microplastics in waterways."),
        "Food Packaging — All 11 Sub-Items":                    ("Food & Beverage",    "The largest category broken into 11 sub-types including wrappers, straws, 6-pack rings, plates, utensils.", "Food Packaging is the single largest category (10,694 items). Understanding its composition is critical."),
        "Alcohol Containers — Beer vs Liquor Over Time":        ("Food & Beverage",    "Quarterly time series comparing Beer and Liquor item counts across the survey record.", "Alcohol containers are associated with encampments and chronic littering — useful for community context."),
        "Recyclable vs Non-Recyclable — Item Counts":           ("Environmental Risk", "All categories split into Recyclable vs Non-Recyclable per City of Tucson recycling guidelines.", "~16% of items are technically recyclable but none are being recycled — a clear intervention target."),
        "Floatable vs Non-Floatable — River Health Risk":       ("Environmental Risk", "Categories classified by whether they float and enter waterways during rain or flooding events.", "~63% of items are floatable — directly relevant to ADEQ stormwater permits and EPA Section 319 reporting."),
        "Health Hazard Items — Rx, Drugs, Nicotine, Toiletries":("Environmental Risk", "Items with direct public health risk: syringes, drug packaging, cigarettes, lighters, and toiletries.", "Syringes create needle-stick hazard for field staff. These require special handling protocols."),
        "Bulk & Large Debris — Appliances, Construction, Auto": ("Environmental Risk", "Large items requiring equipment: appliances, furniture, tires, car parts, construction debris.", "By item count modest, but by weight and removal cost they far exceed smaller categories."),
        "Category Risk Profile — Composite View":               ("Environmental Risk", "Scatter plot showing each category's total volume crossed with its risk dimensions.", "Identifies categories that are both high-volume AND high-risk — the priority removal targets."),
        "Category Trends Over Time — Top 6 Quarterly":         ("Trends by Category", "Quarterly time series for the 6 highest-volume categories.", "Shows whether category composition is stable or shifting over the program period."),
        "Year-over-Year Change by Category":                    ("Trends by Category", "Grouped bars showing each category's annual total across all survey years.", "Reveals which categories are increasing, decreasing, or stable year over year."),
        "Category Composition — How Mix Changed by Year":       ("Trends by Category", "100% stacked bars showing each category's share per year — removes total survey size effect.", "More ecologically meaningful than raw totals for detecting true composition shifts."),
        "Category Mix by River Segment":                        ("Geographic",         "Stacked bars showing category composition across North, Central, South, and Rillito reaches.", "Different segments may have different dominant categories due to adjacent land use patterns."),
        "Segment Specialization — Top Categories per Reach":    ("Geographic",         "One tab per segment showing the top 10 categories and their share of that segment's total.", "Identifies segment-specific waste profiles for targeted cleanup planning."),
        "Full Item-Level Statistics Table":                     ("Data Tables",        "Every item with total, % of all items, records, mean, recyclable, floatable flags.", "The authoritative reference table for reporting, grant writing, and agency submissions."),
        "Category Group Summary Table":                         ("Data Tables",        "All 19 groups with total, rank, %, records, mean, and all environmental classifications.", "Use as the primary summary table in any report or presentation."),
    }

    sel_cat = st.selectbox("Select a figure to display", list(CAT_FIGS.keys()), key="cat_fig_sel")
    grp_label, desc, why = CAT_FIGS[sel_cat]

    # Description card
    st.markdown(
        f'<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["water"]};'
        f'border-radius:0 8px 8px 0;padding:14px 20px;margin:12px 0 20px;">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};'
        f'font-family:DM Mono,monospace;margin-bottom:4px;">{grp_label}</div>'
        f'<div style="font-weight:700;font-size:14px;color:{C["text"]};margin-bottom:4px;">{sel_cat}</div>'
        f'<p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>What it shows:</strong> {desc}</p>'
        f'<p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>Why it matters:</strong> {why}</p>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ── RENDER SELECTED FIGURE ─────────────────────────────────────────────

    if sel_cat == "All 19 Categories — Total Items Ranked":
        grp_ord=[g for g in GROUP_ORDER if g in df["trash_group"].unique()]
        ct=df.groupby("trash_group")["n"].sum().reindex(grp_ord).dropna().reset_index()
        ct["pct"]=(100*ct["n"]/total_all).round(1)
        ct["color"]=ct["trash_group"].map(lambda g:
            C["water"] if g in RECYCLABLE_GROUPS else
            C["brick"] if g in HEALTH_HAZARD_GROUPS else
            C["amber"] if g in FLOATABLE_GROUPS else C["green"])
        fig=go.Figure(go.Bar(x=ct["n"],y=ct["trash_group"],orientation="h",
            marker_color=ct["color"],
            text=[f"{int(v):,} ({p}%)" for v,p in zip(ct["n"],ct["pct"])],
            textposition="outside"))
        fb(fig,"Total Items","Category",h=max(560,32*len(ct)),leg=False,
            title="All 19 Trash Categories — Total Items Recorded, Ranked"); show(fig,"cat_all19")
        st.markdown(
            f'<div style="font-size:12px;color:{C["muted"]};padding:8px 14px;background:{C["sand"]};border-radius:6px;margin:8px 0;">'
            f'Color guide: <span style="color:{C["water"]};font-weight:700;">Blue</span> = Recyclable (per City of Tucson) &nbsp;|&nbsp;'
            f'<span style="color:{C["brick"]};font-weight:700;">Red</span> = Health Hazard &nbsp;|&nbsp;'
            f'<span style="color:{C["amber"]};font-weight:700;">Amber</span> = Floatable &nbsp;|&nbsp;'
            f'<span style="color:{C["green"]};font-weight:700;">Green</span> = Other Non-Recyclable'
            f'</div>',
            unsafe_allow_html=True
        )
        last_updated_insight(df,"general")
        fig_note(
            "Cumulative total of every recorded item in each of the 19 category groups across all survey events.",
            "Food Packaging dominates because it has 11 sub-types — but Clothing at #2 is a strong signal of encampment activity. Plastic Bags is technically its own group.",
            "Longer bars = more total items. Color encodes environmental risk classification.",
            "Raw totals are not adjusted for number of sub-items per category. A category with 11 items will naturally accumulate more than one with 1 item, all else being equal."
        )

    elif sel_cat == "All 56 Individual Items — Total Count Ranked":
        top=df.groupby(["trash_group","trash_item"])["n"].sum().reset_index()
        top=top[top["n"]>0].sort_values("n",ascending=True)
        top["pct"]=(100*top["n"]/total_all).round(2)
        colors=[C["water"] if g in RECYCLABLE_GROUPS else C["brick"] if g in HEALTH_HAZARD_GROUPS else C["green"]
                for g in top["trash_group"]]
        fig=go.Figure(go.Bar(x=top["n"],y=top["trash_item"],orientation="h",
            marker_color=colors,
            customdata=top[["trash_group","pct"]].values,
            hovertemplate="<b>%{y}</b><br>Category: %{customdata[0]}<br>Count: %{x:,}<br>Share: %{customdata[1]}%<extra></extra>"))
        fb(fig,"Total Count","Item",h=max(900,20*len(top)),leg=False,
            title="All 56 Individual Item Types — Ranked by Total Count"); show(fig,"cat_all56")
        fig_note(
            "Every item type in the 56-item survey protocol, ranked from rarest to most common.",
            "Food Wrappers lead at 5,471 items. Syringes and drug paraphernalia appear low in count but are high in health significance.",
            "Hover for category and percentage. Items near the bottom may still matter for ecological or health risk beyond their count.",
            "Items recorded as zero across all events are excluded. A long tail of low-count items is scientifically important — presence/absence matters for biodiversity and pollution assessments."
        )

    elif sel_cat == "Category Share — Proportional Breakdown":
        ct2=df.groupby("trash_group")["n"].sum().sort_values(ascending=False).reset_index()
        ct2=ct2[ct2["n"]>0]
        fig=px.pie(ct2,values="n",names="trash_group",hole=.42,color_discrete_sequence=PAL)
        fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=10)
        fig.update_layout(height=540,paper_bgcolor="rgba(0,0,0,0)",font=dict(family="DM Sans"),
            margin=dict(l=8,r=8,t=36,b=8),
            title=dict(text="Category Composition — Share of All Recorded Items",
                font=dict(family="Cormorant Garamond, serif",size=16,color=C["green"]),x=0))
        show(fig,"cat_pie2")
        last_updated_insight(df,"general")
        fig_note("Proportional breakdown — each slice shows one category as a percentage of the total.",
            "Food Packaging at ~33% means 1 in 3 items found is food-related packaging.",
            "Hover for exact percentages. Small slices are not unimportant — Rx/Drugs at under 1% still carries major health risk.",
            "Always pair with the ranked bar chart — proportions hide absolute scale.")

    elif sel_cat == "Top 10 Heaviest vs Bottom 9 Lightest Categories":
        ct3=df.groupby("trash_group")["n"].sum().reset_index().sort_values("n",ascending=False)
        top10=ct3.head(10); bot9=ct3.tail(9)
        c1c,c2c=st.columns(2)
        with c1c:
            fig=px.bar(top10.sort_values("n"),x="n",y="trash_group",orientation="h",
                color_discrete_sequence=[C["brick"]],text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total Items","",h=380,leg=False,title="Top 10 Heaviest Categories"); show(fig,"cat_top10")
        with c2c:
            fig=px.bar(bot9.sort_values("n"),x="n",y="trash_group",orientation="h",
                color_discrete_sequence=[C["sage"]],text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total Items","",h=380,leg=False,title="Bottom 9 Categories"); show(fig,"cat_bot9")
        fig_note("The top 10 categories account for over 95% of all recorded items.",
            "Shows the skewed distribution — a few categories drive the problem while many others are present but minor.",
            "Left = heaviest. Right = lightest. Even the lightest categories — Rx/Drugs (189) and Auto (167) — have outsized ecological or safety impact.",
            "The top 3 alone (Food Packaging + Clothing + Plastic Bags) represent approximately 53% of all items.")

    elif sel_cat == "Average Items per Survey Event by Category":
        avg_cat=df.groupby("trash_group").agg(total=("n","sum"),events=("event_id","nunique")).reset_index()
        avg_cat["avg"]=(avg_cat["total"]/avg_cat["events"]).round(2)
        avg_cat=avg_cat.sort_values("avg",ascending=True)
        avg_cat["color"]=avg_cat["trash_group"].map(lambda g: C["brick"] if g in HEALTH_HAZARD_GROUPS else C["green"])
        fig=go.Figure(go.Bar(x=avg_cat["avg"],y=avg_cat["trash_group"],orientation="h",
            marker_color=avg_cat["color"],text=avg_cat["avg"].round(1),textposition="outside"))
        fb(fig,"Avg Items per Event","",h=max(560,32*len(avg_cat)),leg=False,
            title="Average Items per Survey Event — All 19 Categories"); show(fig,"cat_avg2")
        fig_note("Mean total items per survey event for each category.",
            "Adjusts for recording frequency — a category recorded across 100 events is compared fairly to one recorded across 20.",
            "Higher = more items found per visit. Red = health hazard categories.",
            "Food Packaging will top this chart too — its high average is partly structural (11 sub-items) but also reflects genuine prevalence.")

    elif sel_cat == "Beverage Containers — Full Breakdown":
        bev=df[df["trash_group"].isin(BEVERAGE_GROUPS)].copy()
        c1c,c2c=st.columns([2,3])
        with c1c:
            bt=bev.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(bt,x="n",y="trash_group",orientation="h",
                color_discrete_sequence=[C["water"]],text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Category",h=380,leg=False,title="Beverage Categories — Totals"); show(fig,"bev_grp")
        with c2c:
            bi=bev.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(bi,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_sequence=PAL,text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=500,title="Beverage Items — All Sub-Types"); show(fig,"bev_items")
        last_updated_insight(df,"general")
        fig_note("All beverage container categories and their sub-type breakdown.",
            "Beverage containers represent single-use plastics and recyclables that ended up in the river corridor.",
            "Water bottles (1,635) are the most common single beverage item — many from encampments. Beer bottles lead alcohol.",
            "The presence of large quantities of Styrofoam cups is environmentally significant — Styrofoam does not biodegrade and fragments into microplastics.")

    elif sel_cat == "Cups — Styrofoam vs Plastic vs Paper":
        cups=df[df["trash_group"]=="Cups"].groupby("trash_item")["n"].sum().reset_index().sort_values("n",ascending=False)
        cups["pct"]=(100*cups["n"]/max(cups["n"].sum(),1)).round(1)
        c1c,c2c=st.columns(2)
        with c1c:
            fig=px.bar(cups.sort_values("n",ascending=True),x="n",y="trash_item",orientation="h",
                color="trash_item",color_discrete_sequence=PAL,text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Cup Type",h=340,leg=False,title="Cups — Sub-Type Breakdown"); show(fig,"cups_bar")
        with c2c:
            fig=px.pie(cups,values="n",names="trash_item",color_discrete_sequence=PAL,hole=.4)
            fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=11)
            fig.update_layout(height=340,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
                margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"cups_pie")
        fig_note("The Cups category broken into 5 sub-types.",
            "Styrofoam cups are particularly problematic — they fragment into microplastics, clog drainage, and are excluded from recycling.",
            "Polar Pop cups are the large convenience store cups associated with Circle K — useful for source attribution and retailer partnership conversations.",
            "Styrofoam (Other) is the most common sub-type — these are generic foam cups from a wide range of food service sources.")

    elif sel_cat == "Food Packaging — All 11 Sub-Items":
        fp=df[df["trash_group"]=="Food Packaging"].groupby("trash_item")["n"].sum().reset_index().sort_values("n",ascending=True)
        fp["pct"]=(100*fp["n"]/max(fp["n"].sum(),1)).round(1)
        fig=px.bar(fp,x="n",y="trash_item",orientation="h",color="trash_item",
            color_discrete_sequence=PAL,
            text=[f"{int(v):,} ({p}%)" for v,p in zip(fp["n"],fp["pct"])])
        fig.update_traces(textposition="outside")
        fb(fig,"Total Items","Item Type",h=max(440,36*len(fp)),leg=False,
            title="Food Packaging — All 11 Sub-Types Ranked"); show(fig,"fp_items")
        last_updated_insight(df,"category","Food Packaging")
        fig_note("Food Packaging is the single largest category at 10,694 items — spanning 11 distinct sub-types.",
            "Food Wrappers alone account for 51% of all Food Packaging (5,471 items). Straws are #3 at 860.",
            "6-pack rings and straws pose direct entanglement risk to birds and reptiles in the riparian corridor.",
            "Non-cup styrofoam (805) is especially harmful — it breaks into small beads that are indistinguishable from food particles to wildlife.")

    elif sel_cat == "Alcohol Containers — Beer vs Liquor Over Time":
        alc=df[df["trash_group"].isin(["Beer","Liquor"])].copy()
        if "date" in alc.columns and alc["date"].notna().any():
            ts_alc=alc.groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ts_alc,x="date",y="n",color="trash_group",markers=True,
                color_discrete_map={"Beer":C["amber"],"Liquor":C["brick"]})
            fb(fig,"Quarter","Items",h=440,title="Alcohol Containers — Beer vs Liquor Quarterly"); show(fig,"alc_ts")
            fig_note("Quarterly counts of Beer and Liquor items across the survey record.",
                "Alcohol containers are associated with encampments, informal gatherings, and chronic littering. Understanding their trajectory helps community engagement planning.",
                "Amber = Beer, Red = Liquor. Rising lines indicate increasing alcohol-related litter.",
                "Beer bottles (789 total) and Liquor glass (598) are heavy items that persist in the environment for decades.")
        else:
            st.info("No date data available for this figure.")

    elif sel_cat == "Recyclable vs Non-Recyclable — Item Counts":
        rec_df=df.copy()
        rec_df["recyclable"]=rec_df["trash_group"].map(lambda g:
            "Recyclable" if g in RECYCLABLE_GROUPS else "Non-Recyclable")
        r_tot=rec_df.groupby("recyclable")["n"].sum().reset_index()
        r_tot["pct"]=(100*r_tot["n"]/max(r_tot["n"].sum(),1)).round(1)
        r_grp=rec_df.groupby(["recyclable","trash_group"])["n"].sum().reset_index()
        c1c,c2c=st.columns([1,2])
        with c1c:
            fig=px.pie(r_tot,values="n",names="recyclable",hole=.5,
                color_discrete_map={"Recyclable":C["water"],"Non-Recyclable":C["brick"]})
            fig.update_traces(textinfo="percent+label",textfont_size=12)
            fig.update_layout(height=300,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
                margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"rec_pie")
        with c2c:
            r_grp_s=r_grp.sort_values("n",ascending=True)
            fig=px.bar(r_grp_s,x="n",y="trash_group",color="recyclable",orientation="h",
                color_discrete_map={"Recyclable":C["water"],"Non-Recyclable":C["brick"]},text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total Items","",h=max(540,30*len(r_grp_s)),title="Recyclable vs Non-Recyclable by Category"); show(fig,"rec_bar")
        st.markdown(
            f'<div style="font-size:12px;padding:8px 14px;background:{C["sand"]};border-radius:6px;margin:8px 0;color:{C["muted"]};">'
            f'Classification based on <strong>City of Tucson recycling guidelines</strong>. '
            f'<span style="color:{C["water"]};font-weight:700;">Blue = Recyclable</span> (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Paper Litter) &nbsp;|&nbsp; '
            f'<span style="color:{C["brick"]};font-weight:700;">Red = Non-Recyclable</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        fig_note("All 19 categories classified by City of Tucson recycling eligibility.",
            "Approximately 16% of items by count are technically recyclable — but none are being recycled because they end up in the river corridor.",
            "Blue = recyclable (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Paper Litter). These represent a missed diversion opportunity.",
            "A beverage container deposit program (bottle bill) would directly target the recyclable fraction. This data can directly support such policy advocacy.")

    elif sel_cat == "Floatable vs Non-Floatable — River Health Risk":
        fl_df=df.copy()
        fl_df["floatable"]=fl_df["trash_group"].map(lambda g:
            "Floatable" if g in FLOATABLE_GROUPS else "Non-Floatable")
        f_tot=fl_df.groupby("floatable")["n"].sum().reset_index()
        f_tot["pct"]=(100*f_tot["n"]/max(f_tot["n"].sum(),1)).round(1)
        f_grp=fl_df.groupby(["floatable","trash_group"])["n"].sum().reset_index()
        c1c,c2c=st.columns([1,2])
        with c1c:
            fig=px.pie(f_tot,values="n",names="floatable",hole=.5,
                color_discrete_map={"Floatable":"#2471a3","Non-Floatable":"#7f8c8d"})
            fig.update_traces(textinfo="percent+label",textfont_size=12)
            fig.update_layout(height=300,paper_bgcolor="rgba(0,0,0,0)",showlegend=False,
                margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"flt_pie")
        with c2c:
            f_grp_s=f_grp.sort_values("n",ascending=True)
            fig=px.bar(f_grp_s,x="n",y="trash_group",color="floatable",orientation="h",
                color_discrete_map={"Floatable":"#2471a3","Non-Floatable":"#7f8c8d"},text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total Items","",h=max(540,30*len(f_grp_s)),title="Floatable vs Non-Floatable by Category"); show(fig,"flt_bar")
        st.markdown(
            f'<div style="font-size:12px;padding:8px 14px;background:{C["sand"]};border-radius:6px;margin:8px 0;color:{C["muted"]};">'
            f'Floatable items travel downstream during rain events and reach waterways. '
            f'<span style="color:#2471a3;font-weight:700;">Blue = Floatable</span> &nbsp;|&nbsp; '
            f'<span style="color:#7f8c8d;font-weight:700;">Gray = Non-Floatable</span> &nbsp;|&nbsp; '
            f'Based on Sonoran Institute field classification.'
            f'</div>',
            unsafe_allow_html=True
        )
        fig_note("Items classified by ability to float and travel downstream during storm events.",
            "Approximately 63% of all recorded items are floatable — meaning the majority of Santa Cruz River litter is at risk of entering the water column during monsoon events.",
            "Blue = enters waterways during rain. Food Packaging, Plastic Bags, Cups, and all beverage bottles are floatable.",
            "This analysis directly supports ADEQ stormwater permit compliance, EPA Section 319 nonpoint source pollution reporting, and conservation grant applications.")

    elif sel_cat == "Health Hazard Items — Rx, Drugs, Nicotine, Toiletries":
        hh=df[df["trash_group"].isin(HEALTH_HAZARD_GROUPS)].copy()
        c1c,c2c=st.columns(2)
        with c1c:
            ht=hh.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(ht,x="n",y="trash_group",orientation="h",
                color="trash_group",
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Category",h=280,leg=False,title="Health Hazard Categories — Totals"); show(fig,"hh_grp")
        with c2c:
            hi=hh.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(hi,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=280,title="Health Hazard Items — Sub-Types"); show(fig,"hh_items")
        if "date" in hh.columns and hh["date"].notna().any():
            ts_hh=hh.groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ts_hh,x="date",y="n",color="trash_group",markers=True,
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]})
            fb(fig,"Quarter","Items",h=320,title="Health Hazard Items Over Time"); show(fig,"hh_ts")
        fig_note("Three categories with direct public health risk: Rx/Drugs, Nicotine, and Toiletries.",
            "Syringes (101 recorded) and drug paraphernalia (88) create needle-stick hazard for field staff and community volunteers. Nicotine (1,255) is the most numerically prevalent hazard.",
            "All three require special handling protocols and personal protective equipment during removal events.",
            "These numbers should be treated as minimums — syringes are likely underreported due to safety concerns and incomplete detection during surveys.")

    elif sel_cat == "Bulk & Large Debris — Appliances, Construction, Auto":
        bk=df[df["trash_group"].isin(BULK_DEBRIS_GROUPS)].copy()
        c1c,c2c=st.columns(2)
        with c1c:
            bt2=bk.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(bt2,x="n",y="trash_group",orientation="h",
                color="trash_group",
                color_discrete_map={"Appliances":C["earth"],"Construction":C["sage"],"Auto":C["muted"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","",h=260,leg=False,title="Bulk Debris — Category Totals"); show(fig,"bk_grp")
        with c2c:
            bi2=bk.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(bi2,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_map={"Appliances":C["earth"],"Construction":C["sage"],"Auto":C["muted"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=400,title="Bulk Debris — All Sub-Types"); show(fig,"bk_items")
        fig_note("Appliances (550), Construction (1,147), and Auto (167) are large items requiring equipment to remove.",
            "Construction debris — particularly Small Items (1,104) — indicates illegal dumping of building waste along the corridor.",
            "By item count these seem modest, but by weight and volunteer-hours required for removal they represent a disproportionate burden.",
            "Tires (48) create standing water that breeds mosquitoes. Shopping carts signal commercial area drainage. These require coordinated heavy equipment removal.")

    elif sel_cat == "Category Risk Profile — Composite View":
        risk_data=[]
        for g in GROUP_ORDER:
            if g not in df["trash_group"].unique(): continue
            total=df[df["trash_group"]==g]["n"].sum()
            risk_data.append({"Category":g,"Total Items":int(total),
                "Recyclable": "Yes" if g in RECYCLABLE_GROUPS else "No",
                "Floatable":  "Yes" if g in FLOATABLE_GROUPS else "No",
                "Health Hazard": "Yes" if g in HEALTH_HAZARD_GROUPS else "No",
                "Bulk Debris": "Yes" if g in BULK_DEBRIS_GROUPS else "No"})
        risk_df=pd.DataFrame(risk_data)
        risk_melt=risk_df.melt(id_vars=["Category","Total Items"],
            value_vars=["Recyclable","Floatable","Health Hazard","Bulk Debris"],
            var_name="Risk Dimension",value_name="Flag")
        risk_melt=risk_melt[risk_melt["Flag"]=="Yes"].copy()
        fig=px.scatter(risk_melt,x="Total Items",y="Category",color="Risk Dimension",size="Total Items",
            size_max=30,
            color_discrete_map={"Recyclable":C["water"],"Floatable":"#2471a3","Health Hazard":C["brick"],"Bulk Debris":C["earth"]},
            category_orders={"Category":list(reversed(GROUP_ORDER))})
        fb(fig,"Total Items","",h=max(540,30*len(risk_df)),
            title="Category Risk Profile — Volume vs Environmental Risk Dimensions"); show(fig,"risk_scatter")
        fig_note("Each dot = a category flagged with a risk dimension. Larger and further right = more items.",
            "Shows which categories combine high volume with high environmental or health risk.",
            "Food Packaging is Floatable. Rx/Drugs is a Health Hazard. Construction is Bulk Debris. Beer is Recyclable.",
            "Categories that are BOTH high-volume AND high-risk are priority targets — e.g. Plastic Bags (3,649 items, Floatable, Non-Recyclable).")

    elif sel_cat == "Category Trends Over Time — Top 6 Quarterly":
        top6=df.groupby("trash_group")["n"].sum().nlargest(6).index.tolist()
        if "date" in df.columns and df["date"].notna().any():
            ct6=df[df["trash_group"].isin(top6)].groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ct6,x="date",y="n",color="trash_group",markers=True,color_discrete_sequence=PAL)
            fb(fig,"Quarter","Items",h=480,title="Top 6 Categories — Quarterly Item Counts"); show(fig,"cat_trend2")
            last_updated_insight(df,"general")
            fig_note("Quarterly trends for the 6 highest-volume categories.",
                "Reveals whether the category composition is stable or if specific categories are increasing.",
                "Lines diverging upward = that category is growing. Parallel lines = uniform change across categories.",
                "A declining Food Packaging trend would signal intervention success. An increasing Clothing trend may reflect changing encampment patterns along the corridor.")
        else:
            st.info("No date data available.")

    elif sel_cat == "Year-over-Year Change by Category":
        if "year" in df.columns and df["year"].notna().any():
            yoy=df.groupby(["year","trash_group"])["n"].sum().reset_index()
            yoy["year_str"]=yoy["year"].astype(int).astype(str)
            ord_cats=[g for g in GROUP_ORDER if g in yoy["trash_group"].unique()]
            fig=px.bar(yoy,x="year_str",y="n",color="trash_group",barmode="group",
                color_discrete_sequence=PAL,category_orders={"trash_group":ord_cats})
            fb(fig,"Year","Total Items",h=500,title="Annual Category Totals — Year-over-Year Comparison"); show(fig,"yoy_cat")
            fig_note("Each cluster of bars = one year, broken into all categories.",
                "Reveals long-term trends by category — whether specific waste types are growing or declining.",
                "Colors are consistent across years. A growing bar = more items in that category that year.",
                "Be cautious comparing years with very different survey effort — more events in a year will produce higher counts regardless of actual litter density.")
        else:
            st.info("No year data available.")

    elif sel_cat == "Category Composition — How Mix Changed by Year":
        if "year" in df.columns and df["year"].notna().any():
            yp=df.groupby(["year","trash_group"])["n"].sum().reset_index()
            yp_tot=yp.groupby("year")["n"].sum().reset_index(name="yr_total")
            yp=yp.merge(yp_tot,on="year")
            yp["share"]=100*yp["n"]/yp["yr_total"]
            yp["year_str"]=yp["year"].astype(int).astype(str)
            ord_cats=[g for g in GROUP_ORDER if g in yp["trash_group"].unique()]
            fig=px.bar(yp,x="year_str",y="share",color="trash_group",barmode="stack",
                color_discrete_sequence=PAL,category_orders={"trash_group":ord_cats})
            fb(fig,"Year","Share of Total (%)",h=500,title="Category Composition by Year — 100% Stacked Shares"); show(fig,"comp_yr")
            fig_note("100% stacked bars — each bar totals 100%, showing category SHARE each year.",
                "Removes the effect of varying survey effort and shows whether the MIX of items is changing.",
                "A growing color slice = that category is increasing as a proportion of all litter.",
                "This is more ecologically meaningful than raw totals for detecting genuine composition shifts independent of survey frequency.")
        else:
            st.info("No year data available.")

    elif sel_cat == "Category Mix by River Segment":
        if "seg" in df.columns:
            sg2=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            ord_cats=[g for g in GROUP_ORDER if g in sg2["trash_group"].unique()]
            fig=px.bar(sg2,x="n",y="seg",color="trash_group",orientation="h",barmode="stack",
                color_discrete_sequence=PAL,
                category_orders={"seg":list(reversed(SEG_ORDER[:-1])),"trash_group":ord_cats})
            fb(fig,"Total Items","Segment",h=400,title="Category Composition by River Segment"); show(fig,"seg_cat")
            color_legend("Segment Colors", mode="segments")
            fig_note("Stacked bars showing category composition across the four named river reaches.",
                "Reveals whether certain reaches have distinctly different waste profiles due to adjacent land use.",
                "A segment with unusually high Clothing indicates encampments. High Construction suggests illegal dumping nearby.",
                "Only sites with confirmed segment labels are included. Unlabeled sites appear under 'Other' which is excluded here.")
        else:
            st.info("No segment data.")

    elif sel_cat == "Segment Specialization — Top Categories per Reach":
        if "seg" in df.columns:
            named_segs=[s for s in SEG_ORDER if s != "Other"]
            seg_tabs=st.tabs(named_segs)
            for i,seg in enumerate(named_segs):
                with seg_tabs[i]:
                    seg_df=df[df["seg"]==seg].groupby("trash_group")["n"].sum().reset_index()
                    seg_tot=max(seg_df["n"].sum(),1)
                    seg_df["pct"]=(100*seg_df["n"]/seg_tot).round(1)
                    seg_df=seg_df[seg_df["n"]>0].sort_values("n",ascending=True)
                    if len(seg_df)==0:
                        st.info(f"No data for {seg} segment.")
                        continue
                    fig=px.bar(seg_df,x="n",y="trash_group",orientation="h",
                        color_discrete_sequence=[SEG_COLORS.get(seg,C["green"])],
                        text=[f"{int(v):,} ({p}%)" for v,p in zip(seg_df["n"],seg_df["pct"])])
                    fig.update_traces(textposition="outside")
                    seg_tot_n=int(df[df["seg"]==seg]["n"].sum())
                    fb(fig,"Total Items","",h=max(380,30*len(seg_df)),leg=False,
                        title=f"{seg} — All Categories ({seg_tot_n:,} total items)"); show(fig,f"seg_spec_{i}")
            fig_note("Top categories for each river segment shown in individual tabs.",
                "Identifies segment-specific waste profiles — useful for targeted cleanup events and reporting to local jurisdictions.",
                "Compare the relative share of each category across segments — a category dominant in one segment but minor in another points to local source patterns.",
                "Use alongside the Map page to connect geographic patterns with specific land uses, outfalls, or encampment locations along each reach.")
        else:
            st.info("No segment data.")

    elif sel_cat == "Full Item-Level Statistics Table":
        item_tbl=df.groupby(["trash_group","trash_item"])["n"].agg(Total="sum",Records="count",Mean="mean").reset_index()
        item_tbl["% of All Items"]=(100*item_tbl["Total"]/total_all).round(2)
        item_tbl["Recyclable"]=item_tbl["trash_group"].map(lambda g: "Yes" if g in RECYCLABLE_GROUPS else "No")
        item_tbl["Floatable"]=item_tbl["trash_group"].map(lambda g: "Yes" if g in FLOATABLE_GROUPS else "No")
        item_tbl["Health Hazard"]=item_tbl["trash_group"].map(lambda g: "Yes" if g in HEALTH_HAZARD_GROUPS else "No")
        item_tbl=item_tbl[item_tbl["Total"]>0].sort_values("Total",ascending=False).round(2).reset_index(drop=True)
        item_tbl.index=range(1,len(item_tbl)+1)
        item_tbl.columns=["Category","Item","Total Count","# Records","Mean per Record","% of All Items","Recyclable","Floatable","Health Hazard"]
        st.dataframe(item_tbl, use_container_width=True, height=580)
        tbl_note("Every individual item type with cumulative statistics. Records = number of data entries. Mean per Record = average count per entry (not per event). % is relative to the current filter. Recyclable = City of Tucson standard. Floatable = river health risk. Health Hazard = direct human contact risk.")

    elif sel_cat == "Category Group Summary Table":
        grp_tbl=df.groupby("trash_group")["n"].agg(Total="sum",Records="count",Mean="mean").reset_index()
        grp_tbl["% of Total"]=(100*grp_tbl["Total"]/total_all).round(1)
        grp_tbl["Rank"]=grp_tbl["Total"].rank(ascending=False).astype(int)
        grp_tbl["Recyclable"]=grp_tbl["trash_group"].map(lambda g: "Yes" if g in RECYCLABLE_GROUPS else "No")
        grp_tbl["Floatable"]=grp_tbl["trash_group"].map(lambda g: "Yes" if g in FLOATABLE_GROUPS else "No")
        grp_tbl["Health Hazard"]=grp_tbl["trash_group"].map(lambda g: "Yes" if g in HEALTH_HAZARD_GROUPS else "No")
        grp_tbl=grp_tbl[grp_tbl["Total"]>0].sort_values("Total",ascending=False).round(2).reset_index(drop=True)
        grp_tbl.index=range(1,len(grp_tbl)+1)
        grp_tbl.columns=["Category","Total Items","# Records","Mean per Record","% of Total","Rank","Recyclable","Floatable","Health Hazard"]
        st.dataframe(grp_tbl, use_container_width=True, height=500)
        tbl_note("All 19 categories with rank, statistics, and environmental classifications. Rank 1 = most items recorded. Recyclable = City of Tucson standard. Floatable = river health classification. Health Hazard = direct human exposure risk. Use this table in any report, grant application, or agency submission.")

    st.markdown('</div>', unsafe_allow_html=True)


elif page == "Locations":
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)
    st.markdown('<div class="pg-title">Locations & Sites</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Site-level analysis of trash burden across all recorded survey locations. Sites with GPS coordinates are ordered <strong>North to South</strong> by latitude. Statistics (mean, SD, SE, CV) are computed at the survey-event level — each event at a site counts as one observation.</div>', unsafe_allow_html=True)

    with st.expander("Filter Data", expanded=False):
        lf=render_filters(long, kp="loc", cats=False)
    stat_strip(long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)
    # Build N→S triplicate stats
    ss=build_site_stats_ns(df)
    # Also keep old simple stats for backward compat
    site_st=df.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),
        mean=("n","mean"),mx=("n","max"),mn_v=("n","min"),sd=("n","std")).reset_index()
    site_st["avg_per_event"]=(site_st["total"]/site_st["events"]).round(1)
    site_st["sd"]=site_st["sd"].fillna(0).round(1)
    site_st=site_st.sort_values("total",ascending=False).reset_index(drop=True)

    # KPI strip
    grand_mean = ss["mean"].mean() if len(ss)>0 else 0
    grand_sd   = ss["sd"].mean() if len(ss)>0 else 0
    st.markdown(f"""<div class="stat-strip">
    <div class="stat-item"><span class="stat-v">{len(ss) if len(ss)>0 else len(site_st)}</span><span class="stat-l">Total Locations</span></div>
    <div class="stat-item"><span class="stat-v">{int(site_st["total"].max()):,}</span><span class="stat-l">Max Items at One Site</span></div>
    <div class="stat-item"><span class="stat-v">{grand_mean:.1f}</span><span class="stat-l">Grand Mean / Event</span></div>
    <div class="stat-item"><span class="stat-v">±{grand_sd:.1f}</span><span class="stat-l">Mean SD Across Sites</span></div>
    <div class="stat-item"><span class="stat-v">{int(site_st["events"].sum()):,}</span><span class="stat-l">Total Events</span></div>
    </div>""", unsafe_allow_html=True)

    color_legend("River Segment Colors", mode="segments")

    loc_tab1, loc_tab2, loc_tab3, loc_tab4 = st.tabs([
        "North to South — Mean", "North to South — Variability",
        "Segment Comparison", "Full Statistics Table"
    ])

    with loc_tab1:
        if len(ss)>0:
            card_open("Average Items per Survey Event — Sites Ordered North to South",
                      "Each bar = one survey site. Height = mean items per event at that site. Sites are ordered geographically from northernmost (top) to southernmost (bottom). Color indicates river segment.")
            ns_show = ss[ss["lat_num"].notna()].sort_values("north_rank")
            if len(ns_show)>0:
                fig=px.bar(ns_show, x="mean", y="site_display", orientation="h",
                    color="seg", color_discrete_map=SEG_COLORS,
                    error_x="se",
                    category_orders={"site_display": ns_show["site_display"].tolist()})
                fig.update_yaxes(categoryorder="array", categoryarray=ns_show["site_display"].tolist(), autorange="reversed")
                fb(fig,"Mean Items per Event","Site (North to South)",
                   h=max(560,26*len(ns_show)),
                   title="Mean Items per Survey Event — North to South"); show(fig,"ns_mean")
                last_updated_insight(df, chart_type="general")
            fig_note(
                "Mean number of items recorded per survey event at each site, ordered north to south by GPS latitude.",
                "Geographic ordering reveals whether trash burden is clustered in certain reaches of the corridor.",
                "Longer bars = heavier sites. Error bars show ±1 standard error (SE). Sites at the top are the northernmost.",
                "SE = SD ÷ √n. A small SE means the site's mean is reliably estimated. A large SE means high variability between events at that site."
            )

        section_title("Site Statistics — North to South")
        st.markdown('<div class="sec-sub">Full statistical summary for sites with GPS coordinates, ordered north to south. N = number of survey events. Mean ± SD are computed across events at each site.</div>', unsafe_allow_html=True)
        if len(ns_show)>0:
            tbl = ns_show[["north_rank","site_display","seg","n_plots","mean","sd","se","cv","range","total","lat_num","lon"]].copy()
            tbl = tbl.rename(columns={"north_rank":"Rank (N→S)","site_display":"Site","seg":"Segment",
                "n_plots":"N (events)","mean":"Mean","sd":"Std Dev","se":"Std Error",
                "cv":"CV (%)","range":"Range","total":"Total","lat_num":"Latitude","lon":"Longitude"})
            tbl["CV (%)"]=tbl["CV (%)"].apply(lambda x: f"{100*x:.1f}" if pd.notna(x) else "—")
            tbl = tbl.round(2)
            st.dataframe(tbl, use_container_width=True, height=500)
            tbl_note("Mean = average items per event. SD = standard deviation (spread across events). SE = standard error (reliability of mean). CV = coefficient of variation (SD÷Mean×100) — higher % means more variable site. Range = max minus min across events. Rank 1 = northernmost site with coordinates.")

    with loc_tab2:
        if len(ss)>0:
            ns_show = ss[ss["lat_num"].notna()].sort_values("north_rank")
            c1v,c2v = st.columns(2)
            with c1v:
                card_open("Standard Deviation by Site — North to South",
                          "SD measures how much individual events vary at each site. A site with SD=0 had exactly the same count every visit. High SD = unpredictable or patchy litter.")
                fig=px.bar(ns_show,x="sd",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
                fig.update_yaxes(categoryorder="array",categoryarray=ns_show["site_display"].tolist(),autorange="reversed")
                fb(fig,"Standard Deviation","Site",h=max(500,24*len(ns_show)),title="Within-Site Variability (SD) — North to South"); show(fig,"ns_sd")
                fig_note("Standard deviation of total items per event at each site.",
                    "High SD indicates inconsistency — some visits found a lot of trash, others very little.",
                    "Longer bars = more variable sites. A site can have a low mean but high SD if trash events are sporadic.",
                    "SD is not comparable across sites with very different means. Use CV for that.")
            with c2v:
                card_open("Coefficient of Variation (CV) by Site — North to South",
                          "CV = SD ÷ Mean × 100. It normalizes variability so sites with different mean burden can be fairly compared.")
                ns_show_cv = ns_show[ns_show["cv"].notna()].copy()
                ns_show_cv["cv_pct"]=(ns_show_cv["cv"]*100).round(1)
                if len(ns_show_cv)>0:
                    fig=px.bar(ns_show_cv,x="cv_pct",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
                    fig.update_yaxes(categoryorder="array",categoryarray=ns_show_cv["site_display"].tolist(),autorange="reversed")
                    fb(fig,"CV (%)","Site",h=max(500,24*len(ns_show_cv)),title="Coefficient of Variation (CV%) — North to South"); show(fig,"ns_cv")
                    fig_note("CV = (SD ÷ Mean) × 100, expressed as a percentage.",
                        "Unlike SD, CV adjusts for the size of the mean so you can compare variability across sites fairly.",
                        "CV < 30% = relatively consistent. CV 30–100% = moderate variability. CV > 100% = highly unpredictable.",
                        "A clean site with CV=150% is more unpredictable than a heavy site with CV=25%.")

            card_open("Range of Items per Event by Site — North to South",
                      "Range = maximum items recorded minus minimum items recorded across all events at that site. Simple and easy to communicate in presentations.")
            fig=px.bar(ns_show,x="range",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
            fig.update_yaxes(categoryorder="array",categoryarray=ns_show["site_display"].tolist(),autorange="reversed")
            fb(fig,"Range (Max − Min)","Site",h=max(500,24*len(ns_show)),title="Range of Items per Event — North to South"); show(fig,"ns_range")
            fig_note("The difference between the heaviest and lightest events recorded at each site.",
                "Range is intuitive for non-technical audiences.",
                "A range of 0 means the same count every visit. A large range means the site fluctuates dramatically.",
                "Range is sensitive to extreme outlier events, unlike SD or CV.")

    with loc_tab3:
        c1s,c2s = st.columns(2)
        with c1s:
            card_open("Total Items by River Segment",
                      "Sum of all recorded items across all events and sites within each named segment. Only sites with segment labels are included.")
            seg_tot=df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["n"].sum().reset_index()
            fig=px.bar(seg_tot,x="seg",y="n",color="seg",color_discrete_map=SEG_COLORS,category_orders={"seg":SEG_ORDER})
            fb(fig,"Segment","Total Items",h=320,leg=False,title="Total Items by River Segment"); show(fig,"loc_seg")
            fig_note("Cumulative sum of all recorded items within each river segment.",
                "Identifies which reach contributes most to the overall corridor burden.",
                "Taller bars = more total trash. This is influenced by both the number of sites and their individual burden.",
                "A segment with many lightly-visited sites can look heavy due to accumulated counts.")
        with c2s:
            card_open("Survey Events by River Segment",
                      "Number of distinct survey events within each segment — shows sampling effort distribution.")
            seg_ev=df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["event_id"].nunique().reset_index(name="events")
            fig=px.bar(seg_ev,x="seg",y="events",color="seg",color_discrete_map=SEG_COLORS)
            fb(fig,"Segment","# Events",h=320,leg=False,title="Survey Events by River Segment"); show(fig,"loc_segev")
            fig_note("Number of individual survey events per segment.",
                "Unequal sampling effort means direct total comparisons should be interpreted with care.",
                "Compare with total items chart — a segment with more events should be expected to have more items.",
                "Normalizing by events (using mean) is more fair when event counts differ substantially.")
        color_legend("Segment Colors", mode="segments")

        section_title("Segment Summary Table")
        seg_summary = df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg").agg(
            Total_Items=("n","sum"), Events=("event_id","nunique"),
            Sites=("site_label","nunique"), Mean_per_event=("n","mean")
        ).reset_index().rename(columns={"seg":"River Segment","Total_Items":"Total Items",
            "Events":"# Events","Sites":"# Sites","Mean_per_event":"Mean per Event"})
        seg_summary = seg_summary.round(1)
        st.dataframe(seg_summary, use_container_width=True, height=240)
        tbl_note("Mean per Event is computed across all individual item records, not event totals. Use 'Total Items ÷ # Events' for event-level mean.")

        section_title("Top 20 Sites by Average Items per Event")
        top20_avg=site_st.nlargest(20,"avg_per_event").sort_values("avg_per_event")
        card_open("Sites Ranked by Average Items per Event",
                  "Per-event average is a fairer metric than total count — it adjusts for how many times a site was visited.")
        fig=px.bar(top20_avg,x="avg_per_event",y="site_label",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
        fb(fig,"Avg Items / Event",None,h=max(460,22*len(top20_avg)),title="Top 20 Sites — Average Items per Event"); show(fig,"loc_avg")
        fig_note("Average total items recorded per survey visit at each site.",
            "Avoids penalizing well-sampled sites that appear heavier only because they were visited more.",
            "A site visited once with 300 items scores higher than one visited 10 times averaging 20 items.",
            "Use alongside visit counts — a high average based on a single visit may not be reliable.")
        card_close()

    with loc_tab4:
        seg_filter2=st.selectbox("Filter by River Segment",["All"]+SEG_ORDER[:-1], key="loc_seg_filter2")
        view_order=st.radio("Sort order",["North to South (GPS)","By Total Items","By Mean per Event"],horizontal=True)

        if len(ss)>0:
            tbl_full = ss.merge(site_st[["site_label","total","events","avg_per_event"]],on="site_label",how="left",suffixes=("","_ev"))
            if seg_filter2!="All": tbl_full=tbl_full[tbl_full["seg"]==seg_filter2]
            if view_order=="North to South (GPS)":
                tbl_full=tbl_full.sort_values(["north_rank","site_label"])
            elif view_order=="By Total Items":
                tbl_full=tbl_full.sort_values("total",ascending=False)
            else:
                tbl_full=tbl_full.sort_values("mean",ascending=False)

            disp=tbl_full[["site_display","seg","n_plots","mean","sd","se","cv","range","total","lat_num","lon"]].copy()
            disp["cv_pct"]=(disp["cv"]*100).round(1)
            disp=disp.drop(columns=["cv"])
            disp=disp.rename(columns={"site_display":"Site (N→S)","seg":"Segment","n_plots":"N Events",
                "mean":"Mean","sd":"SD","se":"SE","cv_pct":"CV (%)","range":"Range",
                "total":"Total","lat_num":"Latitude","lon":"Longitude"})
            disp=disp.round(2).reset_index(drop=True); disp.index=range(1,len(disp)+1)
            st.dataframe(disp, use_container_width=True, height=600)
            tbl_note("N Events = number of survey events at this site. Mean ± SD computed across events. SE = SD÷√N (reliability of mean estimate). CV = SD÷Mean×100 (normalized variability). Range = Max−Min across events. Sites without GPS coordinates may not have a North→South rank.")
        else:
            filtered_st=site_st if seg_filter2=="All" else site_st[site_st["seg"]==seg_filter2]
            disp=filtered_st[["site_label","seg","total","events","avg_per_event","mean","sd","mx","mn_v"]].copy()
            disp.columns=["Location","Segment","Total Items","# Events","Avg/Event","Mean","SD","Max","Min"]
            disp=disp.round(1).reset_index(drop=True); disp.index=range(1,len(disp)+1)
            st.dataframe(disp, use_container_width=True, height=600)
            tbl_note("Mean and SD are computed across individual count records, not event totals.")

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
    st.markdown('<div class="pg-title">Survey Data Entry & Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="pg-lead">Submit new survey entries and manage existing ones. Entries can be deleted by Event ID. All changes are reflected immediately in charts and tables.</div>', unsafe_allow_html=True)

    entry_tab, manage_tab = st.tabs(["Add New Entry", "Manage / Delete Entries"])

    # ── TAB 1: ADD NEW ENTRY ─────────────────────────────────────
    with entry_tab:
        # ── Step state ──────────────────────────────────────────────
        # step 1 = filling form, step 2 = review before submit
        for _k,_v in [("entry_step",1),("entry_snapshot",None)]:
            if _k not in st.session_state: st.session_state[_k]=_v

        # ── STEP 1: FILL OUT THE FORM ────────────────────────────────
        if st.session_state["entry_step"] == 1:
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
                field_notes=st.text_area("Observations, site conditions, notable findings",height=90,
                    placeholder="e.g. Recent flooding, concentrated debris near outfall, unusual items found...")
                st.markdown('</div>', unsafe_allow_html=True)

                total_preview=sum(counts.values())
                st.markdown(f'<div class="live-total"><div class="live-total-n">{total_preview:,}</div><div class="live-total-l">total items counted in this entry</div></div>', unsafe_allow_html=True)
                go_review=st.form_submit_button("Review Before Submitting",use_container_width=True)

            if go_review:
                if not event_id.strip():
                    st.error("Event ID is required.")
                elif not site_final:
                    st.error("Survey location is required.")
                elif total_preview == 0:
                    st.warning("No items were entered. Are you sure you want to submit a zero-count event? If yes, enter at least one count.")
                else:
                    # Save everything to session state and move to review step
                    st.session_state["entry_snapshot"] = {
                        "event_id": event_id.strip(),
                        "survey_date": survey_date,
                        "area_m2": area_m2,
                        "recorder_final": recorder_final,
                        "site_final": site_final,
                        "counts": {k:v for k,v in counts.items() if v>0},
                        "field_notes": field_notes,
                        "total": total_preview,
                    }
                    st.session_state["entry_step"] = 2
                    st.rerun()

        # ── STEP 2: REVIEW PANEL ─────────────────────────────────────
        elif st.session_state["entry_step"] == 2:
            snap = st.session_state["entry_snapshot"]

            st.markdown(
                f'<div style="background:{C["green"]}0d;border:1px solid {C["green"]}33;' +
                f'border-radius:10px;padding:22px 28px;margin-bottom:20px;">' +
                f'<div style="font-family:Cormorant Garamond,serif;font-size:1.3rem;font-weight:700;' +
                f'color:{C["green"]};margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid {C["sand3"]};'+">" +
                "Review Your Entry — Verify Everything Before Submitting" +
                "</div>",
                unsafe_allow_html=True
            )

            # Event info summary
            st.markdown(
                f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;">' +
                f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Event ID</div>' +
                f'<div style="font-size:1.5rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["green"]};">{snap["event_id"]}</div></div>' +
                f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Survey Date</div>' +
                f'<div style="font-size:1rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["text"]};">{snap["survey_date"].strftime("%B %d, %Y")}</div></div>' +
                f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Location</div>' +
                f'<div style="font-size:1rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["text"]};line-height:1.3;">{snap["site_final"]}</div></div>' +
                f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Recorder</div>' +
                f'<div style="font-size:1rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["text"]};">{snap["recorder_final"] or "—"}</div></div>' +
                '</div>',
                unsafe_allow_html=True
            )

            # Plot area + total count
            st.markdown(
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px;">' +
                f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Plot Area</div>' +
                f'<div style="font-size:1.3rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["text"]};">{snap["area_m2"]} m²</div></div>' +
                f'<div style="background:{C["green"]};border-radius:8px;padding:14px 16px;">' +
                f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:rgba(255,255,255,.6);margin-bottom:6px;">Total Items to Be Saved</div>' +
                f'<div style="font-size:2rem;font-family:Cormorant Garamond,serif;font-weight:700;color:white;">{snap["total"]:,}</div></div>' +
                '</div>',
                unsafe_allow_html=True
            )

            # Items recorded — only non-zero
            if snap["counts"]:
                st.markdown(
                    f'<div style="font-size:10px;font-family:DM Mono,monospace;text-transform:uppercase;' +
                    f'letter-spacing:1.5px;color:{C["muted"]};margin-bottom:10px;">Items Recorded (non-zero only)</div>',
                    unsafe_allow_html=True
                )
                # Group by category
                by_group = {}
                for grp_name, items in TRASH_GROUPS.items():
                    grp_counts = {item: snap["counts"][item] for item in items if item in snap["counts"]}
                    if grp_counts: by_group[grp_name] = grp_counts

                for grp_name, grp_counts in by_group.items():
                    grp_total = sum(grp_counts.values())
                    rows_html = "".join(
                        f'<div style="display:flex;justify-content:space-between;padding:5px 0;' +
                        f'border-bottom:1px solid {C["sand3"]};font-size:13px;">' +
                        f'<span style="color:{C["text"]};">{item}</span>' +
                        f'<span style="font-weight:700;color:{C["green"]};font-family:DM Mono,monospace;">{count:,}</span></div>'
                        for item, count in sorted(grp_counts.items(), key=lambda x: -x[1])
                    )
                    st.markdown(
                        f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;' +
                        f'margin-bottom:10px;overflow:hidden;">' +
                        f'<div style="background:{C["sand"]};padding:8px 16px;display:flex;' +
                        f'justify-content:space-between;border-bottom:1px solid {C["sand3"]};">' +
                        f'<span style="font-size:10px;font-family:DM Mono,monospace;text-transform:uppercase;' +
                        f'letter-spacing:1.2px;color:{C["green"]};font-weight:700;">{grp_name}</span>' +
                        f'<span style="font-size:10px;font-family:DM Mono,monospace;color:{C["muted"]};">Total: {grp_total:,}</span></div>' +
                        f'<div style="padding:4px 16px 8px;">{rows_html}</div></div>',
                        unsafe_allow_html=True
                    )

            # Field notes
            if snap.get("field_notes","").strip():
                st.markdown(
                    f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;' +
                    f'padding:14px 16px;margin-bottom:18px;">' +
                    f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;' +
                    f'letter-spacing:1.5px;color:{C["muted"]};margin-bottom:8px;">Field Notes</div>' +
                    f'<div style="font-size:13.5px;color:{C["text"]};line-height:1.7;">{snap["field_notes"]}</div></div>',
                    unsafe_allow_html=True
                )

            st.markdown("</div>", unsafe_allow_html=True)

            # Confirm / Go back buttons
            st.markdown(
                f'<div style="font-size:13.5px;font-weight:600;color:{C["text"]};margin:20px 0 12px;">' +
                "Does everything look correct? Once submitted, this entry is saved to the live database.",
                unsafe_allow_html=True
            )
            col_submit, col_back = st.columns(2)
            with col_submit:
                if st.button("Confirm and Submit to Database", use_container_width=True, key="final_submit"):
                    try:
                        sb=get_sb()
                        sb.table("site_events").upsert({
                            "event_id":int(snap["event_id"]),
                            "date_site":snap["survey_date"].isoformat(),
                            "site_label":snap["site_final"],
                            "location_description":snap["site_final"],
                            "recorder":snap["recorder_final"],
                            "surveyed_m2":float(snap["area_m2"]) if snap["area_m2"] else None
                        }).execute()
                        all_counts=snap["counts"]
                        rows=[{"event_id":int(snap["event_id"]),"trash_group":g,"trash_item":item,"count_value":float(v)}
                              for g,items in TRASH_GROUPS.items() for item in items if (v:=all_counts.get(item,0)) and v>0]
                        if rows: sb.table("trash_counts").insert(rows).execute()
                        load_data.clear()
                        st.session_state["entry_step"]=1
                        st.session_state["entry_snapshot"]=None
                        st.success(
                            f"Saved — Event {snap['event_id']} · {snap['site_final']} · "
                            f"{snap['survey_date'].strftime('%B %d, %Y')} · {snap['total']:,} items"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not save: {e}")
            with col_back:
                if st.button("Go Back and Edit", use_container_width=True, key="back_to_form"):
                    st.session_state["entry_step"]=1
                    st.session_state["entry_snapshot"]=None
                    st.rerun()

    # ── TAB 2: MANAGE / DELETE ───────────────────────────────────
    with manage_tab:
        st.markdown(f"""<div style="background:{C['sand']};border:1px solid {C['sand3']};
        border-left:4px solid {C['brick']};border-radius:0 8px 8px 0;
        padding:14px 18px;margin-bottom:20px;font-size:13.5px;color:{C['text']};line-height:1.7;">
        <strong>About deletion:</strong> Deleting an event removes it from both
        <code>site_events</code> and <code>trash_counts</code> permanently.
        This cannot be undone. Only delete entries that were entered in error.
        If you need to correct a value, delete and re-enter the event with the correct data.
        </div>""", unsafe_allow_html=True)

        # Show existing events table
        section_title("Existing Survey Events")
        st.markdown('<div class="sec-sub">Browse all events currently in the database. Search by Event ID or location name to find what you need.</div>', unsafe_allow_html=True)

        # Build event summary from loaded data
        ev_summary = long.groupby(["event_id","date","site_label"]).agg(
            total_items=("n","sum"),
            categories=("trash_group","nunique")
        ).reset_index()
        ev_summary["date_str"] = ev_summary["date"].dt.strftime("%B %d, %Y").fillna("Unknown date")
        ev_summary = ev_summary.sort_values("date", ascending=False).reset_index(drop=True)

        # Search filter
        search = st.text_input("Search by Event ID or location name", placeholder="e.g. 396 or Cushing")
        if search.strip():
            mask = (ev_summary["event_id"].astype(str).str.contains(search.strip(), case=False) |
                    ev_summary["site_label"].str.contains(search.strip(), case=False, na=False))
            ev_filtered = ev_summary[mask].copy()
        else:
            ev_filtered = ev_summary.copy()

        # Display table
        disp_ev = ev_filtered[["event_id","date_str","site_label","total_items","categories"]].copy()
        disp_ev.columns = ["Event ID","Date","Location","Total Items","Categories Recorded"]
        disp_ev.index = range(1, len(disp_ev)+1)
        st.dataframe(disp_ev, use_container_width=True, height=360)
        tbl_note(f"Showing {len(ev_filtered):,} of {len(ev_summary):,} events. Use the search box above to filter.")

        # Delete section
        section_title("Delete an Entry")
        st.markdown('<div class="sec-sub">Enter the Event ID you want to delete. The event and all its trash count records will be permanently removed.</div>', unsafe_allow_html=True)

        del_col1, del_col2 = st.columns([2,3])
        with del_col1:
            del_id = st.text_input("Event ID to delete", placeholder="e.g. 396", key="del_event_id")

        if del_id.strip():
            # Preview what will be deleted
            try:
                del_int = int(del_id.strip())
                preview = ev_summary[ev_summary["event_id"].astype(str) == del_id.strip()]
                if len(preview) > 0:
                    row = preview.iloc[0]
                    st.markdown(f"""<div style="background:white;border:1px solid {C['sand3']};
                    border-left:4px solid {C['amber']};border-radius:0 8px 8px 0;
                    padding:14px 20px;margin:12px 0;font-size:13.5px;color:{C['text']};line-height:1.8;">
                    <strong>You are about to delete:</strong><br>
                    Event ID: <strong>{row['event_id']}</strong><br>
                    Date: <strong>{row['date_str']}</strong><br>
                    Location: <strong>{row['site_label']}</strong><br>
                    Total items that will be removed: <strong>{int(row['total_items']):,}</strong> across {int(row['categories'])} categories
                    </div>""", unsafe_allow_html=True)

                    # Two-step confirm
                    if "confirm_delete_id" not in st.session_state:
                        st.session_state["confirm_delete_id"] = None

                    if st.session_state["confirm_delete_id"] != del_int:
                        if st.button("Delete this entry", key="del_btn_1"):
                            st.session_state["confirm_delete_id"] = del_int
                            st.rerun()
                    else:
                        st.warning(f"Are you sure you want to permanently delete Event {del_int}? This cannot be undone.")
                        col_yes, col_no = st.columns(2)
                        with col_yes:
                            if st.button("Yes, permanently delete", key="del_confirm_yes"):
                                try:
                                    sb = get_sb()
                                    sb.table("trash_counts").delete().eq("event_id", del_int).execute()
                                    sb.table("site_events").delete().eq("event_id", del_int).execute()
                                    load_data.clear()
                                    st.session_state["confirm_delete_id"] = None
                                    st.success(f"Event {del_int} and all its trash count records have been deleted.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                        with col_no:
                            if st.button("Cancel", key="del_confirm_no"):
                                st.session_state["confirm_delete_id"] = None
                                st.rerun()
                else:
                    st.info(f"Event ID {del_id.strip()} was not found in the database.")
            except ValueError:
                st.error("Event ID must be a number.")

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
