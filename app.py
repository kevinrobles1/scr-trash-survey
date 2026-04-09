# ══════════════════════════════════════════════════════════════════
# Santa Cruz River Trash Survey Dashboard  v5.0
# Sonoran Institute—River Restoration Program
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

def _norm_site_label(s):
    s = "" if s is None else str(s).strip().lower()
    s = s.replace("tuboc", "tubac")
    s = s.replace("st. mary", "st mary").replace("st. mary's", "st mary")
    s = s.replace("santa cruze", "santa cruz")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def assign_segment(site_label, lat=None, lon=None):
    """Assign a river segment from site label first, then coordinates as fallback."""
    s = _norm_site_label(site_label)

    # Rillito / tributary sites
    if any(k in s for k in ["rillito", "arcadia", "country club"]):
        return "Rillito"

    # North reach
    if any(k in s for k in [
        "camino del cerro", "cocerro", "co cerro", "silverbell", "silverlake",
        "north of cocerro", "between an outfall and camino del cerro"
    ]):
        return "North Reach"

    # Central reach
    if any(k in s for k in [
        "cushing", "congress", "trails end", "trail s end", "grant", "granada",
        "carmen", "silverlake bridge", "navajo", "riverview", "verdugo",
        "st mary and riverside", "riverside"
    ]):
        return "Central Reach"

    # South reach
    if any(k in s for k in [
        "speedway", "st mary", "drexel", "irvington", "tubac", "tubac bridge",
        "ina", "west freeway", "freeway", "outfall"
    ]):
        return "South Reach"

    # Coordinate fallback for remaining Santa Cruz corridor sites
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        lat_f = np.nan
        lon_f = np.nan

    if pd.notna(lat_f) and pd.notna(lon_f):
        # Keep only reasonable Southern Arizona coordinates
        if 31.4 <= lat_f <= 32.6 and -111.3 <= lon_f <= -110.7:
            if lat_f >= 32.285:
                return "North Reach"
            elif lat_f >= 32.235:
                return "Central Reach"
            else:
                return "South Reach"

    return "Other"

# Phantom items accidentally migrated as trash—excluded at load time
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
    "Clothing":       ["Clothes, Shoes, Hats","PPE","Misc. Fabric"],
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
# Items that enter waterways during rain events—river health relevance
FLOATABLE_GROUPS   = {"Plastic Bags","Cups","Soda","Water","Sports Drinks","Juice",
    "Food Packaging","Paper Litter"}
NON_FLOATABLE_GROUPS = {"Beer","Liquor","Nicotine","Toiletries","Rx, Drugs","Toys, Games",
    "Clothing","Auto","Construction","Appliances","Misc"}
# Direct public health risk
HEALTH_HAZARD_GROUPS = {"Rx, Drugs","Nicotine","Toiletries"}
# Single-use beverage containers—policy relevance
BEVERAGE_GROUPS    = {"Beer","Liquor","Soda","Water","Sports Drinks","Juice","Cups"}
# Bulk/large debris—removal requires equipment
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

PAGES = ["Overview","Map","Trends","Categories","Locations","Data Table","Data Entry","Export","About"]

# ── TRANSLATIONS ─────────────────────────────────────────────────
# Used for volunteer-facing UI and optionally full-app language toggle

# Temporary helper so translation keys using L(...) do not fail during module load.
# The real L() helper is defined later; here we only need the raw text key.
def L(text, lang=None):
    return text

TR = {
    "en": {
        "lang_label": "Language / Idioma",
        "lang_en": "English",
        "lang_es": "Español",
        # Auth
        "vol_tab": "Volunteer Entry",
        "vol_welcome": "Welcome, Volunteer!",
        "vol_welcome_sub": "You don't need an account to submit trash counts. Fill in your information below and click <strong>Start</strong> to access the data entry form. You will only be able to submit counts—you cannot view, edit, or delete existing data.",
        "vol_lang_prompt": "Which language would you like to use today?",
        "vol_fullname": "Your Full Name *",
        "vol_org": "Organization / Group",
        "vol_contact": "Phone or Email (optional)",
        "vol_exp": "Survey experience level",
        "vol_exp_opts": ["First time today","Participated before (1–3 times)","Regular volunteer (4+ times)"],
        "vol_how": "How did you hear about this opportunity?",
        "vol_notes": "Any other notes about yourself or your group",
        "vol_notes_ph": "e.g. Bringing 5 people, UA Environmental Studies class",
        "vol_disclaimer": "By submitting, you confirm that the data you enter reflects actual field counts from today&#39;s survey. Your name will appear on submitted entries.",
        "vol_start_btn": "Start Volunteer Entry",
        "vol_name_required": "Please enter your full name.",
        # Entry form
        "entry_banner_ey": "Volunteer Survey Entry",
        "entry_banner_title": "Submit Your Trash Counts",
        "entry_banner_sub": "Thank you for volunteering with the Sonoran Institute! Fill in the counts for each item found during your survey plot. Your submission goes directly into the live database.",
        "vol_session_label": "Volunteer session",
        "vol_only_entry": "You can submit survey counts only.",
        "vol_sign_in_link": "Sign in with a staff account",
        "event_info": "Event Information",
        "event_id": "Event ID",
        "survey_date": "Survey Date",
        "plot_area": "Plot Area (m²)",
        "recorder_lbl": "Recorder",
        "recorder_other": "Recorder full name (fill in if not listed above)",
        "recorder_other_ph": "e.g. Maria Garcia",
        "recorder_other_help": "Only needed when 'Other—type below' is selected.",
        "location_existing": "Survey Location (existing)",
        "location_new": "Or enter a new location name",
        "counts_title": "Trash Item Counts",
        "counts_sub": "Enter the count for each item found during the survey. Leave at 0 if not present.",
        "field_notes": "Field Notes (optional)",
        "field_notes_ph": "e.g. Recent flooding, concentrated debris near outfall, unusual items found...",
        "total_label": "total items counted in this entry",
        "review_btn": "Review Before Submitting",
        "event_required": "Event ID is required.",
        "site_required": "Survey location is required.",
        "zero_warning": "No items were entered. Are you sure you want to submit a zero-count event?",
        # Review
        "review_title": "Review Your Entry: Verify Everything Before Submitting",
        "review_event_id": "Event ID",
        "review_date": "Survey Date",
        "review_location": "Location",
        "review_recorder": "Recorder",
        "review_area": "Plot Area",
        "review_total": "Total Items to Be Saved",
        "review_items_label": "Items Recorded (non-zero only)",
        "review_notes_label": "Field Notes",
        "review_confirm_sub": "Does everything look correct? Once submitted, this entry is saved to the live database.",
        "confirm_btn": "Confirm and Submit to Database",
        "back_btn": "Go Back and Edit",
        "saved_msg": "Saved",
        # Classification
        "class_blue": "Recyclable",
        "class_red": "Health Hazard",
        "class_amber": "Floatable",
        "class_green": "Other Non-Recyclable",
        "section_food": "Food & Beverage",
        "section_litter": "Litter & Debris",
        "section_health": "Health Hazards",
        "section_large": "Large & Bulk",
        "section_other": "Other",
        # Filters
        "river_segment":"River Segment",
        "location":"Location",
        "category":"Category",
        "date_range":"Date Range",
        "map_mode_lbl":"Map view",
        "map_mode_seg":"By River Segment",
        "map_mode_burden":"By Trash Burden",
        # About
        "why_river_title":"Why This River and Why This Data",
        "about_db_title":"About This Database",
        "about_why_title":"Why Longitudinal Trash Data Matters",
        "about_team_title":"Program Team",
        "about_p1":"The Santa Cruz River is one of the most ecologically significant waterways in the American Southwest. For more than <strong>12,000 years</strong> it has sustained human communities.",
        "about_p2":"After decades of overextraction and pollution, the river is experiencing a remarkable recovery. Today approximately <strong>35 miles of perennial flow</strong> support the return of native fish including the endangered Gila topminnow.",
        "about_p3":"<strong>Trash is a direct threat to this recovery.</strong> Litter degrades water quality, entangles wildlife, fragments into microplastics, and undermines the investment in restoration.",
        "about_p4":"The Sonoran Institute trash survey program exists to <strong>quantify this threat with scientific precision</strong>—creating the longitudinal data record needed to report to regulatory agencies and secure restoration funding.",
        "about_db_p1":"The trash survey protocol uses <strong>plot-based sampling</strong>: fixed, measured areas surveyed at consistent locations. Each field visit counts and categorizes every piece of litter found using a standardized <strong>56-item, 19-category protocol</strong>.",
        "about_db_p2":"Data collection began in September 2020, creating a <strong>longitudinal record</strong> that captures seasonal patterns, post-monsoon debris, encampment-related waste, and how specific reaches respond to cleanup interventions.",
        "about_db_p3":"This dashboard is the first cloud-hosted, real-time interface for this dataset. Previously, all data lived in a single local Excel workbook. The move to Supabase means the entire team can access, enter, and analyze records from any device.",
        "about_db_p4":"The <strong>19 survey categories</strong> cover the full range of urban litter: food packaging (~33%), clothing (encampment indicator), beverage containers (recyclable fraction), pharmaceutical materials (public health concern), and large debris including appliances and construction waste.",
        "why_title":"Why This Data Matters and What It Can Achieve",
        "why_sub":"The Santa Cruz River runs through the heart of Tucson—one of the few desert rivers in the Southwest with restored perennial flow. Litter that accumulates on its banks washes directly into that flow during monsoon season, carrying plastic, chemicals, and debris into a recovering ecosystem.",
        "impact_reg_title":"Regulatory Compliance",
        "impact_reg":"ADEQ stormwater permits and EPA Section 319 require proof that litter is being actively managed. This dataset provides that with standardized methods, consistent locations, and four years of records.",
        "impact_grant_title":"Grant Funding",
        "impact_grant":"This database shows which river reaches carry the most trash, which categories dominate, and whether prior cleanups made a difference—the exact framing funders need.",
        "impact_health_title":"Public Health",
        "impact_health":"Syringes found during surveys are a safety risk for everyone who walks the river corridor. Documented counts support requests for social service intervention and field crew safety protocols.",
        "impact_cleanup_title":"Targeted Cleanup",
        "impact_cleanup":"Some sites are consistently heavily littered. Others spike after storms or encampments. Longitudinal data is the only way to tell them apart and allocate cleanup resources effectively.",
        "impact_policy_title":"Policy & Advocacy",
        "impact_policy":"About 63% of items float, meaning monsoon storms carry them into the river. About 16% are recyclable under Tucson standards but end up as litter—concrete numbers for bottle deposit and stormwater policy arguments.",
        "impact_refuge_title":"Urban Wildlife Refuge",
        "impact_refuge":"Sonoran Institute and The Wilderness Society are working to establish a Santa Cruz River Urban National Wildlife Refuge. A four-year litter monitoring record supports that case with the U.S. Fish and Wildlife Service.",
        "col_category":"Category","col_total":"Total Items","col_records":"# Records",
        "col_avg":"Avg per Record","col_pct":"% of Total","col_location":"Location",
        "col_segment":"Segment","col_events":"# Events","col_avg_event":"Avg Items/Event",
        "col_event_id":"Event ID","col_date":"Date","col_item":"Item","col_count":"Count",
        "col_area":"Area (m\u00b2)","col_recorder":"Recorder",
        "sec_cat_summary":"Category Summary Table",
        "sec_cat_summary_sub":"Total items, records, and average count per record for each trash category.",
        "sec_raw":"Survey Records",
        "sec_filt_cat":"Filtered Summary \u2014 Category Breakdown",
        "sec_filt_loc":"Filtered Summary \u2014 Location Breakdown",
        "last_updated":"Data current as of",
        "dashboard_refreshed":"Dashboard refreshed",
        "data_current":"Data current as of",
        "items":"items",
        # About—hero
        "about_hero_eyebrow":"Sonoran Institute · Tucson, Arizona",
        "about_hero_title":"Santa Cruz River Trash Survey Program",
        "about_hero_sub":"A longitudinal monitoring program tracking litter and debris along the Santa Cruz River corridor in Tucson, Arizona—building the scientific record needed to protect a living desert river.",
        "about_scroll":"Scroll right to see more \u2192",
        "about_photo_caption":"Santa Cruz River corridor, Tucson, AZ \u00b7 \u00a9Bill Hatcher / Sonoran Institute",
        "about_field_caption":"Field survey crew, Santa Cruz River corridor, 2019",
        "stat_items_lbl":"Items Recorded","stat_items_note":"across all survey events",
        "stat_events_lbl":"Plot Records","stat_events_note":"individual surveyed plots",
        "stat_locs_lbl":"Unique Locations","stat_locs_note":"along the corridor",
        "stat_period_lbl":"Survey Period","stat_period_note":"longitudinal record",
        "reason_reg_title":"Regulatory Reporting",
        "reason_reg":"ADEQ stormwater permit compliance and EPA Section 319 reporting require documented evidence of litter management. This database provides that with verifiable methodology and multi-year records.",
        "reason_grant_title":"Grant Funding",
        "reason_grant":"Federal and foundation grants require baseline data and demonstrated monitoring capacity. This dataset shows where the problem is worst and whether interventions produce measurable change.",
        "reason_cleanup_title":"Targeted Cleanup Design",
        "reason_cleanup":"Not all sites are equal. The data identifies chronic hotspots versus episodic dumping sites that require completely different responses.",
        "reason_health_title":"Public Health Documentation",
        "reason_health":"Syringe and drug paraphernalia counts create a documented health hazard record, supporting requests for targeted interventions and field crew safety resources.",
        "reason_policy_title":"Policy Advocacy",
        "reason_policy":"The recyclable fraction (~16%) and floatable fraction (~63%) are direct arguments for bottle bills, extended producer responsibility legislation, and stormwater ordinances.",
        "reason_refuge_title":"Urban Wildlife Refuge Designation",
        "reason_refuge":"Demonstrating active protection—not just restoration—is essential to securing the Urban National Wildlife Refuge designation Sonoran Institute is pursuing with USFWS.",
        "about_quote":"The Santa Cruz River has provided life-sustaining water to humans for more than 12,000 years—and can flow again with your support.",
        "about_quote_attr":"\u2014 Sonoran Institute",
        "team_role_luke":"Program Director",
        "team_desc_luke":"Luke directs the Santa Cruz River Restoration Program, Sonoran Institute",
        "team_role_kevin":"Database Specialist \u00b7 RISE Intern",
        "team_desc_kevin":"Dashboard development, data migration, and analysis infrastructure",
        "team_name_field":"Field Survey Team",
        "team_role_field":"Data Collectors",
        "team_desc_field":"Sofia Angkasa, Kimberly Stanley, Marie Olson, and all survey crew members who built this record over four years",
        "ftr_connect":"Connect with us",
        "ftr_our_work":"Our Work","ftr_about_us":"About Us","ftr_updates":"Sonoran Updates",
        "ftr_resources":"Resources","ftr_support":"Support Us","ftr_reports":"Living River Reports 2025",
        "ftr_newsletter":"Sign Up for Newsletter","ftr_sustainer":"Become a Sonoran Sustainer",
        "ftr_blog":"Blog Posts","ftr_events":"Events","ftr_mission":"Our Mission & Vision",
        "ftr_people":"Our People","ftr_careers":"Careers","ftr_contact":"Contact Us",
        "ftr_phone":"Phone",
        "ftr_copyright":"\u00a9 Sonoran Institute \u00b7 Santa Cruz River Trash Survey Dashboard v5.1",
        "acct_signed_in":"Signed in as","acct_username":"Username","acct_role":"Role",
        "acct_refresh":"Refresh Data","acct_signout":"Sign Out",
        "acct_signout_note":"Sign out button also available top-right",
        "acct_session":"Account & Session",
        "items_in_view":"Items in View",
        "of_all_data":"Of All Data",
        # KPI strip
        "kpi_items":"Total Items Recorded","kpi_items_note":"across all survey events",
        "kpi_events":"Plot Records","kpi_events_note":"individual surveyed plots",
        "kpi_locs":"Unique Locations","kpi_locs_note":"registered site names",
        "kpi_cats":"Trash Categories","kpi_cats_note":"of 19 groups · 56 items",
        "kpi_period":"Survey Period","kpi_period_note":"date range",
        # Page banners—all pages
        "loc_ey":"Site Analysis",
        "loc_title":"Where the Trash Is and How Much",
        "loc_sub":"Trash burden across the 136 recorded survey locations, ordered North to South.",
        "de_ey":"Field Data Entry",
        "de_title":"Survey Data Entry & Management",
        "de_sub":"Submit new survey entries and manage existing records. All changes save directly to the live database.",
        "ex_ey":"Data Export",
        "ex_title":"Download the Database",
        "ex_sub":"Clean, formatted CSVs ready for Excel, R, Python, or ArcGIS.",
        "dt_ey":"Complete Database",
        "dt_title":"Explore the Full Survey Record",
        "dt_sub":"Every recorded count from every survey event. Filter by segment, location, category, or date.",
        "cat_ey":"Item & Category Analysis",
        "cat_title":"What Kind of Trash We Find",
        "cat_sub":"Deep dive into the 19 category groups and 56 individual item types recorded across all surveys.",
        "ov_ey":"Sonoran Institute · Tucson, Arizona",
        "ov_title":"Santa Cruz River Trash Survey",
        "ov_sub":"Longitudinal survey data collected along the Santa Cruz River corridor, Tucson, AZ. Plot-based surveys across multiple sites and reaches—program led by Luke Cole, Sonoran Institute.",
        "map_ey":"Survey Site Map",
        "map_title":"Where We Survey",
        "map_sub":"GPS locations of all recorded survey sites along the Santa Cruz River corridor and its tributaries.",
        "tr_ey":"Temporal Analysis",
        "tr_title":"How Trash Levels Change Over Time",
        "tr_sub":"Monthly, annual, and seasonal patterns across the full survey record.",
        "filter_data":"Filter Data","cat_summary":"Category Summary Table","cat_summary_sub":"Total items per category.",


    },
    "es": {
        "lang_label": "Idioma / Language",
        "lang_en": "English",
        "lang_es": "Español",
        # Auth
        "vol_tab": "Entrada de Voluntario",
        "vol_welcome": "¡Bienvenido/a, Voluntario/a!",
        "vol_welcome_sub": "No necesitas una cuenta para registrar conteos de basura. Llena tu información a continuación y haz clic en <strong>Comenzar</strong> para acceder al formulario de entrada.",
        "vol_lang_prompt": "¿En qué idioma deseas usar el sistema hoy?",
        "vol_fullname": "Tu nombre completo *",
        "vol_org": "Organización / Grupo",
        "vol_contact": "Teléfono o correo electrónico (opcional)",
        "vol_exp": "Nivel de experiencia en encuestas",
        "vol_exp_opts": ["Primera vez hoy","He participado antes (1–3 veces)","Voluntario/a regular (4+ veces)"],
        "vol_how": "¿Cómo te enteraste de esta oportunidad?",
        "vol_notes": "Otras notas sobre ti o tu grupo",
        "vol_notes_ph": "p.ej. Traigo 5 personas, clase de Estudios Ambientales de la UA",
        "vol_disclaimer": "Al enviar, confirmas que los datos ingresados reflejan los conteos reales del levantamiento de hoy. Tu nombre aparecerá en las entradas enviadas.",
        "vol_start_btn": "Comenzar Entrada de Voluntario",
        "vol_name_required": "Por favor ingresa tu nombre completo.",
        # Entry form
        "entry_banner_ey": "Entrada de Voluntario",
        "entry_banner_title": "Registra tus Conteos de Basura",
        "entry_banner_sub": "¡Gracias por ser voluntario/a con el Sonoran Institute! Ingresa los conteos de cada artículo encontrado durante tu parcela de levantamiento. Tu envío se guarda directamente en la base de datos en vivo.",
        "vol_session_label": "Sesión de voluntario",
        "vol_only_entry": "Solo puedes enviar conteos de levantamiento.",
        "vol_sign_in_link": "Iniciar sesión con cuenta de personal",
        "event_info": "Información del Evento",
        "event_id": "ID del Evento",
        "survey_date": "Fecha del Levantamiento",
        "plot_area": "Área de la Parcela (m²)",
        "recorder_lbl": "Registrador/a",
        "recorder_other": "Nombre completo del registrador (si no está en la lista)",
        "recorder_other_ph": "p.ej. María García",
        "recorder_other_help": "Solo necesario si seleccionaste 'Otro—escribir abajo'.",
        "location_existing": "Ubicación del Levantamiento (existente)",
        "location_new": "O ingresa un nuevo nombre de ubicación",
        "counts_title": "Conteo de Artículos de Basura",
        "counts_sub": "Ingresa el número de cada artículo encontrado durante el levantamiento. Deja en 0 si no estaba presente.",
        "field_notes": "Notas de Campo (opcional)",
        "field_notes_ph": "p.ej. Inundación reciente, desechos concentrados cerca de la descarga, artículos inusuales encontrados...",
        "total_label": "artículos contados en esta entrada",
        "review_btn": "Revisar Antes de Enviar",
        "event_required": "Se requiere el ID del evento.",
        "site_required": "Se requiere la ubicación del levantamiento.",
        "zero_warning": "No se ingresaron artículos. ¿Estás seguro/a de que deseas enviar un evento con conteo cero?",
        # Review
        "review_title": "Revisa Tu Entrada—Verifica Todo Antes de Enviar",
        "review_event_id": "ID del Evento",
        "review_date": "Fecha del Levantamiento",
        "review_location": "Ubicación",
        "review_recorder": "Registrador/a",
        "review_area": "Área de Parcela",
        "review_total": "Total de Artículos a Guardar",
        "review_items_label": "Artículos Registrados (solo los no cero)",
        "review_notes_label": "Notas de Campo",
        "review_confirm_sub": "¿Todo se ve correcto? Una vez enviado, esta entrada se guarda en la base de datos en vivo.",
        "confirm_btn": "Confirmar y Enviar a la Base de Datos",
        "back_btn": "Regresar y Editar",
        "saved_msg": "Guardado",
        # Classification
        "class_blue": "Reciclable",
        "class_red": "Riesgo para la Salud",
        "class_amber": "Flotante",
        "class_green": "Otro No Reciclable",
        "section_food": "Alimentos y Bebidas",
        "section_litter": "Basura y Desechos",
        "section_health": "Riesgos para la Salud",
        "section_large": "Desechos Grandes y Voluminosos",
        "section_other": "Otros",
        # Filters
        "river_segment":"Segmento del Río",
        "location":"Ubicación",
        "category":"Categoría",
        "date_range":"Rango de Fechas",
        "map_mode_lbl":"Vista del Mapa",
        "map_mode_seg":"Por Segmento del Río",
        "map_mode_burden":"Por Carga de Basura",
        # About page text
        "why_river_title":"Por Qué Este Río—y Por Qué Estos Datos",
        "about_db_title":"Acerca de Esta Base de Datos",
        "about_why_title":"Por Qué Importan los Datos Longitudinales de Basura",
        "about_team_title":"Equipo del Programa",
        "about_p1":"El Río Santa Cruz es una de las vías fluviales más ecológicamente significativas del suroeste americano. Por más de <strong>12,000 años</strong> ha sostenido comunidades humanas—desde la Nación Tohono O'odham, que ha administrado estas tierras desde tiempos inmemoriales, hasta el millón de residentes de Tucson hoy.",
        "about_p2":"Después de décadas de sobreexplotación y contaminación, el río está experimentando una recuperación notable. Hoy, aproximadamente <strong>35 millas de flujo perenne</strong> sostienen el regreso de peces nativos incluyendo el amenazado Gila topminnow, bosques de álamo-sauce, aves migratorias y reptiles. El Proyecto Heritage de 2019 creó un tramo fluvial a través del centro de Tucson por primera vez en una generación.",
        "about_p3":"<strong>La basura es una amenaza directa para esta recuperación.</strong> Los desechos degradan la calidad del agua, enredan la fauna silvestre, se fragmentan en microplásticos y socavan la inversión en restauración. Durante los eventos de monzón, los artículos flotantes viajan aguas abajo hacia el propio río.",
        "about_p4":"El programa de encuestas de basura del Sonoran Institute existe para <strong>cuantificar esta amenaza con precisión científica</strong>—creando el registro de datos longitudinales necesario para reportar a agencias reguladoras, asegurar fondos de restauración, diseñar programas de limpieza dirigidos y demostrar progreso medible con el tiempo.",
        "about_db_p1":"El protocolo de encuesta de basura utiliza <strong>muestreo basado en parcelas</strong>: áreas medidas y fijas encuestadas en ubicaciones consistentes. Cada visita de campo cuenta y categoriza cada pieza de basura encontrada usando un protocolo estandarizado de <strong>56 artículos y 19 categorías</strong>.",
        "about_db_p2":"La recolección de datos comenzó en septiembre de 2020, creando un <strong>registro longitudinal</strong> que captura patrones estacionales, desechos post-monzón, basura relacionada con campamentos y cómo los tramos específicos responden a las intervenciones de limpieza.",
        "about_db_p3":"Este panel es la primera interfaz en tiempo real alojada en la nube para este conjunto de datos. Anteriormente, todos los datos vivían en un único libro de Excel local. El traslado a Supabase significa que todo el equipo del Sonoran Institute puede ahora acceder, ingresar y analizar registros desde cualquier dispositivo.",
        "about_db_p4":"Las <strong>19 categorías de encuesta</strong> cubren la gama completa de basura urbana: empaques de alimentos (aproximadamente un tercio de todos los artículos), ropa y tela (un indicador de campamentos), envases de bebidas (la fracción reciclable que termina como basura), materiales farmacéuticos y de drogas (una preocupación directa de salud pública), y desechos grandes como electrodomésticos y materiales de construcción.",
        # Overview impact panel
        "why_title":"Por Qué Importan Estos Datos—y Qué Pueden Lograr",
        "why_sub":"El Río Santa Cruz es una de las vías fluviales más significativas y amenazadas del suroeste americano. Lo que sucede con la basura en sus orillas determina lo que sucede con su agua, su fauna y las comunidades que dependen de él.",
        "impact_reg_title":"Cumplimiento Regulatorio",
        "impact_reg":"Los permisos de aguas pluviales de ADEQ y la Sección 319 de la EPA requieren pruebas documentadas de gestión activa de basura. Esta base de datos es esa evidencia, con metodología estandarizada y registros de múltiples años que satisfacen los requisitos de las agencias.",
        "impact_grant_title":"Financiamiento de Subvenciones",
        "impact_grant":"Los fondos federales y de fundaciones para la restauración de ríos requieren datos de referencia y capacidad de monitoreo demostrada. Esta base de datos establece ambos, mostrando qué tramos están más afectados y si las intervenciones están reduciendo los conteos con el tiempo.",
        "impact_health_title":"Salud Pública",
        "impact_health":"Las jeringas encontradas durante las encuestas son un riesgo de pinchazo para toda persona que camine por el corredor fluvial. Tener un conteo documentado apoya las solicitudes de intervención de servicios sociales, informa los protocolos del equipo de campo y da a las agencias de salud pública los números que necesitan.",
        "impact_cleanup_title":"Limpieza Dirigida",
        "impact_cleanup":"Algunos sitios están consistentemente llenos de basura. Otros aumentan después de tormentas o eventos de campamentos. Estas dos situaciones requieren respuestas completamente diferentes. Los datos longitudinales son la única manera de distinguirlas.",
        "impact_policy_title":"Política y Defensa",
        "impact_policy":"Aproximadamente el 63% de los artículos registrados flotan, lo que significa que una tormenta de monzón los lleva directamente al río. Aproximadamente el 16% son reciclables bajo los estándares de la ciudad de Tucson pero terminan como basura. Ambas cifras son argumentos cuantificables para leyes de depósito de botellas y ordenanzas de aguas pluviales.",
        "impact_refuge_title":"Refugio de Vida Silvestre Urbana",
        "impact_refuge":"El Sonoran Institute y The Wilderness Society están trabajando para establecer un Refugio Nacional de Vida Silvestre Urbana en el Río Santa Cruz. El Servicio de Pesca y Vida Silvestre de EE.UU. necesita ver que el río está siendo protegido activamente. Un registro de monitoreo de basura de cuatro años apoya ese caso.",
        # Table column labels
        "col_category":"Categoría","col_total":"Total de Artículos","col_records":"# Registros",
        "col_avg":"Promedio por Registro","col_pct":"% del Total","col_location":"Ubicación",
        "col_segment":"Segmento","col_events":"# Eventos","col_avg_event":"Artículos Prom/Evento",
        "col_event_id":"ID Evento","col_date":"Fecha","col_item":"Artículo","col_count":"Conteo",
        "col_area":"Área (m²)","col_recorder":"Registrador",
        # Section titles
        "sec_cat_summary":"Tabla Resumen por Categoría",
        "sec_cat_summary_sub":"Total de artículos, número de registros individuales y promedio por registro para cada categoría de basura.",
        "sec_raw":"Registros de Encuesta",
        "sec_filt_cat":"Resumen Filtrado—Desglose por Categoría",
        "sec_filt_loc":"Resumen Filtrado—Desglose por Ubicación",
        "last_updated":"Datos actualizados hasta",
        "dashboard_refreshed":"Panel actualizado el",
        "data_current":"Datos vigentes a",
        "items":"artículos",
        # About—hero
        "about_hero_eyebrow":"Sonoran Institute · Tucson, Arizona",
        "about_hero_title":"Programa de Monitoreo de Basura del Río Santa Cruz",
        "about_hero_sub":"Un programa de monitoreo longitudinal que rastrea basura y desechos a lo largo del corredor del Río Santa Cruz en Tucson, Arizona—construyendo el registro científico necesario para proteger un río vivo del desierto.",
        "about_scroll":"Desliza para ver más fotos →",
        "about_photo_caption":"Corredor del Río Santa Cruz, Tucson, AZ · ©Bill Hatcher / Sonoran Institute",
        "about_field_caption":"Equipo de encuesta de campo, corredor del Río Santa Cruz, 2019",
        # About—db stats
        "stat_items_lbl":"Artículos Registrados","stat_items_note":"en todos los eventos de encuesta",
        "stat_events_lbl":"Registros de Parcela","stat_events_note":"parcelas muestreadas individuales",
        "stat_locs_lbl":"Ubicaciones Únicas","stat_locs_note":"a lo largo del corredor",
        "stat_period_lbl":"Período de Encuesta","stat_period_note":"registro longitudinal",
        # About—why data matters
        "reason_reg_title":"Informes Regulatorios",
        "reason_reg":"El cumplimiento del permiso de aguas pluviales de ADEQ y los informes de la Sección 319 de la EPA requieren evidencia documentada de la gestión de basura. Esta base de datos la proporciona con metodología verificable y registros de múltiples años.",
        "reason_grant_title":"Financiamiento de Subvenciones",
        "reason_grant":"Las subvenciones federales y de fundaciones para la restauración de ríos requieren datos de referencia y capacidad de monitoreo demostrada. Este conjunto de datos establece ambos—mostrando dónde el problema es mayor y si las intervenciones producen cambios medibles.",
        "reason_cleanup_title":"Diseño de Limpieza Dirigida",
        "reason_cleanup":"No todos los sitios son iguales. Los datos identifican puntos críticos crónicos frente a sitios de vertido episódico—que requieren respuestas diferentes que no se pueden diseñar sin datos longitudinales sistemáticos.",
        "reason_health_title":"Documentación de Salud Pública",
        "reason_health":"Los conteos de jeringas y parafernalia de drogas crean un registro documentado de riesgos para la salud pública, apoyando solicitudes de intervenciones dirigidas y recursos de seguridad para el equipo de campo.",
        "reason_policy_title":"Defensa de Políticas",
        "reason_policy":"La fracción reciclable (~16%) y la fracción flotante (~63%) son directamente relevantes para las conversaciones sobre responsabilidad extendida del productor, leyes de depósito de botellas y ordenanzas de aguas pluviales.",
        "reason_refuge_title":"Designación de Refugio de Vida Silvestre Urbana",
        "reason_refuge":"Demostrar protección activa—no solo restauración—es esencial para asegurar la designación de Refugio Nacional de Vida Silvestre Urbana que el Sonoran Institute persigue con The Wilderness Society y el USFWS.",
        # About—quote
        "about_quote":"El Río Santa Cruz ha proporcionado agua vital para los humanos durante más de 12,000 años—y puede fluir de nuevo con tu apoyo.",
        "about_quote_attr":"— Sonoran Institute",
        # About—team
        "team_role_luke":"Director del Programa",
        "team_desc_luke":"Programa de Restauración del Río Santa Cruz, Sonoran Institute",
        "team_role_kevin":"Especialista en Bases de Datos · Becario RISE",
        "team_desc_kevin":"Desarrollo del panel, migración de datos e infraestructura de análisis",
        "team_name_field":"Equipo de Encuesta de Campo",
        "team_role_field":"Recopiladores de Datos",
        "team_desc_field":"Sofia Angkasa, Kimberly Stanley, Marie Olson, y todos los miembros del equipo de encuesta que construyeron este registro durante cuatro años",
        # Footer
        "ftr_connect":"Conéctate con nosotros",
        "ftr_our_work":"Nuestro Trabajo",
        "ftr_about_us":"Sobre Nosotros",
        "ftr_updates":"Actualizaciones de Sonoran",
        "ftr_resources":"Recursos",
        "ftr_support":"Apóyanos",
        "ftr_reports":"Informes Río Vivo 2025",
        "ftr_newsletter":"Suscríbete al Boletín",
        "ftr_sustainer":"Conviértete en Sustentador de Sonoran",
        "ftr_blog":"Publicaciones del Blog",
        "ftr_events":"Eventos",
        "ftr_mission":"Nuestra Misión y Visión",
        "ftr_people":"Nuestra Gente",
        "ftr_careers":"Carreras",
        "ftr_contact":"Contáctanos",
        "ftr_phone":"Teléfono",
        "ftr_copyright":"© Sonoran Institute · Panel de Monitoreo de Basura del Río Santa Cruz v5.0",
        # Account
        "acct_signed_in":"Sesión iniciada como",
        "acct_username":"Usuario",
        "acct_role":"Rol",
        "acct_refresh":"Actualizar Datos",
        "acct_signout":"Cerrar Sesión",
        "acct_signout_note":"Botón de cerrar sesión también disponible arriba a la derecha",
        "acct_session":"Cuenta y Sesión",

        # ── ALL PAGES ──
        "pages": ["Acerca De","Resumen","Mapa","Tendencias","Categorías","Ubicaciones","Tabla de Datos","Entrada de Datos","Exportar"],
        # Nav
        "About":"Acerca De","Overview":"Resumen","Map":"Mapa","Trends":"Tendencias",
        "Categories":"Categorías","Locations":"Ubicaciones","Data Table":"Tabla de Datos",
        "Data Entry":"Entrada de Datos","Export":"Exportar",
        # About
        "about_ey":"Sonoran Institute · Tucson, Arizona",
        "about_title":"Programa de Monitoreo de Basura del Río Santa Cruz",
        "about_sub":"Un programa de monitoreo longitudinal que rastrea basura y desechos a lo largo del corredor del Río Santa Cruz en Tucson, Arizona—construyendo el registro científico necesario para proteger un río vivo del desierto.",
        "about_sec1":"Por Qué Este Río—y Por Qué Estos Datos",
        "about_sec2":"Acerca de Esta Base de Datos",
        "about_sec3":"Por Qué Importan los Datos Longitudinales de Basura",
        "about_sec4":"Equipo del Programa",
        "about_p1":"El Río Santa Cruz es una de las vías fluviales más ecológicamente significativas del suroeste americano. Por más de <strong>12,000 años</strong> ha sostenido comunidades humanas—desde la Nación Tohono O'odham, que ha administrado estas tierras desde tiempos inmemoriales, hasta el millón de residentes de Tucson hoy.",
        "about_p2":"Después de décadas de sobreexplotación y contaminación, el río está experimentando una recuperación notable. Hoy, aproximadamente <strong>35 millas de flujo perenne</strong> sostienen el regreso de peces nativos incluyendo el amenazado Gila topminnow, bosques de álamo-sauce, aves migratorias y reptiles.",
        "about_p3":"<strong>La basura es una amenaza directa para esta recuperación.</strong> Los desechos degradan la calidad del agua, enredan la fauna silvestre, se fragmentan en microplásticos y socavan la inversión en restauración.",
        "about_p4":"El programa de encuestas de basura del Sonoran Institute existe para <strong>cuantificar esta amenaza con precisión científica</strong>—creando el registro de datos longitudinales necesario para reportar a agencias reguladoras, asegurar fondos de restauración y diseñar programas de limpieza dirigidos.",
        # Overview
        "ov_ey":"Sonoran Institute · Tucson, Arizona",
        "ov_title":"Monitoreo de Basura del Río Santa Cruz",
        "ov_sub":"Datos de encuestas longitudinales recolectados a lo largo del corredor del Río Santa Cruz, Tucson, AZ. Encuestas basadas en parcelas en múltiples sitios y tramos—programa dirigido por Luke Cole, Sonoran Institute.",
        "ov_filter":"Filtrar Datos",
        "kpi_items":"Total de Artículos Registrados",
        "kpi_items_note":"en todos los eventos de encuesta",
        "kpi_events":"Registros de Parcela",
        "kpi_events_note":"parcelas muestreadas individuales",
        "kpi_locs":"Ubicaciones Únicas",
        "kpi_locs_note":"nombres de sitio registrados",
        "kpi_cats":"Categorías de Basura",
        "kpi_cats_note":"de 19 grupos · 56 artículos",
        "kpi_period":"Período de Encuesta",
        "kpi_period_note":"rango de fechas",
        "chart_monthly":"Artículos Mensuales Registrados a lo Largo del Tiempo",
        "chart_monthly_sub":"Barras verdes = encuesta realizada · Gris = sin encuesta ese mes (la basura aún presente) · Línea dorada discontinua = promedio móvil de 3 meses",
        "chart_pie":"Distribución por Categoría de Basura",
        "chart_pie_sub":"Desglose proporcional de todos los artículos registrados en cada categoría.",
        "chart_top15":"Top 15 Artículos por Conteo Total",
        "chart_top15_sub":"Clasificados por conteo acumulado en todos los eventos y ubicaciones.",
        "chart_seg":"Artículos por Segmento del Río y Categoría",
        "chart_seg_sub":"Gráfico de barras apiladas que muestra la contribución de cada categoría dentro de cada segmento del río.",
        "cat_summary":"Tabla Resumen por Categoría",
        "cat_summary_sub":"Total de artículos, número de registros individuales y conteo promedio por registro para cada categoría de basura.",
        "why_title":"Por Qué Importan Estos Datos—y Qué Pueden Lograr",
        "why_sub":"El Río Santa Cruz es una de las vías fluviales más significativas y amenazadas del suroeste americano. Lo que sucede con la basura en sus orillas determina lo que sucede con su agua, su fauna y las comunidades que dependen de él.",
        # Map
        "map_ey":"Mapa de Sitios de Encuesta",
        "map_title":"Dónde Realizamos Encuestas",
        "map_sub":"Ubicaciones GPS de todos los sitios de encuesta registrados a lo largo del corredor del Río Santa Cruz y sus afluentes.",
        "map_mode_lbl":"Vista del Mapa","map_mode_seg":"Por Segmento del Río",
        "map_mode_burden":"Por Carga de Basura",
        "map_mode_events":"Eventos Individuales",
        # Trends
        "tr_ey":"Análisis Temporal",
        "tr_title":"Cómo Cambian los Niveles de Basura a lo Largo del Tiempo",
        "tr_sub":"Patrones mensuales, anuales y estacionales a lo largo del registro completo de encuestas.",
        # Categories
        "cat_ey":"Análisis de Artículos y Categorías",
        "cat_title":"Qué Tipo de Basura Encontramos",
        "cat_sub":"Análisis profundo de los 19 grupos de categorías y 56 tipos de artículos individuales registrados.",
        "cat_toggle":"Activar/Desactivar Categorías (incluir/excluir de todas las figuras)",
        "cat_select":"Selecciona una figura para mostrar",
        # Locations
        "loc_ey":"Análisis por Sitio",
        "loc_title":"Dónde Está la Basura—y Cuánta",
        "loc_sub":"Carga de basura en las 136 ubicaciones de encuesta registradas. Los sitios están ordenados de Norte a Sur.",
        # Data Table
        "dt_ey":"Base de Datos Completa",
        "dt_title":"Explorar el Registro Completo de Encuestas",
        "dt_sub":"Cada conteo registrado de cada evento de encuesta. Filtra por segmento, ubicación, categoría o fecha.",
        "dt_wide":"Formato Amplio—una fila por evento, cada artículo como columna (como Excel)",
        "dt_long":"Formato Largo—una fila por artículo por evento",
        # Data Entry
        "de_ey":"Entrada de Datos de Campo",
        "de_title":"Entrada y Gestión de Datos de Encuesta",
        "de_sub":"Envía nuevas entradas de encuesta y gestiona registros existentes. Todos los cambios se guardan directamente en la base de datos en vivo.",
        "de_tab1":"Agregar Nueva Entrada",
        "de_tab2":"Gestionar / Eliminar Entradas",
        # Export
        "ex_ey":"Exportación de Datos",
        "ex_title":"Descargar la Base de Datos",
        "ex_sub":"CSVs limpios y formateados listos para Excel, R, Python o ArcGIS.",
        # Common UI
        "filter_data":"Filtrar Datos",
        "river_segment":"Segmento del Río",
        "location":"Ubicación",
        "category":"Categoría",
        "date_range":"Rango de Fechas",
        "items_in_view":"Artículos en Vista",
        "events":"Eventos",
        "locations":"Ubicaciones",
        "of_all_data":"De Todos los Datos",
        "sign_out":"Cerrar Sesión",
        "refresh_data":"Actualizar Datos",
        "live_db":"Base de Datos en Vivo",
        "summer_note":"<strong>Sobre las brechas en el registro mensual:</strong> Las barras grises o los meses faltantes—especialmente junio, julio y agosto—<strong>no significan que no había basura</strong> en el río. Significan que no se realizó ninguna encuesta ese mes. La cobertura de encuestas generalmente disminuye en verano debido a la reducida disponibilidad de voluntarios estudiantiles, el calor extremo y la menor capacidad del programa.",
    }
}

def T(key, lang=None):
    """Get translation for key in current language."""
    if lang is None:
        lang = st.session_state.get("lang","en")
    return TR.get(lang,TR["en"]).get(key, TR["en"].get(key,key))

TEXT_ES = {
    "Strict triplicate sessions only": "Solo sesiones triplicadas estrictas",
    "All recorded plots": "Todas las parcelas registradas",
    "Analysis scope": "Alcance del análisis",
    "Current view": "Vista actual",
    "What this means": "Qué significa esto",
    "Why this matters": "Por qué importa",
    "What is included right now": "Qué está incluido ahora",
    "What is left out right now": "Qué queda fuera ahora",
    "Best use of this view": "Cuándo conviene usar esta vista",
    "Why some charts may still look similar": "Por qué algunas gráficas todavía pueden verse parecidas",
    "Monthly Items Recorded Over Time": "Artículos registrados por mes a lo largo del tiempo",
    "Green bars = survey conducted · Gray = no survey that month (trash still present—see note below) · Gold dashed line = 3-month rolling average": "Barras verdes = sí hubo muestreo · barras grises = no hubo muestreo ese mes (la basura puede seguir presente) · línea dorada punteada = promedio móvil de 3 meses",
    "Share by Trash Category": "Proporción por categoría de basura",
    "Proportional breakdown of all items recorded across every category. Food Packaging, Clothing, and Misc typically dominate.": "Desglose proporcional de todos los artículos registrados en cada categoría. Empaques de comida, ropa y misceláneos suelen dominar.",
    "Top 15 Recorded Items": "Top 15 artículos registrados",
    "Most common items in the current view, ranked by total count across all kept records.": "Artículos más comunes en la vista actual, ordenados por conteo total en todos los registros conservados.",
    "Trash by River Segment": "Basura por tramo del río",
    "Each bar shows how total items are distributed across trash categories within each mapped river segment in the current view.": "Cada barra muestra cómo se distribuyen los artículos totales entre categorías de basura dentro de cada tramo del río en la vista actual.",
    "Average Items per Plot: North to South": "Promedio de artículos por parcela, de norte a sur",
    "Each bar = one survey site. Height = mean items per event at that site. Sites are ordered geographically from northernmost (top) to southernmost (bottom). Color indicates river segment.": "Cada barra representa un sitio de muestreo. La altura muestra el promedio de artículos por evento en ese sitio. Los sitios están ordenados geográficamente de norte a sur. El color indica el tramo del río.",
    "Standard Deviation: North to South": "Desviación estándar, de norte a sur",
    "SD measures how much exact triplicate sessions vary at each site. A site with SD=0 had the same triplicate session mean every time. High SD = unpredictable or patchy litter.": "La DE muestra cuánto cambian las sesiones triplicadas exactas en cada sitio. Un sitio con DE=0 tuvo el mismo promedio en cada sesión triplicada. Una DE alta indica basura más variable o irregular.",
    "Coefficient of Variation: North to South": "Coeficiente de variación, de norte a sur",
    "CV = SD ÷ Mean × 100. It normalizes variability so sites with different mean burden can be fairly compared.": "CV = DE ÷ media × 100. Normaliza la variabilidad para poder comparar de forma más justa sitios con distintas cargas promedio.",
    "Range of Items: North to South": "Rango de artículos, de norte a sur",
    "Range = maximum triplicate session mean minus minimum triplicate session mean at that site. Simple and easy to communicate in presentations.": "Rango = promedio máximo de sesión triplicada menos promedio mínimo de sesión triplicada en ese sitio. Es una medida simple y fácil de comunicar.",
    "Total Items by River Segment": "Artículos totales por tramo del río",
    "Sum of all recorded items across all events and sites within each named segment. Only sites with segment labels are included.": "Suma de todos los artículos registrados en todos los eventos y sitios dentro de cada tramo con nombre. Solo se incluyen sitios con etiqueta de tramo.",
    "Triplicate Sessions by River Segment": "Sesiones triplicadas por tramo del río",
    "Number of independent exact triplicate sessions within each segment, showing conservative sampling effort distribution.": "Número de sesiones triplicadas exactas e independientes dentro de cada tramo, para mostrar de forma conservadora el esfuerzo de muestreo.",
    "Sites Ranked by Average Items per Plot": "Sitios ordenados por promedio de artículos por parcela",
    "Average items per plot is a fairer metric than total count because it adjusts for how many strict triplicate sessions a site has.": "El promedio de artículos por parcela es una medida más justa que el conteo total porque ajusta por cuántas sesiones triplicadas estrictas tiene cada sitio.",
    "No coordinate data available.": "No hay datos de coordenadas disponibles.",
    "No valid GPS coordinates.": "No hay coordenadas GPS válidas.",
    "No river-segment data is available in the current scope for this figure.": "No hay datos de tramo del río disponibles en el alcance actual para esta figura.",
    "No individual event coordinates in database.": "No hay coordenadas de eventos individuales en la base de datos.",
    "No event-level data available.": "No hay datos a nivel de evento disponibles.",
    "No segment data available.": "No hay datos de tramos disponibles.",
    "No weight data in the database.": "No hay datos de peso en la base de datos.",
    "No date data available for this figure.": "No hay datos de fecha disponibles para esta figura.",
    "No date data available.": "No hay datos de fecha disponibles.",
    "No year data available.": "No hay datos de año disponibles.",
    "No segment data.": "No hay datos de tramos.",
    "Map view": "Vista del mapa",
    "Individual Events": "Eventos individuales",
    "Sort order": "Orden",
    "North to South (GPS)": "De norte a sur (GPS)",
    "By Total Items": "Por artículos totales",
    "By Mean per Plot": "Por promedio por parcela",
    "Filter by River Segment": "Filtrar por tramo del río",
    "All": "Todos",
    L("Table format"): "Formato de tabla",
    L("Wide format—one row per event, each item as a column (like Excel)"): "Formato ancho, una fila por evento y cada artículo como columna (como en Excel)",
    L("Long format—one row per item per event"): "Formato largo, una fila por artículo por evento",
    "Toggle Categories (include/exclude from all figures)": "Cambiar categorías (incluir o excluir en todas las figuras)",
    L("Categories to include in figures"): "Categorías que se mostrarán en las figuras",
    "Select a figure to display": "Selecciona una figura para mostrar",
    "Choose chart": "Elegir gráfica",
    "What it shows": "Qué muestra",
    "Why useful": "Por qué sirve",
    "Why it matters": "Por qué importa",
    "How to read this figure": "Cómo leer esta figura",
    "How to interpret it": "Cómo interpretarla",
    "Additional context": "Contexto adicional",
    "Top 15 Most Frequently Recorded Items": "Top 15 artículos registrados con mayor frecuencia",
    "Ranked by cumulative count across all survey events and locations.": "Ordenados por conteo acumulado en todos los eventos y sitios de muestreo.",
    "Items by River Segment and Category": "Artículos por tramo del río y categoría",
    "Stacked bar chart showing contribution of each trash category within each known river segment. Only sites with assigned segment labels are shown.": "Gráfica de barras apiladas que muestra la contribución de cada categoría de basura dentro de cada tramo conocido del río. Solo se muestran sitios con tramo asignado.",
    "Category Colors:": "Colores de categorías:",
    "Recyclable": "Reciclable",
    "Health Hazard": "Riesgo para la salud",
    "Floatable": "Flotable",
    "Other Non-Recyclable": "Otro no reciclable",
    "City of Tucson standard": "estándar de la Ciudad de Tucson",
    "Rx, Drugs, Nicotine, Toiletries": "medicamentos, drogas, nicotina y artículos de higiene",
    "river health / ADEQ risk": "salud del río / riesgo ADEQ",
    "Plot Records": "Registros de parcelas",
    "Authorized Personnel Only": "Solo personal autorizado",
    "Sign in to\nyour account": "Inicia sesión\nen tu cuenta",
    "Access the Santa Cruz River data dashboard,<br>field entry tools, and analysis reports.": "Accede al panel de datos del Río Santa Cruz,<br>a las herramientas de captura de campo y a los reportes de análisis.",
    "Sign In": "Iniciar sesión",
    "Create Account": "Crear cuenta",
    "Forgot Password": "Olvidé mi contraseña",
    "Look Up Username": "Buscar nombre de usuario",
    "Username": "Nombre de usuario",
    "Password": "Contraseña",
    "Your username is how you sign in. Write it down—there is no way to look it up later. Choose something simple like your first name or initials.": "Tu nombre de usuario es lo que usarás para iniciar sesión. Guárdalo. El sistema no lo recupera automáticamente después. Elige algo simple, como tu nombre o tus iniciales.",
    "Security question (for password reset)": "Pregunta de seguridad (para restablecer contraseña)",
    "— Select one —": "— Selecciona una —",
    "Security question for": "Pregunta de seguridad para",
    "Start over": "Empezar de nuevo",
    "Download CSV": "Descargar CSV",
    "Preview first 30 rows": "Vista previa de las primeras 30 filas",
    "Our Work": "Nuestro trabajo",
    "Santa Cruz River": "Río Santa Cruz",
    "Colorado River Delta": "Delta del Río Colorado",
    "Growing Water Smart": "Growing Water Smart",
    "One Basin": "One Basin",
    "Resources": "Recursos",
    "About Us": "Sobre nosotros",
    "Our Mission & Vision": "Nuestra misión y visión",
    "Our People": "Nuestro equipo",
    "Board": "Consejo",
    "Partners": "Aliados",
    "Financials": "Finanzas",
    "Careers": "Empleo",
    "Sonoran Updates": "Novedades de Sonoran",
    "Sign Up for Newsletter": "Suscríbete al boletín",
    "Become a Sonoran Sustainer": "Hazte miembro de Sonoran",
    "Blog Posts": "Publicaciones del blog",
    "Events": "Eventos",
    "Contact Us": "Contáctanos",
    "Support Us": "Apóyanos",
    "Donate →": "Donar →",
    "Endangered Rivers Report": "Informe de ríos en peligro",
    "Urban Wildlife Refuge": "Refugio urbano de vida silvestre",
    "Living River Reports 2025": "Informes Un Río Vivo 2025",
    "Downtown Tucson to Marana 2025": "Centro de Tucson a Marana 2025",
    "Supplementary Data 2025": "Datos suplementarios 2025",
    "Un Río Vivo—Español 2025": "Un Río Vivo, Español 2025",
    "Site-Level Analysis": "Análisis a nivel de sitio",
    "Where the Trash Is and How Much": "Dónde está la basura y cuánta hay",
    "Trash burden across recorded survey locations. Sites are ordered North to South along the river corridor.": "Carga de basura en los sitios de muestreo registrados. Los sitios están ordenados de norte a sur a lo largo del corredor del río.",
    "Monthly Item Count: Full Record": "Conteo mensual de artículos, registro completo",
    "Annual Totals by Year": "Totales anuales por año",
    "Month by Month Comparison Across Years": "Comparación mes a mes entre años",
    "Average Items Per Survey Event Over Time": "Promedio de artículos por evento de muestreo a lo largo del tiempo",
    "Items by River Segment (Quarterly)": "Artículos por tramo del río, trimestral",
    "Weight of Trash Collected Over Time": "Peso de la basura recolectada a lo largo del tiempo",
    "Totals & Overview": "Totales y panorama general",
    "Food & Beverage": "Alimentos y bebidas",
    "Environmental Risk": "Riesgo ambiental",
    "Trends by Category": "Tendencias por categoría",
    "Geographic": "Geográfico",
    "Data Tables": "Tablas de datos",
    "All 19 Categories: Total Items Ranked": "Las 19 categorías, artículos totales ordenados",
    "All 56 Items: Total Count Ranked": "Los 56 artículos, conteo total ordenado",
    "Category Share: Proportional Breakdown": "Proporción por categoría",
    "Top 10 Heaviest vs Bottom 9 Lightest Categories": "Las 10 categorías más altas frente a las 9 más bajas",
    "Average Items per Survey Event by Category": "Promedio de artículos por evento según categoría",
    "Beverage Containers: Full Breakdown": "Envases de bebidas, desglose completo",
    "Cups: Styrofoam vs Plastic vs Paper": "Vasos, unicel frente a plástico y papel",
    "Food Packaging: All 11 Sub-Items": "Empaques de comida, los 11 subartículos",
    "Alcohol Containers: Beer vs Liquor Over Time": "Envases de alcohol, cerveza frente a licor a lo largo del tiempo",
    "Recyclable vs Non-Recyclable: Item Counts": "Reciclable frente a no reciclable, conteo de artículos",
    "Floatable vs Non-Floatable: River Health Risk": "Flotable frente a no flotable, riesgo para la salud del río",
    "Health Hazard Items: Rx, Drugs, Nicotine, Toiletries": "Artículos de riesgo para la salud, medicamentos, drogas, nicotina y artículos de higiene",
    "Bulk and Large Debris: Appliances, Construction, Auto": "Desechos grandes y voluminosos, electrodomésticos, construcción y automotriz",
    "Category Risk Profile: Composite View": "Perfil de riesgo por categoría, vista compuesta",
    "Category Trends Over Time: Top 6 (Quarterly)": "Tendencias por categoría a lo largo del tiempo, top 6 trimestral",
    "Year over Year Change by Category": "Cambio por categoría año con año",
    "Category Composition: How Mix Changed by Year": "Composición por categoría, cómo cambió la mezcla por año",
    "Category Mix by River Segment": "Mezcla de categorías por tramo del río",
    "Segment Specialization: Top Categories per Reach": "Especialización por tramo, principales categorías por alcance",
    "Full Item-Level Statistics Table": "Tabla completa de estadísticas por artículo",
    "Category Group Summary Table": "Tabla resumen por grupo de categoría",
    "Total Items": "Artículos totales",
    "River Segment": "Tramo del río",
    "Category": "Categoría",
    "Item": "Artículo",
    "Location": "Ubicación",
    "Year": "Año",
    "Month": "Mes",
    "Average Items": "Promedio de artículos",
    "Weight (oz)": "Peso (oz)",
    "Number of Events": "Número de eventos",
    "Standard Deviation": "Desviación estándar",
    "Mean Items per Plot": "Promedio de artículos por parcela",
    "Survey Site": "Sitio de muestreo",
    "Share (%)": "Proporción (%)",
    "Classification": "Clasificación",
    "Date": "Fecha"
}

def L(text, lang=None):
    if text is None:
        return text
    if not isinstance(text, str):
        return text
    if lang is None:
        lang = st.session_state.get("lang", "en")
    if lang != "es":
        return text
    return TEXT_ES.get(text, text)


TEXT_ES.update({
    "Santa Cruz River Program": "Programa del Río Santa Cruz",
    "Tucson, Arizona": "Tucson, Arizona",
    "Trash Survey": "Estudio de basura",
    "Longitudinal monitoring of litter and debris along the Santa Cruz River corridor and tributaries. Plot-based surveys across multiple sites and reaches.": "Monitoreo longitudinal de basura y desechos a lo largo del corredor del Río Santa Cruz y sus tributarios. Muestreos por parcelas en múltiples sitios y tramos.",
    "Program Director": "Director del programa",
    "No exact triplicate sessions are available under the current filters or page scope.": "No hay sesiones triplicadas exactas disponibles con los filtros o el alcance actual de la página.",
    "Total items, number of events, and average items per event by calendar year. Sorted most recent first.": "Artículos totales, número de eventos y promedio de artículos por evento por año calendario. Ordenado del más reciente al más antiguo.",
    "Total items by calendar month across all years combined.": "Artículos totales por mes calendario, sumando todos los años.",
    "One row per survey event. Columns show each of the 56 recorded item types plus event metadata—exactly like the original Excel format. Zero = item was not found that visit.": "Una fila por evento de muestreo. Las columnas muestran cada uno de los 56 tipos de artículos registrados más los metadatos del evento, igual que en el formato original de Excel. Cero significa que ese artículo no apareció en esa visita."
})

TEXT_ES.update({
    "All 19 Categories: Total Items Ranked": "Las 19 categorías, artículos totales ordenados",
    "All 56 Items: Total Count Ranked": "Los 56 artículos, conteo total ordenado",
    "Category Share: Proportional Breakdown": "Proporción por categoría",
    "Top 10 Heaviest vs Bottom 9 Lightest Categories": "10 categorías más pesadas frente a 9 más ligeras",
    "Average Items per Survey Event by Category": "Promedio de artículos por evento por categoría",
    "Beverage Containers: Full Breakdown": "Envases de bebidas, desglose completo",
    "Cups: Styrofoam vs Plastic vs Paper": "Vasos, unicel frente a plástico y papel",
    "Food Packaging: All 11 Sub-Items": "Empaques de comida, los 11 subtipos",
    "Alcohol Containers: Beer vs Liquor Over Time": "Envases de alcohol, cerveza frente a licor a lo largo del tiempo",
    "Bulk and Large Debris: Appliances, Construction, Auto": "Residuos grandes y voluminosos, electrodomésticos, construcción y auto",
    "Category Risk Profile: Composite View": "Perfil de riesgo por categoría",
    "Category Trends Over Time: Top 6 (Quarterly)": "Tendencias por categoría a lo largo del tiempo, las 6 principales",
    "Year over Year Change by Category": "Cambio por categoría de un año a otro",
    "Category Composition: How Mix Changed by Year": "Composición por categoría, cómo cambió la mezcla por año",
    "Category Mix by River Segment": "Mezcla de categorías por tramo del río",
    "Segment Specialization: Top Categories per Reach": "Especialización por tramo, categorías principales por sección",
    "Full Item-Level Statistics Table": "Tabla completa de estadísticas por artículo",
    "Category Group Summary Table": "Tabla resumen por grupo de categoría",
    "Totals & Overview": "Totales y resumen",
    "Food & Beverage": "Alimentos y bebidas",
    "Environmental Risk": "Riesgo ambiental",
    "Trends by Category": "Tendencias por categoría",
    "Geographic": "Geográfico",
    "Data Tables": "Tablas de datos",
    "Every trash category ranked by cumulative item count. Colors encode environmental classification.": "Cada categoría de basura ordenada por conteo acumulado de artículos. Los colores muestran la clasificación ambiental.",
    "The most important summary figure—use it to explain which categories drive the problem to any audience.": "Es la figura resumen más importante. Sirve para explicar qué categorías impulsan el problema a cualquier audiencia.",
    "Every recorded item type ranked by total count from most to least common across all survey events.": "Cada tipo de artículo registrado, ordenado por conteo total desde el más común hasta el menos común en todos los eventos de muestreo.",
    "Pinpoints specific items for prevention campaigns, source identification, and partnership messaging.": "Ayuda a identificar artículos específicos para campañas de prevención, búsqueda de fuentes y mensajes con aliados.",
    "Donut chart showing each category as a percentage of all recorded items.": "Gráfica de dona que muestra cada categoría como porcentaje de todos los artículos registrados.",
    "Easy to present in reports—shows visually that Food Packaging dominates the composition.": "Es fácil de presentar en reportes y muestra visualmente que los empaques de comida dominan la composición.",
    "All categories split into Recyclable vs Non-Recyclable per City of Tucson recycling guidelines.": "Todas las categorías separadas entre reciclable y no reciclable según las reglas de reciclaje de la Ciudad de Tucson.",
    "Categories classified by whether they float and enter waterways during rain or flooding events.": "Categorías clasificadas según si flotan y entran al agua durante lluvias o inundaciones.",
    "Items with direct public health risk: syringes, drug packaging, cigarettes, lighters, and toiletries.": "Artículos con riesgo directo para la salud pública, como jeringas, envolturas de drogas, cigarros, encendedores y artículos de higiene.",
    "Large items requiring equipment: appliances, furniture, tires, car parts, construction debris.": "Artículos grandes que requieren equipo para retirarse, como electrodomésticos, muebles, llantas, autopartes y residuos de construcción.",
    "Top: Heatmap shows each category's item count per year. Darker green = more items. Bottom: Stacked bar shows total burden per year with category breakdown.": "Arriba, el mapa de calor muestra el conteo de artículos por categoría y por año. Verde más oscuro significa más artículos. Abajo, la barra apilada muestra la carga total por año con el desglose por categoría.",
    "100% stacked bars—each bar totals 100%, showing category SHARE each year.": "Barras apiladas al 100%. Cada barra suma 100% y muestra la proporción de cada categoría en cada año.",
    "Stacked bars showing category composition across the four named river reaches.": "Barras apiladas que muestran la composición por categoría en los cuatro tramos nombrados del río.",
    "Top categories for each river segment shown in individual tabs.": "Las categorías principales de cada tramo del río se muestran en pestañas separadas.",
    "Average items per plot is a fairer metric than total count because it adjusts for how many strict triplicate sessions a site has.": "El promedio de artículos por parcela es una medida más justa que el conteo total porque ajusta por cuántas sesiones triplicadas estrictas tiene cada sitio.",
    "Recyclable vs Non-Recyclable by Category": "Reciclable frente a no reciclable por categoría",
    "Floatable vs Non-Floatable by Category": "Flotable frente a no flotable por categoría",
    "Health Hazard Categories: Totals": "Categorías de riesgo para la salud, totales",
    "Health Hazard Items: Sub-Types": "Artículos de riesgo para la salud, subtipos",
    "Health Hazard Items Over Time": "Artículos de riesgo para la salud a lo largo del tiempo",
    "Bulk Debris: Category Totals": "Residuos voluminosos, totales por categoría",
    "Bulk Debris: All Sub-Types": "Residuos voluminosos, todos los subtipos",
    "Annual Item Totals by Category (Heatmap)": "Totales anuales de artículos por categoría, mapa de calor",
    "Annual Category Totals: Stacked Bar": "Totales anuales por categoría, barra apilada",
    "Category Composition by Year: Proportional": "Composición por categoría por año, proporcional",
    "Category Composition by River Segment": "Composición por categoría por tramo del río",
    "Total Items": "Artículos totales",
    "Share of Total (%)": "Proporción del total (%)",
    "Segment": "Tramo",
    "Quarter": "Trimestre",
    "Items": "Artículos",
    "Total": "Total",
    "Classification based on <strong>City of Tucson recycling guidelines</strong>.": "Clasificación basada en las <strong>reglas de reciclaje de la Ciudad de Tucson</strong>.",
    "Floatable items travel downstream during rain events and reach waterways.": "Los artículos flotables viajan río abajo durante las lluvias y llegan al agua.",
    "" + L("Based on Sonoran Institute field classification.") + "": "Basado en la clasificación de campo del Sonoran Institute.",
    "" + L("Blue = Recyclable") + "": "Azul = reciclable",
    "" + L("Red = Non-Recyclable") + "": "Rojo = no reciclable",
    "" + L("Blue = Floatable") + "": "Azul = flotable",
    "" + L("Gray = Non-Floatable") + "": "Gris = no flotable",
    "Yes": "Sí",
    "No": "No",
    "Non-Recyclable": "No reciclable",
    "Non-Floatable": "No flotable"
})

SPANISH_MONTHS = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

def fmt_month_year_local(val):
    if val is None or val == "":
        return ""
    try:
        ts = pd.Timestamp(val)
        if st.session_state.get("lang", "en") == "es":
            return f"{SPANISH_MONTHS.get(ts.month, ts.strftime('%B'))} {ts.year}"
        return ts.strftime("%B %Y")
    except Exception:
        return str(val)


def fmt_full_date_local(val):
    if val is None or val == "":
        return ""
    try:
        ts = pd.Timestamp(val)
        if st.session_state.get("lang", "en") == "es":
            return f"{SPANISH_MONTHS.get(ts.month, ts.strftime('%B'))} {ts.day:02d}, {ts.year}"
        return ts.strftime("%B %d, %Y")
    except Exception:
        return str(val)


TEXT_ES.update({
    "River Segments": "Tramos del río",
    "Trash Burden": "Carga de basura",
    "Low": "Baja",
    "High": "Alta",
    "North Reach": "Tramo norte",
    "Central Reach": "Tramo central",
    "South Reach": "Tramo sur",
    "Rillito": "Rillito",
    "Other": "Otro",
    "Sites with GPS": "Sitios con GPS",
    "Total Sites in DB": "Total de sitios en la base de datos",
    "Events Mapped": "Eventos en el mapa",
    "Grand Avg Items/Site": "Promedio general de artículos por sitio",
    "River Segment Colors": "Colores por tramo del río",
    "Map Color = Trash Burden (Total Items)": "Color del mapa = carga de basura (artículos totales)",
    "Map Color = Trash Burden": "Color del mapa = carga de basura",
    "Sites with GPS Coordinates": "Sitios con coordenadas GPS",
    "All survey locations that have latitude/longitude data. Sorted by total items recorded descending.": "Todos los sitios de muestreo que tienen datos de latitud y longitud. Están ordenados de mayor a menor según el total de artículos registrados.",
    "Site Name": "Nombre del sitio",
    "Total Items": "Artículos totales",
    "# Events": "# Eventos",
    "Avg Items/Event": "Promedio de artículos por evento",
    "Latitude": "Latitud",
    "Longitude": "Longitud",
    "All Sites (Including Those Without GPS)": "Todos los sitios, incluso los que no tienen GPS",
    "Complete list of all recorded locations in the database, with or without coordinates.": "Lista completa de todos los sitios registrados en la base de datos, con o sin coordenadas.",
    "Showing": "Mostrando",
    "unique location names in the current analysis scope. Many may have slight spelling variations (e.g. 'Drexel and Irvington' vs 'Drexel and irvington') which cause them to appear as separate entries.": "nombres únicos de ubicación dentro del alcance actual del análisis. Varias ubicaciones pueden tener diferencias pequeñas de escritura, por ejemplo mayúsculas o variaciones leves del nombre, y por eso pueden aparecer como entradas separadas.",
    "Latitude and longitude values are averaged from all records for that site. 'Avg Items/Event' = total items ÷ number of survey events at that location. Map circles: blue = lower trash burden, red = higher trash burden.": "Los valores de latitud y longitud se promedian usando todos los registros de ese sitio. 'Promedio de artículos por evento' = artículos totales ÷ número de eventos de muestreo en esa ubicación. En el mapa, los círculos azules indican menor carga de basura y los rojos indican mayor carga.",
    "Map colors": "Colores del mapa",
    "Blue": "Azul",
    "Orange": "Naranja",
    "Red": "Rojo",
    "Click any circle to see site details and exact counts.": "Haz clic en cualquier círculo para ver los detalles del sitio y los conteos exactos.",
    "How trash burden is calculated": "Cómo se calcula la carga de basura",
    "Each site's color is determined by the total number of individual trash items recorded at that site across all survey events in the database. This is the sum of all 19 trash categories (food packaging, cups, clothing, nicotine products, construction debris, etc.) counted during every field visit to that location. Sites with more total items appear warmer (orange to red), while sites with fewer items appear cooler (blue to teal).": "El color de cada sitio se basa en la cantidad total de artículos de basura registrados en ese lugar a lo largo de todos los eventos de muestreo de la base de datos. Es la suma de las 19 categorías de basura, como empaques de comida, vasos, ropa, productos de nicotina y desechos de construcción, contadas en cada visita de campo a esa ubicación. Los sitios con más artículos se ven en colores más cálidos, de naranja a rojo, y los sitios con menos artículos se ven en colores más fríos, de azul a verde azulado.",
    "Why logarithmic color scaling": "Por qué se usa una escala logarítmica de color",
    "A few high-count sites would compress all other sites into the same blue if a linear scale were used. Logarithmic spacing spreads the colors across the full range so differences among lower-count sites remain visible.": "Si se usara una escala lineal, unos pocos sitios con conteos muy altos harían que casi todos los demás se vieran del mismo azul. La escala logarítmica reparte mejor los colores en todo el rango para que también se noten las diferencias entre sitios con conteos más bajos.",
    "What this metric represents": "Qué representa esta medida",
    "Cumulative litter load over time, not density per square meter or items per single visit. A site surveyed more often will naturally accumulate a higher total, so read this alongside the number of survey events shown in each popup.": "Representa la carga acumulada de basura a lo largo del tiempo, no la densidad por metro cuadrado ni la cantidad de artículos en una sola visita. Un sitio muestreado más veces normalmente tendrá un total más alto, así que conviene leer este valor junto con el número de eventos de muestreo que aparece en cada ventana del mapa.",
    "Date": "Fecha"
})

C = dict(
    forest="#7a8f35", green="#93a445", sage="#a8b85a", mint="#ffffff",
    cream="#faf7f0", sand="#f2ede2", sand2="#e8e1d0", sand3="#d8ceba",
    gold="#c9820e", amber="#e8a620", earth="#8b4513", brick="#b5451b",
    sky="#1a5276", water="#2471a3",
    text="#18180f", med="#3a3a28", muted="#686854", divider="#cec6b0", white="#ffffff",
)
PAL = ["#93a445","#2471a3","#b5451b","#e8a620","#a8b85a","#6c4f8a","#2e8b8b","#d4a017","#888877","#8b4513","#c0392b","#16a085","#e07b4c","#4a7c59","#9b59b6","#34759a","#cc6677","#557a44","#af6e3d"]

from PIL import Image as _PILImg, ImageDraw as _PILDraw
_fi = _PILImg.new("RGBA",(32,32),(0,0,0,0))
_fd = _PILDraw.Draw(_fi)
_fd.ellipse([1,1,30,30],fill=(122,143,53))
_fd.ellipse([10,10,20,20],fill=(255,255,255,240))
_fd.ellipse([17,7,24,14],fill=(255,255,255,240))
_fd.line([(23,10),(28,9)],fill=(255,255,255,240),width=1)
_fd.polygon([(11,14),(6,6),(8,4),(14,10)],fill=(255,255,255,220))
_fd.polygon([(10,18),(5,24),(7,25),(12,20)],fill=(255,255,255,220))
st.set_page_config(page_title="SCR Trash Survey · Sonoran Institute", page_icon=_fi,
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
/* Kill browser/Streamlit default blue link color globally */
.stApp a, .stApp a:visited, .stMarkdownContainer a, .stMarkdownContainer a:visited,
[data-testid="stMarkdownContainer"] a, [data-testid="stMarkdownContainer"] a:visited {{
    color:inherit!important;
    text-decoration:none!important;
}}
[data-testid="stMarkdownContainer"] a:hover {{
    color:{C["mint"]}!important;
    text-decoration:underline!important;
    text-decoration-color:rgba(93,168,50,.4)!important;
}}
.block-container{{padding:0!important;max-width:100%!important;}}
[data-testid="stSidebar"],[data-testid="collapsedControl"]{{display:none!important;}}

/* ── HEADER ── */
.hdr{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 60%,{C["sage"]} 100%);
      border-bottom:none;margin-bottom:0;box-shadow:none;}}
.hdr-in{{max-width:1360px;margin:0 auto;padding:14px 96px;
         display:flex;align-items:center;justify-content:space-between;}}
.hdr-brand{{display:flex;align-items:center;gap:18px;}}
.hdr-logo{{height:42px;}}
.hdr-name{{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;
           color:#fff;line-height:1.2;letter-spacing:-.01em;}}
.hdr-sub{{font-size:9.5px;color:rgba(255,255,255,.45);letter-spacing:2px;
          text-transform:uppercase;margin-top:3px;font-family:'DM Mono',monospace;}}
.hdr-right{{display:flex;align-items:center;gap:0;}}
.hdr-user{{font-size:13px;color:rgba(255,255,255,.7);line-height:1.5;text-align:right;padding-right:16px;}}
.hdr-user strong{{color:#fff;font-size:14px;display:block;font-weight:600;}}
.hdr-pos{{font-size:11px;color:rgba(255,255,255,.5);display:block;}}
.hdr-pill{{display:inline-flex;align-items:center;gap:5px;background:rgba(93,168,50,.2);
           border:1px solid rgba(93,168,50,.4);border-radius:20px;padding:2px 10px;
           font-size:10px;color:{C["mint"]};font-family:'DM Mono',monospace;
           letter-spacing:.5px;margin-top:3px;}}
.hdr-dot{{width:6px;height:6px;background:{C["mint"]};border-radius:50%;
          animation:pulse 2s infinite;display:inline-block;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.4;}}}}

/* ── NAV—uses components.html iframe for perfect rendering ── */
.nav-outer{{background:{C["forest"]};position:sticky;top:0;z-index:200;
            border-bottom:1px solid rgba(255,255,255,.08);
            box-shadow:0 3px 14px rgba(0,0,0,.35);}}

/* Hide the actual Streamlit radio group—nav is rendered via iframe */
.nav-radio-hide div[role="radiogroup"]{{
    position:absolute!important;opacity:0!important;
    pointer-events:none!important;height:0!important;overflow:hidden!important;
}}

/* ── KILL ALL GAPS—NUCLEAR ── */
.stApp,.stApp>div,.stApp>div>div {{overflow-x:hidden;background:{C["cream"]};}}
section[data-testid="stMain"] {{padding-top:0!important;margin-top:0!important;}}
section[data-testid="stMain"]>div:first-child {{padding-top:0!important;margin-top:0!important;}}
[data-testid="stAppViewBlockContainer"]>div:first-child {{padding-top:0!important;margin-top:0!important;}}
.css-z5fcl4,.css-1d391kg,.css-ffhzg2 {{padding-top:0!important;margin-top:0!important;}}
.main .block-container,.block-container,
section[data-testid="stMain"]>div,section[data-testid="stMain"]>div>div,
[data-testid="stMainBlockContainer"],[data-testid="stAppViewBlockContainer"],
[data-testid="stAppViewContainer"],div[class*="block-container"],
div[class*="appview-container"]>section>div {{
    padding-top:0!important;padding-bottom:0!important;
    margin-top:0!important;margin-bottom:0!important;
}}
.stMainBlockContainer>div,.stMainBlockContainer>div>div {{
    padding-top:0!important;margin-top:0!important;
}}
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlock"]>[data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stVerticalBlock"]>.element-container,
[data-testid="block-container"] {{
    gap:0!important;margin-top:0!important;margin-bottom:0!important;
    padding-top:0!important;padding-bottom:0!important;
}}
/* The inter-element gap Streamlit adds between markdown blocks */
.element-container {{margin-top:0!important;margin-bottom:0!important;padding:0!important;}}
[data-testid="stMarkdownContainer"] {{margin:0!important;padding:0!important;}}
/* Override Streamlit's stMainBlockContainer top padding—this is the cream gap source */
[data-testid="stMainBlockContainer"],
.stMainBlockContainer,
[data-testid="stAppViewBlockContainer"] {{
    padding-top:0!important;margin-top:0!important;
    padding-left:0!important;padding-right:0!important;
}}
/* The header's bottom should bleed into the sticky nav with no cream gap */
div[data-testid="stVerticalBlock"]:first-of-type>.element-container:first-child {{
    margin-top:0!important;padding-top:0!important;line-height:0!important;font-size:0!important;
}}
/* ── BODY ── */
.body{{max-width:1360px;margin:0 auto;padding:24px 96px 80px 96px;background:{C["cream"]};}}
.pg-title{{font-family:'Cormorant Garamond',serif;font-size:2.2rem;font-weight:700;
           color:{C["green"]};letter-spacing:-.02em;line-height:1.15;margin-bottom:6px;}}
.pg-lead{{font-size:14px;color:{C["muted"]};line-height:1.8;max-width:780px;margin-bottom:28px;}}
.sec-hd{{font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;
          color:{C["text"]};margin-bottom:4px;letter-spacing:-.01em;}}
.sec-sub{{font-size:11.5px;color:{C["muted"]};margin-bottom:20px;line-height:1.7;}}
@media print {{
    /* Show the full page on print, not just the visible viewport */
    .stApp {{ overflow:visible!important; }}
    section.main, .block-container, [data-testid="stMainBlockContainer"] {{
        overflow:visible!important;
        height:auto!important;
        max-height:none!important;
    }}
    [data-testid="stVerticalBlock"] {{
        overflow:visible!important;
        height:auto!important;
    }}
    /* Hide Streamlit chrome */
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    footer, .stDeployButton, button {{ display:none!important; }}
    /* Page breaks */
    .body {{ padding:20px!important; }}
    h1, h2, h3 {{ page-break-after:avoid; }}
    .js-plotly-plot {{ page-break-inside:avoid; }}
}}
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
.card{{background:#fff;border:1px solid {C["sand3"]};border-radius:12px;
       padding:32px 32px 24px;margin-bottom:32px;box-shadow:0 2px 14px rgba(0,0,0,.05);}}
.card-hd{{display:flex;align-items:flex-start;justify-content:space-between;
          padding-bottom:14px;margin-bottom:20px;border-bottom:1px solid {C["sand3"]};}}

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
  border-color:{C["green"]}!important;box-shadow:0 0 0 3px rgba(147,164,69,.15)!important;}}
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
div[data-testid="stExpander"]{{background:{C["cream"]}!important;border:1px solid {C["sand3"]}!important;border-radius:10px!important;}}
div[data-testid="stExpander"] details,div[data-testid="stExpander"] summary,div[data-testid="stExpander"] div[data-testid="stExpanderDetails"]{{background:{C["cream"]}!important;border:none!important;}}

/* ── SCROLLBAR ── */
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:{C["sand"]};}}
::-webkit-scrollbar-thumb{{background:{C["sand3"]};border-radius:3px;}}
::-webkit-scrollbar-thumb:hover{{background:{C["sage"]};}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px);}}to{{opacity:1;transform:none;}}}}
.fade-up{{animation:fadeUp .45s ease both;}}
.card{{transition:box-shadow .3s ease,transform .3s ease;}}
.card:hover{{box-shadow:0 10px 36px rgba(0,0,0,.1);transform:translateY(-3px);}}
.kpi{{transition:box-shadow .3s ease,transform .3s ease;}}
.kpi:hover{{box-shadow:0 10px 30px rgba(122,143,53,.15);transform:translateY(-3px);}}
.stat-item{{transition:background .2s ease;}}
.stat-item:hover{{background:rgba(147,164,69,.05);}}
.ftr-social-icon{{transition:all .25s ease;}}
.ftr-social-icon:hover{{transform:translateY(-2px);}}

/* ── ABOUT PAGE WRAPPER ── */
.about-shell{{max-width:1220px;margin:0 auto;padding:0 132px;box-sizing:border-box;}}
.about-hero{{background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 60%,{C["sage"]} 100%);
    border-radius:12px;padding:44px 56px;margin:0 0 28px 0;position:relative;overflow:hidden;}}
.about-body{{max-width:1220px;margin:0 auto;padding:0 132px 80px 132px;box-sizing:border-box;background:{C["cream"]};}}
@media (max-width: 1200px){{
  .about-shell,.about-body{{padding-left:88px;padding-right:88px;}}
  .about-hero{{padding-left:44px;padding-right:44px;}}
}}
@media (max-width: 900px){{
  .about-shell,.about-body{{padding-left:28px;padding-right:28px;}}
  .about-hero{{padding-left:24px;padding-right:24px;}}
}}

/* ── FOOTER ── */
.ftr{{background:linear-gradient(160deg,{C["forest"]} 0%,#7a8f35 100%);
      padding:36px 0 28px;margin-top:0;border-top:2px solid {C["sage"]};}}
.ftr-in{{max-width:1360px;margin:0 auto;padding:0 96px;}}
.ftr-copy{{color:rgba(255,255,255,.96);font-size:12px;line-height:1.9;font-family:'DM Sans',sans-serif;font-weight:500;}}
.ftr-a{{color:rgba(255,255,255,.97)!important;text-decoration:none!important;transition:color .15s;font-weight:500;}}
.ftr-a:hover{{color:#ffffff!important;text-decoration:underline!important;text-decoration-color:rgba(255,255,255,.45)!important;}}
.ftr-social-icon{{display:inline-flex;align-items:center;justify-content:center;
    width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.08);
    border:1px solid rgba(255,255,255,.15);margin-right:6px;text-decoration:none;
    font-size:12px;color:rgba(255,255,255,.6);transition:all .15s;}}
.ftr-social-icon:hover{{background:rgba(93,168,50,.25);border-color:{C["mint"]};color:{C["mint"]};}}
.ftr-divider{{border:none;border-top:1px solid rgba(255,255,255,.08);margin:20px 0;}}
.ftr-links-row{{display:flex;flex-wrap:wrap;gap:6px 28px;}}
.ftr-section-lbl{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:2px;
    text-transform:uppercase;color:rgba(255,255,255,.82);margin-bottom:12px;display:block;}}

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
def _clean_hover(fig):
    """Force clean professional hover labels on every trace."""
    for trace in fig.data:
        t = getattr(trace, "type", "")
        nm = trace.name if hasattr(trace,"name") and trace.name and str(trace.name) not in ("0","","None") else ""
        p = f"<b>{nm}</b><br>" if nm else ""
        if t == "bar":
            trace.hovertemplate = p + ("<b>%{y}</b><br>Total items: %{x:,.0f}<extra></extra>" if getattr(trace,"orientation",None)=="h" else "<b>%{x}</b><br>Total items: %{y:,.0f}<extra></extra>")
        elif t == "scatter":
            trace.hovertemplate = p + "<b>%{x}</b><br>Total items: %{y:,.0f}<extra></extra>"
        elif t == "pie":
            trace.hovertemplate = "<b>%{label}</b><br>Share: %{percent}<br>Total items: %{value:,.0f}<extra></extra>"
        elif t == "heatmap":
            trace.hovertemplate = "<b>%{y}</b><br>Year: %{x}<br>Total items: %{z:,.0f}<extra></extra>"
        elif t in ("scattergeo","scattermapbox"):
            trace.hovertemplate = "%{text}<extra></extra>"
        elif t == "box":
            trace.hovertemplate = p + "Median: %{median:,.0f}<br>Lowest: %{lowerfence:,.0f}<br>Highest: %{upperfence:,.0f}<extra></extra>"
        elif t == "violin":
            trace.hovertemplate = p + "Value: %{y:,.0f}<extra></extra>"
        elif t == "histogram":
            trace.hovertemplate = "Bin: %{x}<br>Frequency: %{y:,.0f}<extra></extra>"
        else:
            ht = getattr(trace,"hovertemplate",None)
            if ht and "<extra></extra>" not in str(ht): trace.hovertemplate = str(ht)+"<extra></extra>"
    return fig

def fb(fig, xt=None, yt=None, h=400, leg=True, title=None):
    xt = L(xt)
    yt = L(yt)
    title = L(title)
    fig.update_layout(
        height=h, paper_bgcolor="white", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color=C["text"], size=12),
        margin=dict(l=10,r=10,t=56 if title else 32,b=80),
        title=dict(text=title, font=dict(family="Cormorant Garamond, serif", size=16, color=C["green"]),
                   x=0, xanchor="left", pad=dict(l=0)) if title else None,
        legend=dict(bgcolor="rgba(255,255,255,.95)",bordercolor=C["divider"],borderwidth=1,
                    font=dict(size=10),orientation="h",yanchor="top",y=-0.12,
                    xanchor="left",x=0) if leg else dict(visible=False),
        xaxis_title=xt, yaxis_title=yt,
        hoverlabel=dict(
            bgcolor="white", bordercolor=C["divider"],
            font=dict(family="DM Sans, sans-serif", size=12.5, color=C["text"]),
        ),
    )
    fig.update_xaxes(showgrid=False,zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    fig.update_yaxes(showgrid=True,gridcolor=C["sand2"],zeroline=False,linecolor=C["divider"],tickfont=dict(size=11,color=C["muted"]))
    _clean_hover(fig)
    return fig

def show(fig, key=None):
    _clean_hover(fig)
    _nm_en={"n":"Total Items","seg":"River Segment","trash_group":"Category","trash_item":"Item","site_label":"Location","year_str":"Year","month_name":"Month","total":"Total Items","avg":"Average Items","weight_oz":"Weight (oz)","events":"Number of Events","sd":"Standard Deviation","cv_pct":"CV (%)","mean":"Mean Items per Plot","site_display":"Survey Site","share":"Share (%)","recyclable":"Classification","floatable":"Classification","year":"Year","date":"Date"}
    _nm={k:L(v) for k,v in _nm_en.items()}
    for a in ["xaxis","yaxis"]:
        try:
            ax=fig.layout[a]
            if ax and ax.title and hasattr(ax.title,"text") and ax.title.text in _nm: ax.title.text=_nm[ax.title.text]
            elif ax and ax.title and hasattr(ax.title,"text") and ax.title.text in _nm_en: ax.title.text=_nm[_nm_en[ax.title.text]] if _nm_en[ax.title.text] in _nm else L(_nm_en[ax.title.text])
        except: pass
    try:
        lt=fig.layout.legend.title.text
        if lt and lt in _nm: fig.layout.legend.title.text=_nm[lt]
        elif lt and lt in _nm_en: fig.layout.legend.title.text=L(_nm_en[lt])
    except: pass
    fig.update_layout(hoverlabel=dict(bgcolor="white",bordercolor="#d8ceba",font=dict(family="DM Sans, sans-serif",size=12.5,color="#18180f")))
    st.plotly_chart(fig, config=PC, use_container_width=True, key=key)
    try:
        _ldate = st.session_state.get("_db_latest_date", "")
        _today = fmt_full_date_local(date.today())
        _ldate_disp = fmt_month_year_local(_ldate) if _ldate else ""
        if _ldate_disp:
            _badge = f"{T('data_current')} <strong>{_ldate_disp}</strong> &nbsp;·&nbsp; {T('dashboard_refreshed')} {_today}"
        else:
            _badge = f"{T('dashboard_refreshed')} {_today}"
        st.markdown(
            f'<div style="font-size:10.5px;color:{C["muted"]};font-family:DM Mono,monospace;' +
            f'letter-spacing:.3px;padding:2px 0 6px;text-align:right;opacity:.75;">{_badge}</div>',
            unsafe_allow_html=True
        )
    except Exception: pass

def card_open(title, subtitle=""):
    title = L(title)
    subtitle = L(subtitle)
    sub = f'<div class="sec-sub" style="margin:8px 0 0 0;line-height:1.85;color:{C["muted"]};max-width:980px;font-size:13px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="background:white;border:1px solid {C['sand3']};border-radius:14px;
                    padding:28px 38px 22px;margin:0 0 14px 0;
                    box-shadow:0 2px 10px rgba(0,0,0,.04);">
            <div class="sec-hd" style="margin:0 0 10px 0;font-size:1.6rem;line-height:1.12;color:{C['text']};">{title}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True
    )

def card_close():
    return

def tbl_note(text):
    st.markdown(f'<div class="tbl-note">{L(text)}</div>', unsafe_allow_html=True)

def section_title(text):
    st.markdown(f'<div style="font-family:Cormorant Garamond,serif;font-size:1.3rem;font-weight:700;color:{C["green"]};margin:36px 0 18px;padding-bottom:10px;border-bottom:2px solid {C["sand3"]};">{L(text)}</div>', unsafe_allow_html=True)

def page_banner(eyebrow, title, subtitle, img_url=None, img_alt=""):
    """Full-bleed hero banner, same size and aesthetic as About page."""
    eyebrow, title, subtitle = L(eyebrow), L(title), L(subtitle)
    bg_img = img_url or "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg"
    st.markdown(f"""
    <div style="
        background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 55%,{C["sage"]} 100%);
        border-radius:0;
        padding:36px 96px 36px;
        margin:0;
        position:relative;
        overflow:hidden;
        box-shadow:none;">
      <div style="position:absolute;inset:0;
        background:url('{bg_img}') center/cover no-repeat;
        opacity:.18;border-radius:0 0 16px 16px;"></div>
      <div style="position:absolute;inset:0;
        background-image:radial-gradient(circle at 1px 1px,rgba(93,168,50,.05) 1px,transparent 0);
        background-size:28px 28px;"></div>
      <div style="position:relative;z-index:2;max-width:860px;">
        <div style="font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:3px;
          text-transform:uppercase;color:{C["mint"]};margin-bottom:16px;">{eyebrow}</div>
        <div style="font-family:'Cormorant Garamond',serif;font-size:2.6rem;font-weight:700;
          color:white;line-height:1.08;letter-spacing:-.02em;margin-bottom:14px;">{title}</div>
        <div style="font-size:14px;color:rgba(255,255,255,.8);line-height:1.9;max-width:700px;">{subtitle}</div>
      </div>
    </div>""", unsafe_allow_html=True)
def card_open(title, subtitle=""):
    title = L(title)
    subtitle = L(subtitle)
    sub = f'<div class="sec-sub" style="margin:8px 0 0 0;line-height:1.85;color:{C["muted"]};max-width:980px;font-size:13px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="background:white;border:1px solid {C['sand3']};border-radius:14px;
                    padding:28px 38px 22px;margin:0 0 14px 0;
                    box-shadow:0 2px 10px rgba(0,0,0,.04);">
            <div class="sec-hd" style="margin:0 0 10px 0;font-size:1.6rem;line-height:1.12;color:{C['text']};">{title}</div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True
    )

def card_close():
    return

def tbl_note(text):
    st.markdown(f'<div class="tbl-note">{L(text)}</div>', unsafe_allow_html=True)

def section_title(text):
    st.markdown(f'<div style="font-family:Cormorant Garamond,serif;font-size:1.3rem;font-weight:700;color:{C["green"]};margin:36px 0 18px;padding-bottom:10px;border-bottom:2px solid {C["sand3"]};">{L(text)}</div>', unsafe_allow_html=True)

def page_banner(eyebrow, title, subtitle, img_url=None, img_alt=""):
    """Full-bleed hero banner—same size and aesthetic as About page."""
    eyebrow, title, subtitle = L(eyebrow), L(title), L(subtitle)
    bg_img = img_url or "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg"
    st.markdown(f"""
    <div style="
        background:linear-gradient(160deg,{C["forest"]} 0%,{C["green"]} 55%,{C["sage"]} 100%);
        border-radius:0;
        padding:32px 80px 32px;
        margin:0;
        position:relative;
        overflow:hidden;
        box-shadow:none;">
      <!-- River photo overlay at 18% opacity, identical to About hero -->
      <div style="position:absolute;inset:0;
        background:url('{bg_img}') center/cover no-repeat;
        opacity:.18;border-radius:0 0 16px 16px;"></div>
      <!-- Subtle dot-grid texture -->
      <div style="position:absolute;inset:0;
        background-image:radial-gradient(circle at 1px 1px,rgba(93,168,50,.05) 1px,transparent 0);
        background-size:28px 28px;"></div>
      <!-- Content -->
      <div style="position:relative;z-index:2;max-width:820px;">
        <div style="font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:3px;
          text-transform:uppercase;color:{C["mint"]};margin-bottom:14px;">{eyebrow}</div>
        <div style="font-family:'Cormorant Garamond',serif;font-size:2.6rem;font-weight:700;
          color:white;line-height:1.08;letter-spacing:-.02em;margin-bottom:12px;">{title}</div>
        <div style="font-size:14px;color:rgba(255,255,255,.68);line-height:1.85;max-width:660px;">{subtitle}</div>
      </div>
    </div>""", unsafe_allow_html=True)

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
    # Try full insert with security columns first
    try:
        get_sb().table("users").insert({
            "username":u,"password_hash":_hash(password,salt),"salt":salt,
            "full_name":full_name.strip(),"position_title":position.strip(),
            "security_question":sec_q.strip(),
            "security_answer_hash":_hash(sec_a.strip().lower(), ans_salt),
            "security_answer_salt":ans_salt,
        }).execute()
        return True,"Account created! You can now sign in."
    except Exception as e:
        err = str(e)
        if "unique" in err.lower() or "duplicate" in err.lower():
            return False,"That username is already taken—please choose a different one."

    # First insert failed for non-duplicate reason—try without security columns
    # (handles case where schema hasn't been updated yet in Supabase)
    try:
        get_sb().table("users").insert({
            "username":u,"password_hash":_hash(password,salt),"salt":salt,
            "full_name":full_name.strip(),"position_title":position.strip(),
        }).execute()
        return True,(
            "✅ Account created! You can sign in now.\n\n"
            "⚠️ Note: Password reset via security question is not active yet. "
            "Contact Kevin Robles if you ever need a password reset. "
            "Your account and password are fully secure."
        )
    except Exception as e2:
        err2 = str(e2)
        if "unique" in err2.lower() or "duplicate" in err2.lower():
            return False,"That username is already taken—please choose a different one."
        return False, f"Could not create account. Please contact Kevin Robles. (Error: {err2})"

def get_security_question(username):
    """Return the security question for a username, or None."""
    try:
        r = get_sb().table("users").select("security_question").eq("username",username.strip()).execute()
        if r.data and r.data[0].get("security_question"):
            return r.data[0]["security_question"]
        return None
    except Exception:
        # Security columns may not exist yet—that's OK, just return None
        return None

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
    except Exception: return False

def get_username_by_fullname(full_name, sec_answer):
    """Look up username by full name + security answer—lets users recover forgotten usernames."""
    try:
        # Try with security columns first
        r = get_sb().table("users").select("username,full_name,security_answer_hash,security_answer_salt").execute()
        if not r.data: return None
        for row in r.data:
            if row.get("full_name","").strip().lower() == full_name.strip().lower():
                ans_hash = row.get("security_answer_hash","")
                ans_salt = row.get("security_answer_salt","")
                if ans_hash and ans_salt:
                    if secrets.compare_digest(ans_hash, _hash(sec_answer.strip().lower(), ans_salt)):
                        return row["username"]
        return None
    except Exception:
        # Security columns may not exist yet—fall back to name-only lookup
        try:
            r = get_sb().table("users").select("username,full_name").execute()
            if not r.data: return None
            for row in r.data:
                if row.get("full_name","").strip().lower() == full_name.strip().lower():
                    return row["username"]
        except Exception: pass
        return None

def reset_password(username, new_password):
    """Set a new password for a user (called after security answer verified)."""
    if len(new_password)<6: return False,"Password must be at least 6 characters."
    salt = secrets.token_hex(16)
    try:
        get_sb().table("users").update({
            "password_hash":_hash(new_password,salt),"salt":salt
        }).eq("username",username.strip()).execute()
        return True,"Password updated—sign in with your new password."
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
    [data-testid="column"]:last-of-type{{padding:48px 42px!important;}}
    [data-testid="column"]:last-of-type label{{color:{C["med"]}!important;font-size:12.5px!important;font-weight:600!important;}}
    [data-testid="column"]:last-of-type input{{background:white!important;color:{C["text"]}!important;border:1.5px solid {C["sand3"]}!important;border-radius:5px!important;}}
    [data-testid="column"]:last-of-type .stButton>button{{background:white!important;color:{C["text"]}!important;border:1.5px solid {C["sand3"]}!important;border-radius:5px!important;font-weight:600!important;}}
    [data-testid="column"]:last-of-type .stButton>button:hover{{background:{C["green"]}!important;color:white!important;border-color:{C["green"]}!important;}}
    .auth-ey{{font-family:'DM Mono',monospace;font-size:9.5px;letter-spacing:3px;text-transform:uppercase;color:{C["mint"]};margin-bottom:14px;}}
    .auth-ttl{{font-family:'Cormorant Garamond',serif;font-size:2.4rem;font-weight:700;color:{C["text"]};letter-spacing:-.02em;line-height:1.1;margin-bottom:8px;}}
    .auth-sub{{font-size:13px;color:{C["muted"]};line-height:1.75;margin-bottom:32px;}}
    .auth-ftr{{margin-top:24px;padding-top:16px;border-top:1px solid {C["sand3"]};font-size:11px;color:{C["muted"]};font-family:'DM Mono',monospace;display:flex;align-items:center;gap:8px;}}
    </style>""", unsafe_allow_html=True)

    lc, rc = st.columns([0.9, 1.1])
    with lc:
        components.html(f"""<!DOCTYPE html><html><head>
        <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,700;1,700&family=DM+Sans:wght@400;600&family=DM+Mono:wght@400&display=swap" rel="stylesheet">
        <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        body{{background:#93a445;
             min-height:100vh;padding:52px;display:flex;flex-direction:column;
             justify-content:space-between;position:relative;overflow:hidden;font-family:'DM Sans',sans-serif;}}
        body::before{{content:'';position:absolute;inset:0;
             background-image:radial-gradient(circle at 1px 1px,rgba(255,255,255,.06) 1px,transparent 0);
             background-size:28px 28px;}}
        body::after{{content:'';position:absolute;bottom:-160px;right:-160px;width:500px;height:500px;
             background:radial-gradient(circle,rgba(255,255,255,.08) 0%,transparent 65%);border-radius:50%;}}
        .brand{{display:flex;align-items:center;gap:14px;position:relative;z-index:2;}}
        .brand img{{height:40px;opacity:.9;}}
        .bn{{font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:700;color:rgba(255,255,255,.88);line-height:1.25;}}
        .bs{{font-family:'DM Mono',monospace;font-size:8px;color:rgba(255,255,255,.3);letter-spacing:2.5px;text-transform:uppercase;margin-top:3px;}}
        .hero{{flex:1;display:flex;flex-direction:column;justify-content:center;padding:44px 0 36px;position:relative;z-index:2;}}
        .ey{{display:flex;align-items:center;gap:12px;margin-bottom:20px;}}
        .eyl{{width:36px;height:1px;background:rgba(255,255,255,.6);}}
        .eyt{{font-family:'DM Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;color:rgba(255,255,255,.8);}}
        h1{{font-family:'Cormorant Garamond',serif;font-size:3.4rem;font-weight:700;line-height:1.06;color:white;letter-spacing:-.03em;margin-bottom:20px;}}
        h1 em{{font-style:italic;color:white;}}
        .desc{{font-size:14px;color:rgba(255,255,255,.45);line-height:1.85;max-width:380px;margin-bottom:40px;}}
        .stats{{display:flex;gap:0;}}
        .st{{padding:0 28px 0 0;}}
        .st:first-child{{padding-left:0;}}
        .st+.st{{border-left:1px solid rgba(255,255,255,.1);padding-left:28px;}}
        .sv{{font-family:'Cormorant Garamond',serif;font-size:1.9rem;font-weight:700;color:white;line-height:1;}}
        .sl{{font-family:'DM Mono',monospace;font-size:9px;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:1.5px;margin-top:5px;}}
        .foot{{position:relative;z-index:2;font-family:'DM Mono',monospace;font-size:10px;color:rgba(255,255,255,.2);line-height:1.9;}}
        </style></head><body>
        <div class="brand"><img src="{LOGO_W}"><div><div class="bn">Sonoran Institute</div><div class="bs">{L("Santa Cruz River Program")}</div></div></div>
        <div class="hero">
          <div class="ey"><div class="eyl"></div><div class="eyt">{L("Tucson, Arizona")}</div></div>
          <h1>{L("Santa Cruz River")}<br><em>{L("Trash Survey")}</em></h1>
          <div class="desc">{L("Longitudinal monitoring of litter and debris along the Santa Cruz River corridor and tributaries. Plot-based surveys across multiple sites and reaches.")}</div>
          <div class="stats">
            <div class="st"><div class="sv">395+</div><div class="sl">{L("Plot Records")}</div></div>
          </div>
        </div>
        <div class="foot">{L("Program Director")}: Luke Cole<br>sonoraninstitute.org</div>
        </body></html>""", height=900, scrolling=False)

    with rc:
        st.markdown(f"""<div class="auth-ey">{L("Authorized Personnel Only")}</div>
        <div class="auth-ttl">{L("Sign in to\nyour account").replace(chr(10),"<br>")}</div>
        <div class="auth-sub">{L("Access the Santa Cruz River data dashboard,<br>field entry tools, and analysis reports.")}</div>""", unsafe_allow_html=True)
        t1,t2,t3,t4,t5 = st.tabs([L("Sign In"),L("Create Account"),L("Forgot Password"),L("Look Up Username"), T("vol_tab")])

        with t1:
            with st.form("_login"):
                un=st.text_input(L("Username")); pw=st.text_input(L("Password"),type="password")
                st.markdown("<div style='height:6px'></div>",unsafe_allow_html=True)
                if st.form_submit_button(L("Sign In"),use_container_width=True):
                    ok,prof=login(un,pw)
                    if ok: st.session_state["auth"]=True; st.session_state["prof"]=prof; st.rerun()
                    else: st.error("Invalid username or password. Use the Forgot Password tab if needed.")

        with t2:
            st.markdown(f'<div style="font-size:12px;color:{C["muted"]};margin-bottom:12px;padding:10px 12px;background:{C["sand"]};border-radius:6px;border:1px solid {C["sand3"]};">{L("Your username is how you sign in. Write it down—there is no way to look it up later. Choose something simple like your first name or initials.")}</div>', unsafe_allow_html=True)
            with st.form("_reg"):
                c1,c2=st.columns(2)
                fn=c1.text_input("Full Name"); pos=c2.text_input("Position / Title")
                nu=st.text_input("Username (min 3 characters—write this down)")
                c3,c4=st.columns(2)
                p1=c3.text_input("Password (min 6 characters)",type="password")
                p2=c4.text_input("Confirm Password",type="password")
                st.markdown("<div style='height:4px'></div>",unsafe_allow_html=True)
                sq=st.selectbox(L("Security question (for password reset)"),[L("— Select one —")]+SECURITY_QUESTIONS)
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

        with t4:
            st.markdown(f'<div style="font-size:13px;color:{C["muted"]};margin-bottom:16px;line-height:1.7;">If you remember your full name and security answer but forgot your username, enter them below. Your username will be shown if they match.</div>', unsafe_allow_html=True)
            with st.form("_lookup"):
                lu_name = st.text_input("Your full name (as entered when you created your account)")
                lu_ans  = st.text_input("Your security question answer")
                if st.form_submit_button("Find My Username", use_container_width=True):
                    if not lu_name.strip():
                        st.error("Please enter your full name.")
                    elif not lu_ans.strip():
                        st.error("Please enter your security answer.")
                    else:
                        found = get_username_by_fullname(lu_name, lu_ans)
                        if found:
                            st.success(f"Your username is: **{found}**")
                        else:
                            st.error("No account found matching that name and security answer. Names are case-sensitive. Try your full name exactly as you typed it when registering.")
            st.markdown(f'<div style="font-size:12px;color:{C["muted"]};margin-top:12px;line-height:1.7;padding:10px 12px;background:{C["sand"]};border-radius:6px;">Note: Email-based password reset is not available. This dashboard runs without an email service. The security question system is the recovery method. If you are completely locked out, contact Kevin Robles to reset your account manually in Supabase.</div>', unsafe_allow_html=True)

        with t5:
            # Language toggle buttons for volunteers
            _vl1, _vl2 = st.columns(2)
            with _vl1:
                if st.button('🇺🇸  English', key='_vol_en', use_container_width=True):
                    st.session_state['lang']='en'; st.rerun()
            with _vl2:
                if st.button('🇲🇽  Español', key='_vol_es', use_container_width=True):
                    st.session_state['lang']='es'; st.rerun()
            st.markdown(f'<div style="font-size:11px;color:{C["muted"]};text-align:center;margin:4px 0 14px;font-family:DM Mono,monospace;">{T("vol_lang_prompt")}</div>', unsafe_allow_html=True)

            st.markdown(f'<div style="background:{C["green"]}0f;border:1px solid {C["green"]}30;border-radius:8px;padding:16px 18px;margin-bottom:16px;line-height:1.75;font-size:13px;"><strong style="color:{C["green"]};">{T("vol_welcome")}</strong><br>{T("vol_welcome_sub")}</div>', unsafe_allow_html=True)
            with st.form('_vol'):
                vc1,vc2 = st.columns(2)
                v_name  = vc1.text_input(T('vol_fullname'), placeholder='e.g. Maria Garcia / María García')
                v_org   = vc2.text_input(T('vol_org'), placeholder='e.g. Tucson Audubon, UA Service Day')
                vc3,vc4 = st.columns(2)
                v_phone = vc3.text_input(T('vol_contact'), placeholder='In case we need to follow up')
                v_exp   = vc4.selectbox(T('vol_exp'), T('vol_exp_opts'))
                v_how   = st.text_input(T('vol_how'), placeholder='e.g. Sonoran Institute newsletter, UA class, friend')
                v_note  = st.text_area(T('vol_notes'), height=70, placeholder=T('vol_notes_ph'))
                st.markdown(f'<div style="font-size:11px;color:{C["muted"]};margin-top:8px;line-height:1.6;">{T("vol_disclaimer")}</div>', unsafe_allow_html=True)
                if st.form_submit_button(T('vol_start_btn'), use_container_width=True):
                    if not v_name.strip():
                        st.error(T('vol_name_required'))
                    else:
                        st.session_state['auth'] = True
                        st.session_state['prof'] = {
                            'user_id': None,
                            'username': 'volunteer',
                            'full_name': v_name.strip(),
                            'position_title': f"Voluntario/a · {v_org.strip()}" if v_org.strip() and st.session_state.get('lang')=='es' else (f"Volunteer · {v_org.strip()}" if v_org.strip() else 'Volunteer'),
                            'is_volunteer': True,
                            'volunteer_org': v_org.strip(),
                            'volunteer_exp': v_exp,
                            'volunteer_how': v_how.strip(),
                            'volunteer_notes': v_note.strip(),
                            'volunteer_contact': v_phone.strip(),
                        }
                        st.session_state['page'] = 'Data Entry'
                        st.rerun()


        # Language toggle—bottom of login panel
        st.markdown(f'<div style="margin-top:20px;padding-top:16px;border-top:1px solid {C["sand3"]};font-family:DM Mono,monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:{C["muted"]};margin-bottom:8px;">Language / Idioma</div>', unsafe_allow_html=True)
        _ll1, _ll2 = st.columns(2)
        with _ll1:
            if st.button("🇺🇸  English", key="_login_en", use_container_width=True,
                         type="primary" if st.session_state.get("lang","en")=="en" else "secondary"):
                st.session_state["lang"]="en"; st.rerun()
        with _ll2:
            if st.button("🇲🇽  Español", key="_login_es", use_container_width=True,
                         type="primary" if st.session_state.get("lang","en")=="es" else "secondary"):
                st.session_state["lang"]="es"; st.rerun()

        st.markdown(f"""<div class="auth-ftr"><span style="width:5px;height:5px;border-radius:50%;background:{C["mint"]};display:inline-block;"></span>Cloud database secured by Supabase · Passwords encrypted</div>""",unsafe_allow_html=True)
    st.stop()

# ──────────────────────────────────────────────────────────────────
# DATA LOADING
# ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    sb=get_sb()
    # ── PAGINATED FETCH—Supabase caps at 1,000 rows per call ──────
    # We must paginate to get ALL rows. .limit() alone is unreliable
    # across supabase-py versions. Pagination always works.
    def fetch_all(table, cols):
        rows=[]; offset=0; page=1000
        while True:
            batch=sb.table(table).select(cols).range(offset,offset+page-1).execute().data or []
            rows.extend(batch)
            if len(batch)<page: break
            offset+=page
        return rows

    tc=pd.DataFrame(fetch_all("trash_counts","event_id,trash_group,trash_item,count_value"))
    se=pd.DataFrame(fetch_all("site_events","*"))
    wt=pd.DataFrame(fetch_all("weights_data","event_id,date_recorded,total_weight_oz"))

    if tc.empty: tc=pd.DataFrame(columns=["event_id","trash_group","trash_item","count_value"])
    if se.empty: se=pd.DataFrame()
    if wt.empty: wt=pd.DataFrame(columns=["event_id","date_recorded","total_weight_oz"])

    # ── Load custom categories (added by staff via Data Entry) ──
    try:
        cc = pd.DataFrame(fetch_all("custom_categories","group_name,item_name,created_by,created_at"))
    except Exception:
        cc = pd.DataFrame(columns=["group_name","item_name","created_by","created_at"])

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
        L("Recyclable") if g in RECYCLABLE_GROUPS else L("Non-Recyclable"))
    tc["floatable"]=tc["trash_group"].map(lambda g:
        L("Floatable") if g in FLOATABLE_GROUPS else L("Non-Floatable"))
    tc["beverage"]=tc["trash_group"].isin(BEVERAGE_GROUPS)
    tc["health_hazard"]=tc["trash_group"].isin(HEALTH_HAZARD_GROUPS)
    tc["bulk_debris"]=tc["trash_group"].isin(BULK_DEBRIS_GROUPS)

    long=tc.copy()
    if not se.empty and not long.empty:
        cols=[c for c in ["event_id","date_site","site_label","point_id","replicate_no","lat","lon","recorder","surveyed_m2"] if c in se.columns]
        long=long.merge(se[cols],on="event_id",how="left")

    long["date"]=pd.to_datetime(long.get("date_site",pd.NaT),errors="coerce")
    long["site_label"]=long.get("site_label",pd.Series("Unknown",index=long.index)).fillna("Unknown")
    long["site_label"] = (
        long["site_label"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .replace({
            "NE Side of SCR at Tuboc Bridge": "NE Side of SCR at Tubac Bridge",
            "Tuboc Bridge": "Tubac Bridge",
            "Riverview and Navajo": "Navajo and Riverview",
            "Navajo and Riverview ": "Navajo and Riverview",
            "Santa Cruze River Park": "Santa Cruz River Park",
            "South of grant Bridge west of Freeway": "South of Grant Bridge west of Freeway",
            "drexel": "Drexel",
        })
    )
    long["lat"]=pd.to_numeric(long.get("lat",np.nan),errors="coerce") if "lat" in long.columns else np.nan
    long["lon"]=pd.to_numeric(long.get("lon",np.nan),errors="coerce") if "lon" in long.columns else np.nan

    # ── COORDINATE CORRECTIONS—verified against Excel Site sheet ──
    # These are confirmed data-entry errors found in the source data.
    # Zero coords (events 20,187,188,189): no GPS recorded—null out
    zero_mask = (long["lat"]==0.0) | (long["lon"]==0.0)
    long.loc[zero_mask, "lat"] = np.nan
    long.loc[zero_mask, "lon"] = np.nan
    # Event 78 (Riverview Blvd, West Freeway): lon -111.990556 → -110.990556 (off by 1 degree)
    if "event_id" in long.columns:
        m78 = long["event_id"].astype(str) == "78"
        long.loc[m78 & (long["lon"] < -111.5), "lon"] = -110.990556
        # Event 249 (Navajo and Riverview): lat 32.345760 → 32.245760 (off by 0.1 degree)
        m249 = long["event_id"].astype(str) == "249"
        long.loc[m249 & (long["lat"] > 32.3), "lat"] = 32.245760
        # Event 197 (St. Mary's and Riverside): lon -110.963360 → -110.985360 (typo)
        m197 = long["event_id"].astype(str) == "197"
        long.loc[m197 & (long["lon"] > -110.97) & (long["lon"] < -110.96), "lon"] = -110.985360
        # Event 334 (Near Verdugo Park): lat 32.110259 → 32.210259 (off by 0.1 degree)
        m334 = long["event_id"].astype(str) == "334"
        long.loc[m334 & (long["lat"] < 32.15), "lat"] = 32.210259
        # Event 15 (Santa Cruz): lon -110.080527 → -110.980527 (missing digit—all SCR sites ~-110.98x)
        m15 = long["event_id"].astype(str) == "15"
        long.loc[m15 & (long["lon"] > -110.5), "lon"] = -111.080527
    # ────────────────────────────────────────────────────────────────
    long["seg"] = [assign_segment(s, la, lo) for s, la, lo in zip(long["site_label"], long["lat"], long["lon"])]
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

    # Store custom categories in session state for runtime TRASH_GROUPS merge
    if not cc.empty:
        import streamlit as _st
        _st.session_state["_custom_cats_df"] = cc
    return long, se, wt

def make_et(df):
    if df.empty: return pd.DataFrame()
    g=[c for c in ["event_id","date","site_label","seg","surveyed_m2","lat","lon"] if c in df.columns]
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
def _norm_series_str(s):
    return s.fillna("").astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

def _triplicate_plot_meta(df):
    """
    Build one row per plot/event so triplicate sessions can be identified
    conservatively. Preferred session key is site + date + point_id when
    point_id exists. Fallback is site + date only.
    """
    base_cols = [c for c in ["event_id", "site_label", "date", "point_id", "replicate_no", "seg", "lat", "lon"] if c in df.columns]
    if df.empty or not {"event_id", "site_label", "date"}.issubset(df.columns):
        return pd.DataFrame(columns=["event_id","site_label","date","point_id_norm","replicate_norm","seg","lat","lon","session_key","has_point_id"])
    pm = df[base_cols].drop_duplicates("event_id").copy()
    pm["date"] = pd.to_datetime(pm["date"], errors="coerce").dt.normalize()
    pm = pm[pm["date"].notna()].copy()
    pm["site_label"] = _norm_series_str(pm["site_label"])
    pm["point_id_norm"] = _norm_series_str(pm["point_id"]) if "point_id" in pm.columns else ""
    if "replicate_no" in pm.columns:
        rep = pm["replicate_no"]
        rep_num = pd.to_numeric(rep, errors="coerce")
        pm["replicate_norm"] = np.where(rep_num.notna(), rep_num.astype("Int64").astype(str), _norm_series_str(rep))
        pm["replicate_norm"] = pd.Series(pm["replicate_norm"], index=pm.index).replace({"<NA>":"", "nan":"", "None":""})
    else:
        pm["replicate_norm"] = ""
    pm["has_point_id"] = pm["point_id_norm"].ne("")
    day_str = pm["date"].dt.strftime("%Y-%m-%d")
    pm["session_key"] = np.where(
        pm["has_point_id"],
        "PID::" + pm["site_label"] + "::" + day_str + "::" + pm["point_id_norm"],
        "SD::" + pm["site_label"] + "::" + day_str
    )
    return pm

def strict_triplicate_sessions(df):
    """
    Strict session table:
    - exactly 3 distinct plot/event records
    - one site
    - one date
    - if point_id exists, either 3 distinct replicate labels or replicate labels missing
    This is intentionally conservative.
    """
    pm = _triplicate_plot_meta(df)
    if pm.empty:
        return pd.DataFrame(columns=["session_key","site_label","date","n_plots","n_rep","has_point_id"])
    sess = pm.groupby("session_key", dropna=False).agg(
        site_label=("site_label","first"),
        date=("date","first"),
        n_plots=("event_id","nunique"),
        n_sites=("site_label","nunique"),
        n_dates=("date","nunique"),
        n_rep=("replicate_norm", lambda s: s[s.ne("")].nunique()),
        has_point_id=("has_point_id","max"),
    ).reset_index()
    keep = sess[
        (sess["n_plots"] == 3) &
        (sess["n_sites"] == 1) &
        (sess["n_dates"] == 1) &
        ((~sess["has_point_id"]) | (sess["n_rep"].isin([0, 3])))
    ].copy()
    return keep

def keep_exact_triplicate_sessions(df):
    """
    Keep only rows belonging to exact triplicate sessions.
    """
    if df.empty or "event_id" not in df.columns:
        return df.iloc[0:0].copy()
    keep = strict_triplicate_sessions(df)
    if keep.empty:
        return df.iloc[0:0].copy()
    pm = _triplicate_plot_meta(df)
    keep_ids = pm.loc[pm["session_key"].isin(keep["session_key"]), "event_id"].dropna().unique().tolist()
    out = df[df["event_id"].isin(keep_ids)].copy()
    return out

def build_site_stats_raw(df):
    """
    Raw plot-level site statistics. Every event/plot is kept as recorded.
    Use for descriptive viewing only.
    """
    if df.empty or "site_label" not in df.columns:
        return pd.DataFrame()
    df2 = df.copy()
    df2["n"] = pd.to_numeric(df2["n"], errors="coerce").fillna(0)
    ev_totals = df2.groupby(["site_label","event_id","seg"], dropna=False)["n"].sum().reset_index(name="plot_total")
    ss = ev_totals.groupby(["site_label","seg"], dropna=False).agg(
        n_plots=("plot_total","count"),
        mean=("plot_total","mean"),
        median=("plot_total","median"),
        sd=("plot_total","std"),
        total=("plot_total","sum"),
        min_v=("plot_total","min"),
        max_v=("plot_total","max")
    ).reset_index()
    ss["sd"] = ss["sd"].fillna(0)
    ss["se"] = ss["sd"] / np.sqrt(ss["n_plots"].replace(0, np.nan))
    ss["cv"] = np.where(ss["mean"] > 0, ss["sd"] / ss["mean"], np.nan)
    ss["range"] = ss["max_v"] - ss["min_v"]

    coords = df2.groupby("site_label", dropna=False).agg(lat=("lat","mean"), lon=("lon","mean")).reset_index()
    ss = ss.merge(coords, on="site_label", how="left")
    ss["lat_num"] = pd.to_numeric(ss["lat"], errors="coerce")
    ss_with = ss[ss["lat_num"].notna()].sort_values("lat_num", ascending=False).copy()
    ss_with["north_rank"] = range(1, len(ss_with)+1)
    ss_without = ss[ss["lat_num"].isna()].copy()
    ss_without["north_rank"] = np.nan
    ss = pd.concat([ss_with, ss_without], ignore_index=True)
    ss["site_display"] = ss.apply(
        lambda r: f"{int(r['north_rank'])}. {r['site_label']}" if pd.notna(r["north_rank"]) else r["site_label"],
        axis=1
    )
    ss = ss.sort_values(["north_rank","site_label"]).reset_index(drop=True)
    return ss

def build_site_stats_ns(df):
    """
    Strict site summary ordered North to South.
    Each exact triplicate session contributes one observation after the
    three plot totals are averaged into a session mean.
    """
    if df.empty or "site_label" not in df.columns:
        return pd.DataFrame()

    df2 = keep_exact_triplicate_sessions(df)
    if df2.empty:
        return pd.DataFrame()

    df2["n"] = pd.to_numeric(df2["n"], errors="coerce").fillna(0)
    pm = _triplicate_plot_meta(df2)[["event_id","session_key"]].copy()

    ev_totals = df2.groupby(["site_label","date","event_id","seg"], dropna=False)["n"].sum().reset_index(name="plot_total")
    ev_totals = ev_totals.merge(pm, on="event_id", how="left")

    sessions = ev_totals.groupby(["session_key","site_label","seg","date"], dropna=False).agg(
        n_session_plots=("event_id","nunique"),
        session_mean=("plot_total","mean"),
        session_raw_total=("plot_total","sum")
    ).reset_index()
    sessions = sessions[sessions["n_session_plots"] == 3].copy()

    ss = sessions.groupby(["site_label","seg"], dropna=False).agg(
        n_plots=("session_mean","count"),
        mean=("session_mean","mean"),
        median=("session_mean","median"),
        sd=("session_mean","std"),
        total=("session_raw_total","sum"),
        min_v=("session_mean","min"),
        max_v=("session_mean","max")
    ).reset_index()
    ss["sd"] = ss["sd"].fillna(0)
    ss["se"] = ss["sd"] / np.sqrt(ss["n_plots"].replace(0, np.nan))
    ss["cv"] = np.where(ss["mean"] > 0, ss["sd"] / ss["mean"], np.nan)
    ss["range"] = ss["max_v"] - ss["min_v"]

    coords = df2.groupby("site_label", dropna=False).agg(lat=("lat","mean"), lon=("lon","mean")).reset_index()
    ss = ss.merge(coords, on="site_label", how="left")

    ss["lat_num"] = pd.to_numeric(ss["lat"], errors="coerce")
    ss_with = ss[ss["lat_num"].notna()].sort_values("lat_num", ascending=False).copy()
    ss_with["north_rank"] = range(1, len(ss_with)+1)
    ss_without = ss[ss["lat_num"].isna()].copy()
    ss_without["north_rank"] = np.nan
    ss = pd.concat([ss_with, ss_without], ignore_index=True)

    ss["site_display"] = ss.apply(
        lambda r: f"{int(r['north_rank'])}. {r['site_label']}" if pd.notna(r["north_rank"]) else r["site_label"],
        axis=1
    )
    ss = ss.sort_values(["north_rank","site_label"]).reset_index(drop=True)
    return ss


def render_analysis_scope_selector(df, context_label=""):
    """Global page-level scope selector used across charts and tables."""
    options = [L("Strict triplicate sessions only"), L("All recorded plots")]
    default_opt = options[0] if st.session_state.get("analysis_scope_global", options[0]) == options[0] else options[1]
    choice = st.radio(
        L("Analysis scope"),
        options,
        index=0 if default_opt == options[0] else 1,
        horizontal=True,
        key="analysis_scope_global",
        label_visibility="collapsed",
    )
    strict_only = choice == options[0]
    scoped = keep_exact_triplicate_sessions(df) if strict_only else df.copy()

    total_events = int(df["event_id"].nunique()) if "event_id" in df.columns else 0
    scoped_events = int(scoped["event_id"].nunique()) if "event_id" in scoped.columns else 0
    total_sites = int(df["site_label"].nunique()) if "site_label" in df.columns else 0
    scoped_sites = int(scoped["site_label"].nunique()) if "site_label" in scoped.columns else 0
    total_items = int(pd.to_numeric(df["n"], errors="coerce").fillna(0).sum()) if "n" in df.columns and len(df) > 0 else 0
    scoped_items = int(pd.to_numeric(scoped["n"], errors="coerce").fillna(0).sum()) if "n" in scoped.columns and len(scoped) > 0 else 0
    total_sessions = len(strict_triplicate_sessions(df))
    dropped_events = max(total_events - scoped_events, 0)
    dropped_items = max(total_items - scoped_items, 0)

    if st.session_state.get("lang", "es") == "es":
        if strict_only:
            body = (
                f"<strong>Vista actual:</strong> solo sesiones triplicadas estrictas. "
                f"<br><br><strong>¿Qué es esto?</strong> aquí solo se usan días de muestreo donde el mismo sitio y la misma fecha tienen exactamente <strong>3 parcelas registradas</strong>. "
                f"Esas 3 parcelas se toman como un mismo conjunto comparable."
                f"<br><br><strong>¿Por qué importa?</strong> porque esta vista pone a los sitios bajo una estructura de muestreo más pareja. Eso ayuda mucho cuando se quiere comparar sitios, años o figuras para un reporte, una presentación o un paper."
                f"<br><br><strong>¿La basura sigue siendo real?</strong> sí. Los conteos siguen siendo reales. Lo que cambia aquí no es la basura, sino qué días de muestreo se dejan dentro de la comparación."
                f"<br><br><strong>Lo que sí entra ahora:</strong> {scoped_events:,} registros de parcelas, {total_sessions:,} sesiones triplicadas exactas, {scoped_sites:,} sitios y {scoped_items:,} artículos contados."
                f"<br><strong>Lo que queda fuera ahora:</strong> {dropped_events:,} registros de parcelas y {dropped_items:,} artículos contados de días con 1 parcela, 2 parcelas o más de 3 parcelas."
                f"<br><strong>Cuándo conviene usar esta vista:</strong> cuando quieres una comparación más limpia y más defendible."
            )
        else:
            body = (
                f"<strong>Vista actual:</strong> todas las parcelas registradas. "
                f"<br><br><strong>¿Qué es esto?</strong> aquí se usa todo lo que está en la base de datos, incluyendo días con 1 parcela, 2 parcelas, triplicados exactos y días con más parcelas."
                f"<br><br><strong>¿Por qué importa?</strong> porque esta vista enseña todo el archivo completo, pero mezcla distintos tipos de muestreo. Sirve para ver el panorama general, aunque no es la comparación más limpia entre sitios o fechas."
                f"<br><br><strong>Lo que se muestra ahora:</strong> {total_events:,} registros de parcelas, {total_sites:,} sitios y {total_items:,} artículos contados."
                f"<br><strong>Dentro de esta base completa hay:</strong> {total_sessions:,} sesiones triplicadas exactas."
                f"<br><strong>Cuándo conviene usar esta vista:</strong> cuando quieres ver todo lo que se ha registrado, sin filtrar por estructura de muestreo."
            )
        helper = "<strong>Por qué algunas figuras todavía pueden parecerse:</strong> a veces los mismos tipos de basura siguen arriba en ambas vistas. Eso no significa que el cambio falló. Solo significa que el patrón general se mantuvo parecido aunque cambió qué filas entran al análisis."
    else:
        if strict_only:
            body = (
                f"<strong>Current view:</strong> strict triplicate sessions only. "
                f"<br><br><strong>What is this?</strong> this page only keeps survey days where the same site and the same date have exactly <strong>3 plot records</strong>. Those 3 plots are treated as one comparable set."
                f"<br><br><strong>Why is this important?</strong> because it puts sites on a more even sampling structure. That makes comparisons easier to defend in a report, presentation, or paper."
                f"<br><br><strong>Are the trash counts still real?</strong> yes. The counts are still real. What changes here is which sampling days are included in the comparison."
                f"<br><br><strong>Included right now:</strong> {scoped_events:,} plot records, {total_sessions:,} exact triplicate sessions, {scoped_sites:,} sites, and {scoped_items:,} counted items."
                f"<br><strong>Left out right now:</strong> {dropped_events:,} plot records and {dropped_items:,} counted items from days with 1 plot, 2 plots, or more than 3 plots."
            )
        else:
            body = (
                f"<strong>Current view:</strong> all recorded plots. "
                f"<br><br><strong>What is this?</strong> this page uses the full database, including single plots, doubles, exact triplicates, and larger multi-plot days."
                f"<br><br><strong>Why is this important?</strong> because it shows the whole record, but it mixes different sampling setups together."
                f"<br><br><strong>Shown right now:</strong> {total_events:,} plot records, {total_sites:,} sites, and {total_items:,} counted items."
            )
        helper = "<strong>Why some charts may still look similar:</strong> the same kinds of trash can still stay near the top in both views. That does not mean the toggle failed."

    st.markdown(
        f"""<div style="background:white;border:1px solid {C['sand3']};border-left:4px solid {C['water']};
        border-radius:0 10px 10px 0;padding:20px 24px;margin:0 0 18px;font-size:13.5px;line-height:1.9;color:{C['text']};">
        <div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:{C['muted']};margin-bottom:10px;">{L('Analysis scope')}</div>
        {body}
        </div>""",
        unsafe_allow_html=True
    )
    st.markdown(
        f"""<div style="margin:-2px 0 18px 2px;font-size:12.5px;line-height:1.82;color:{C['muted']};">{helper}</div>""",
        unsafe_allow_html=True
    )
    if strict_only and scoped.empty:
        st.warning(L("No exact triplicate sessions are available under the current filters or page scope."))
    return scoped, strict_only


def fig_note(what, why, read, extra=""):
    extra_html = f'<p style="color:{C["muted"]};margin:4px 0;font-size:13px;"><strong>{L("Additional context")}:</strong> {L(extra)}</p>' if extra else ""
    st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["green"]};
    border-radius:0 8px 8px 0;padding:20px 24px;margin:16px 0 28px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
    <div style="font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:600;color:{C["green"]};margin-bottom:10px;">{L("How to read this figure")}</div>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>{L("What it shows")}:</strong> {L(what)}</p>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>{L("Why it matters")}:</strong> {L(why)}</p>
    <p style="margin:4px 0;font-size:13.5px;color:{C["text"]};"><strong>{L("How to interpret it")}:</strong> {L(read)}</p>
    {extra_html}
    </div>""", unsafe_allow_html=True)

def last_updated_insight(df, chart_type="general", site=None, category=None):
    if df is None or df.empty or "date" not in df.columns: return
    latest = df["date"].dropna().max()
    if pd.isna(latest): return
    as_of = fmt_month_year_local(latest)
    total = int(df["n"].sum()) if "n" in df.columns else 0
    es = st.session_state.get("lang", "es") == "es"

    if chart_type == "monthly":
        recent = df[df["date"].dt.year == latest.year]
        yr_total = int(recent["n"].sum()) if "n" in recent.columns else 0
        msg = f"Hasta <strong>{as_of}</strong>, se han registrado <strong>{yr_total:,}</strong> artículos en {latest.year}." if es else f"As of <strong>{as_of}</strong>, a total of <strong>{yr_total:,}</strong> items have been recorded in {latest.year}."
    elif chart_type == "site" and site:
        site_df = df[df["site_label"]==site] if "site_label" in df.columns else df
        site_total = int(site_df["n"].sum()) if "n" in site_df.columns else 0
        site_mean = site_df.groupby("event_id")["n"].sum().mean() if "event_id" in site_df.columns else 0
        msg = f"Hasta <strong>{as_of}</strong>, <strong>{site}</strong> registra <strong>{site_total:,}</strong> artículos totales y un promedio de <strong>{site_mean:.1f}</strong> por evento." if es else f"As of <strong>{as_of}</strong>, <strong>{site}</strong> has recorded <strong>{site_total:,}</strong> total items, with a mean of <strong>{site_mean:.1f}</strong> items per event."
    elif chart_type == "category" and category:
        cat_df = df[df["trash_group"]==category] if "trash_group" in df.columns else df
        cat_total = int(cat_df["n"].sum()) if "n" in cat_df.columns else 0
        share = 100*cat_total/max(total,1)
        msg = f"Hasta <strong>{as_of}</strong>, la categoría <strong>{L(category)}</strong> suma <strong>{cat_total:,}</strong> artículos, es decir <strong>{share:.1f}%</strong> del total mostrado." if es else f"As of <strong>{as_of}</strong>, the category <strong>{category}</strong> accounts for <strong>{cat_total:,}</strong> items, or <strong>{share:.1f}%</strong> of the total shown."
    else:
        msg = f"Hasta <strong>{as_of}</strong>, la vista actual incluye <strong>{total:,}</strong> artículos contados." if es else f"As of <strong>{as_of}</strong>, the current view includes <strong>{total:,}</strong> counted items."
    st.markdown(f'<div style="font-size:12.2px;color:{C["muted"]};line-height:1.8;margin:4px 0 18px;">{msg}</div>', unsafe_allow_html=True)

def cat_color_legend():
    """Universal category color guide—shown above every category table/chart."""
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;' +
        f'background:white;border:1px solid {C["sand3"]};border-radius:8px;' +
        f'padding:10px 16px;margin:10px 0 16px;font-size:12px;">' +
        f'<span style="font-weight:700;font-size:11px;font-family:DM Mono,monospace;' +
        f'text-transform:uppercase;letter-spacing:1px;color:{C["muted"]};margin-right:4px;">{L("Category Colors:")}</span>' +
        f'<span style="display:inline-flex;align-items:center;gap:5px;">' +
        f'<span style="width:11px;height:11px;border-radius:50%;background:{C["water"]};display:inline-block;"></span>' +
        f'<span style="color:{C["text"]};">{L("Recyclable")}</span> <span style="color:{C["muted"]};font-size:10px;">({L("City of Tucson standard")})</span></span>' +
        f'<span style="display:inline-flex;align-items:center;gap:5px;">' +
        f'<span style="width:11px;height:11px;border-radius:50%;background:{C["brick"]};display:inline-block;"></span>' +
        f'<span style="color:{C["text"]};">{L("Health Hazard")}</span> <span style="color:{C["muted"]};font-size:10px;">({L("Rx, Drugs, Nicotine, Toiletries")})</span></span>' +
        f'<span style="display:inline-flex;align-items:center;gap:5px;">' +
        f'<span style="width:11px;height:11px;border-radius:50%;background:{C["amber"]};display:inline-block;"></span>' +
        f'<span style="color:{C["text"]};">{L("Floatable")}</span> <span style="color:{C["muted"]};font-size:10px;">({L("river health / ADEQ risk")})</span></span>' +
        f'<span style="display:inline-flex;align-items:center;gap:5px;">' +
        f'<span style="width:11px;height:11px;border-radius:50%;background:{C["green"]};display:inline-block;"></span>' +
        f'<span style="color:{C["text"]};">{L("Other Non-Recyclable")}</span></span>' +
        '</div>',
        unsafe_allow_html=True
    )

def color_legend(title="Trash Burden", mode="gradient"):
    """Render a color legend below a map or chart."""
    title_disp = L(title)
    if mode == "gradient":
        st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;
        padding:14px 18px;margin:10px 0;display:inline-flex;align-items:center;gap:16px;
        font-size:12px;color:{C["muted"]};box-shadow:0 2px 6px rgba(0,0,0,.04);">
        <strong style="color:{C["text"]};font-size:12px;">{title_disp}:</strong>
        <div style="width:160px;height:10px;border-radius:4px;
        background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);"></div>
        <span>{L("Lower")}</span><span style="font-size:16px;">→</span><span>{L("Higher")}</span>
        </div>""", unsafe_allow_html=True)
    else:
        segs = [(L("North Reach"),"#2980b9"),(L("Central Reach"),"#27ae60"),(L("South Reach"),"#e67e22"),(L("Rillito"),"#8e44ad")]
        dots = "".join(f'<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px;"><span style="width:10px;height:10px;border-radius:50%;background:{c};display:inline-block;"></span>{s}</span>' for s,c in segs)
        st.markdown(f"""<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;
        padding:12px 18px;margin:10px 0;font-size:12px;color:{C["text"]};
        box-shadow:0 2px 6px rgba(0,0,0,.04);">
        <strong>{L("River Segments")}:</strong>&nbsp;&nbsp;{dots}
        </div>""", unsafe_allow_html=True)

def render_filters(df, kp="", cats=True):
    all_segs=[s for s in df["seg"].dropna().unique() if s!="Other"] if "seg" in df.columns else []
    all_segs=sorted(all_segs)
    all_sites=sorted(df["site_label"].dropna().unique()) if "site_label" in df.columns else []
    all_grps=sorted(df["trash_group"].dropna().unique()) if "trash_group" in df.columns else []
    mn,mx=df["date"].min(),df["date"].max()
    ncols=4 if cats else 3
    cols=st.columns(ncols)
    with cols[0]: sel_segs=st.multiselect(T("river_segment"),all_segs,default=all_segs,key=f"{kp}_segs")
    with cols[1]: sel_sites=st.multiselect(T("location"),all_sites,default=all_sites,key=f"{kp}_sites")
    if cats:
        with cols[2]: sel_grps=st.multiselect(T("category"),all_grps,default=all_grps,key=f"{kp}_grps")
    else: sel_grps=all_grps
    with cols[-1]:
        dr=st.date_input(T("date_range"),value=(mn.date(),mx.date()),key=f"{kp}_dr") if pd.notna(mn) and pd.notna(mx) else None
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
    <div class="stat-item"><span class="stat-v">{ni:,}</span><span class="stat-l">{T("items_in_view")}</span></div>
    <div class="stat-item"><span class="stat-v">{ne:,}</span><span class="stat-l">{T("events")}</span></div>
    <div class="stat-item"><span class="stat-v">{ns:,}</span><span class="stat-l">{T("locations")}</span></div>
    <div class="stat-item"><span class="stat-v">{pct:.0f}%</span><span class="stat-l">{T("of_all_data")}</span></div>
    </div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────
# MAP
# ──────────────────────────────────────────────────────────────────
def color_val(v,vmin,vmax):
    if pd.isna(v): return "#5b8bd9"
    import math
    if vmax==vmin: t=0.5
    else:
        log_v=math.log1p(float(v)-float(vmin));log_max=math.log1p(float(vmax)-float(vmin))
        t=max(0,min(1,log_v/log_max)) if log_max>0 else 0.5
    stops=[(0,(49,130,206)),(0.33,(78,201,176)),(0.66,(245,149,52)),(1,(214,69,65))]
    for i in range(len(stops)-1):
        t0,c0=stops[i]; t1,c1=stops[i+1]
        if t0<=t<=t1:
            f=(t-t0)/(t1-t0) if t1>t0 else 0
            return "#{:02x}{:02x}{:02x}".format(*[round(c0[j]+f*(c1[j]-c0[j])) for j in range(3)])
    return "#d64541"

def render_map(df,lat,lon,label_col,popup_cols,metric_col,seg_col=None,height=560):
    if df is None or len(df)==0:
        st.info(L("No coordinate data available."))
        return

    popup_labels = {
        "event_id": L("Event ID"),
        "site_label": L("Site Name"),
        "seg": L("River Segment"),
        "total": L("Total Items"),
        "events": L("# Events"),
        "avg_per_event": L("Avg Items/Event"),
        "date": L("Date"),
        "lat": L("Latitude"),
        "lon": L("Longitude")
    }

    d=df.copy()
    d[lat]=pd.to_numeric(d[lat],errors="coerce")
    d[lon]=pd.to_numeric(d[lon],errors="coerce")
    d=d[d[lat].notna()&d[lon].notna()]
    d=d[(d[lat]>31.5)&(d[lat]<33.0)&(d[lon]>-112.0)&(d[lon]<-110.0)]
    if len(d)==0:
        st.info(L("No valid GPS coordinates."))
        return

    vals=pd.to_numeric(d[metric_col],errors="coerce") if metric_col in d.columns else pd.Series([0]*len(d))
    vmin,vmax=float(vals.min()),float(vals.max())
    recs=[]
    for _,r in d.iterrows():
        popup_parts=[]
        for c in popup_cols:
            if c not in d.columns:
                continue
            label = popup_labels.get(c, L(str(c).replace("_"," ").strip().title()))
            value = r.get(c,'') or ''
            if c == "seg":
                value = L(str(value))
            popup_parts.append(f"<b>{html.escape(str(label))}</b>: {html.escape(str(value))}")
        popup="<br>".join(popup_parts)
        seg_value = str(r.get(seg_col,"Other")) if seg_col else None
        color=SEG_COLORS.get(seg_value,"#888") if seg_col else color_val(r.get(metric_col,np.nan),vmin,vmax)
        recs.append({"lat":float(r[lat]),"lon":float(r[lon]),"lbl":str(r.get(label_col,"")),"popup":popup,"color":color})

    clat,clon=float(d[lat].mean()),float(d[lon].mean())
    if seg_col:
        leg_html="".join(f'<div class="li"><div class="ld" style="background:{c}"></div>{html.escape(L(s))}</div>' for s,c in SEG_COLORS.items() if s!="Other")
    else:
        leg_html=f'<div style="width:130px;height:7px;border-radius:2px;background:linear-gradient(to right,#3182ce,#4ec9b0,#f59534,#d64541);margin-bottom:4px;"></div><div style="display:flex;justify-content:space-between;font-size:10px;color:#888;"><span>{html.escape(L("Low"))}</span><span>{html.escape(L("High"))}</span></div>'
    leg_title=L("River Segments") if seg_col else L("Trash Burden")

    html_src=f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>html,body,#map{{height:{height}px;width:100%;margin:0;padding:0;font-family:'DM Sans',sans-serif;}}
.legend{{position:absolute;bottom:18px;right:18px;z-index:9999;background:rgba(255,255,255,.97);
padding:13px 16px;border-radius:8px;border:1px solid #d4ccc0;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);}}
.lt{{font-weight:700;margin-bottom:9px;color:#93a445;font-size:10px;text-transform:uppercase;letter-spacing:.8px;}}
.li{{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px;}}
.ld{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
.leaflet-popup-content{{font-family:'DM Sans',sans-serif;font-size:13px;line-height:1.65;min-width:190px;}}
</style></head><body>
<div id="map"></div>
<div class="legend"><div class="lt">{html.escape(leg_title)}</div>{leg_html}</div>
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
if(bounds.length>1) map.fitBounds(bounds,{{padding:[40,40],maxZoom:14}});
</script></body></html>"""
    components.html(html_src, height=height+10)

# ──────────────────────────────────────────────────────────────────
# APP START
# ──────────────────────────────────────────────────────────────────
# ── Language init—must happen before anything renders ──
# Handle query params—lang switch and sign out
_qp_lang = st.query_params.get("lang", None)
_qp_so   = st.query_params.get("signout", None)
if _qp_so == "1":
    st.session_state["auth"] = False
    st.session_state["prof"] = None
    st.query_params.clear()
    st.rerun()
if _qp_lang in ("en", "es"):
    st.session_state["lang"] = _qp_lang
    try: st.query_params.pop("lang")
    except: pass
elif "lang" not in st.session_state:
    st.session_state["lang"] = "es"

inject_css()
auth_gate()
prof=st.session_state.get("prof") or {}

# HEADER—sign out sits inside header HTML, triggers hidden Streamlit button
_lang = st.session_state.get("lang","en")
_en_col  = "rgba(255,255,255,.9)"  if _lang=="en" else "rgba(255,255,255,.35)"
_es_col  = "rgba(255,255,255,.9)"  if _lang=="es" else "rgba(255,255,255,.35)"
_en_dec  = "underline" if _lang=="en" else "none"
_es_dec  = "underline" if _lang=="es" else "none"
_btn_sty = "font-family:DM Mono,monospace;font-size:8.5px;letter-spacing:1px;text-transform:uppercase;cursor:pointer;text-underline-offset:3px;text-decoration-color:rgba(255,255,255,.4);transition:color .15s;user-select:none;"
st.markdown(f"""<div class="hdr"><div class="hdr-in">
  <div class="hdr-brand">
    <img src="{LOGO_W}" class="hdr-logo">
    <div><div class="hdr-name">Santa Cruz River Trash Survey</div>
         <div class="hdr-sub">Santa Cruz River Program</div></div>
  </div>
  <div class="hdr-right">
    <div class="hdr-user">
      <strong>{prof.get('full_name','')}</strong>
      <span class="hdr-pos">{prof.get('position_title','')}</span>
      <div style="display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:4px;">
        <div class="hdr-pill"><span class="hdr-dot"></span>&nbsp;Live Database</div>
        <span onclick="(()=>{{var u=new URL(window.location.href);u.searchParams.set('lang','en');window.location.href=u.toString();}})()"
          style="{_btn_sty}color:{_en_col};text-decoration:{_en_dec};"
          onmouseover="this.style.color='rgba(255,255,255,.9)'"
          onmouseout="this.style.color='{_en_col}'">EN</span>
        <span style="color:rgba(255,255,255,.2);font-size:9px;">·</span>
        <span onclick="(()=>{{var u=new URL(window.location.href);u.searchParams.set('lang','es');window.location.href=u.toString();}})()"
          style="{_btn_sty}color:{_es_col};text-decoration:{_es_dec};"
          onmouseover="this.style.color='rgba(255,255,255,.9)'"
          onmouseout="this.style.color='{_es_col}'">ES</span>
        <span style="color:rgba(255,255,255,.2);font-size:9px;">·</span>
        <span onclick="(()=>{{var u=new URL(window.location.href);u.searchParams.set('signout','1');window.location.href=u.toString();}})()"
          style="{_btn_sty}color:rgba(255,255,255,.35);text-decoration:none;"
          onmouseover="this.style.color='rgba(255,255,255,.8)'"
          onmouseout="this.style.color='rgba(255,255,255,.35)'">Sign Out</span>
      </div>
    </div>
  </div>
</div></div>""", unsafe_allow_html=True)


# ── NAV BAR—native Streamlit radio, CSS-styled as a nav bar ──────
if "page" not in st.session_state: st.session_state["page"] = PAGES[0]

# The radio IS the nav—CSS removes dots and makes it look like tabs
st.markdown(f"""<style>
/* ── Nav wrapper ── */
div[data-testid="stHorizontalBlock"]:has(div[role="radiogroup"]) {{
    background:{C["forest"]} !important;
    position:sticky !important;
    top:0 !important;
    z-index:200 !important;
    border-bottom:none !important;
    margin-top:0 !important;
    box-shadow:0 0 0 20px {C["forest"]},0 3px 14px rgba(0,0,0,.35) !important;
    margin:0 !important;
    margin-top:0 !important;
    margin-bottom:0 !important;
    padding:0 !important;
    width:100% !important;
}}
/* Make the radiogroup fill the full width */
div[role="radiogroup"] {{
    display:flex !important;
    flex-wrap:nowrap !important;
    gap:0 !important;
    background:transparent !important;
    padding:0 96px !important;justify-content:flex-start !important;
    max-width:1360px !important;
    margin:0 auto !important;
    border:none !important;
    width:100% !important;
    box-sizing:border-box !important;
}}
/* Each option wrapper */
div[role="radiogroup"] > label {{
    display:flex !important;
    align-items:center !important;
    padding:10px 16px !important;
    font-family:'DM Sans',sans-serif !important;
    font-size:11px !important;
    font-weight:700 !important;
    letter-spacing:1.2px !important;
    text-transform:uppercase !important;
    color:rgba(255,255,255,.65) !important;
    border-bottom:3px solid transparent !important;
    cursor:pointer !important;
    white-space:nowrap !important;
    transition:color .15s,border-color .15s,background .15s !important;
    background:transparent !important;
    border-radius:0 !important;
    margin:0 !important;
    line-height:1 !important;
    min-height:0 !important;
}}
div[role="radiogroup"] > label:hover {{
    color:white !important;
    background:rgba(255,255,255,.06) !important;
    border-bottom-color:rgba(255,255,255,.3) !important;
}}
/* Selected / active tab */
div[role="radiogroup"] > label[data-baseweb="radio"]:has(input:checked),
div[role="radiogroup"] > label:has(input:checked) {{
    color:{C["mint"]} !important;
    border-bottom-color:{C["mint"]} !important;
    background:rgba(93,168,50,.08) !important;
}}
/* Hide the radio circle dot completely */
div[role="radiogroup"] > label > div:first-child {{
    display:none !important;
    width:0 !important;
    height:0 !important;
    margin:0 !important;
    padding:0 !important;
}}
div[role="radiogroup"] input[type="radio"] {{
    display:none !important;
}}
/* The text span inside label */
div[role="radiogroup"] > label > div:last-child {{
    margin:0 !important;
    padding:0 !important;
}}
div[role="radiogroup"] > label > div:last-child p {{
    font-family:'DM Sans',sans-serif !important;
    font-size:11px !important;
    font-weight:700 !important;
    letter-spacing:1.2px !important;
    text-transform:uppercase !important;
    margin:0 !important;
    color:inherit !important;
    line-height:1 !important;
}}
</style>""", unsafe_allow_html=True)

# Resolve page display names in current language
_page_labels = [T(p) for p in PAGES]
_cur_idx = PAGES.index(st.session_state["page"]) if st.session_state["page"] in PAGES else 0

_nav_choice = st.radio(
    "nav", _page_labels, index=_cur_idx,
    horizontal=True, label_visibility="collapsed", key="main_nav"
)
# Map label back to English page key
page = PAGES[_page_labels.index(_nav_choice)] if _nav_choice in _page_labels else PAGES[0]
st.session_state["page"] = page

# Language switching handled via URL query params (see lang init above)

# LOAD DATA
with st.spinner("Loading from database…"):
    try: long, se, wt = load_data()
    except Exception as e: st.error(f"Database error: {e}"); st.stop()

et = make_et(long)

# ── Merge custom categories from DB into TRASH_GROUPS for this session ──
# custom_cats is a DataFrame with group_name, item_name columns
try:
    _custom = st.session_state.get("_custom_cats_df", pd.DataFrame())
    if not _custom.empty:
        for _, row in _custom.iterrows():
            g, item = str(row["group_name"]).strip(), str(row["item_name"]).strip()
            if g and item:
                if g not in TRASH_GROUPS:
                    TRASH_GROUPS[g] = []
                if item not in TRASH_GROUPS[g]:
                    TRASH_GROUPS[g].append(item)
                # Also add to GROUP_ORDER if new
                if g not in GROUP_ORDER:
                    GROUP_ORDER.append(g)
except Exception:
    pass

# Cache the latest survey date globally—used by the "Data current as of" badge on every chart
try:
    _latest = long["date"].dropna().max() if "date" in long.columns else None
    if _latest is not None and not pd.isna(_latest):
        st.session_state["_db_latest_date"] = pd.Timestamp(_latest)
    else:
        st.session_state["_db_latest_date"] = ""
except Exception:
    st.session_state["_db_latest_date"] = ""

# ══════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════
if page == "Overview":
    page_banner(T("ov_ey"), T("ov_title"), T("ov_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Overview")
    with st.expander(T("filter_data"), expanded=False):
        lf = render_filters(scope_long, kp="ov")
    stat_strip(scope_long, lf)

    total_n=int(lf["n"].sum()); n_ev=lf["event_id"].nunique(); n_si=lf["site_label"].nunique()
    n_gr=lf["trash_group"].nunique()  # After query fix: should be 19
    d_min,d_max=lf["date"].min(),lf["date"].max()
    span=f"{d_min.strftime('%b %Y')} – {d_max.strftime('%b %Y')}" if pd.notna(d_min) and pd.notna(d_max) else "—"
    st.markdown(f"""<div class="kpi-grid">
    <div class="kpi"><div class="kpi-lbl">{T("kpi_items")}</div><div class="kpi-val">{total_n:,}</div><div class="kpi-note">{T("kpi_items_note")}</div></div>
    <div class="kpi"><div class="kpi-lbl">{T("kpi_events")}</div><div class="kpi-val">{n_ev:,}</div><div class="kpi-note">{T("kpi_events_note")}</div></div>
    <div class="kpi"><div class="kpi-lbl">{T("kpi_locs")}</div><div class="kpi-val">{n_si:,}</div><div class="kpi-note">{T("kpi_locs_note")}</div></div>
    <div class="kpi"><div class="kpi-lbl">{T("kpi_cats")}</div><div class="kpi-val">{n_gr}</div><div class="kpi-note">{T("kpi_cats_note")}</div></div>
    <div class="kpi"><div class="kpi-lbl">{T("kpi_period")}</div><div class="kpi-val sm">{span}</div><div class="kpi-note">{T("kpi_period_note")}</div></div>
    </div>""", unsafe_allow_html=True)

    c1,c2 = st.columns([3,2])
    with c1:
        card_open("Monthly Items Recorded Over Time",
                  "Green bars = survey conducted · Gray = no survey that month (trash still present—see note below) · Gold dashed line = 3-month rolling average")
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
        st.markdown(T("summer_note") if T("summer_note") != "summer_note" else '<div style="background:white;border:1px solid #e8a62044;border-left:4px solid #e8a620;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0 16px;font-size:13px;line-height:1.75;color:#18180f;"><strong>About gaps in the monthly record:</strong> Gray bars or missing months—especially June, July, and August—<strong>do not mean there was no trash</strong> on the river. They mean no survey was conducted that month. Survey coverage typically decreases in summer due to reduced student volunteer availability, high heat, and lower program capacity. Trash accumulates year-round regardless of whether surveys are conducted. Do not interpret survey gaps as evidence of cleaner river conditions.</div>', unsafe_allow_html=True)
        card_close()
    with c2:
        card_open("Share by Trash Category",
                  "Proportional breakdown of all items recorded across every category. Food Packaging, Clothing, and Misc typically dominate.")
        grp=lf.groupby("trash_group")["n"].sum().sort_values(ascending=False).reset_index()
        if len(grp)>0:
            fig=px.pie(grp,values="n",names="trash_group",hole=.44,color_discrete_sequence=PAL)
            fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=9.5,pull=[.04]+[0]*(len(grp)-1))
            fig.update_layout(height=300,paper_bgcolor="white",showlegend=False,margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"ov_pie")
        cat_color_legend()
        card_close()

    c3,c4 = st.columns([2,3])
    with c3:
        card_open("Top 15 Recorded Items",
                  "Most common items in the current view, ranked by total count across all kept records.")
        top=lf.groupby("trash_item")["n"].sum().nlargest(15).reset_index().sort_values("n")
        # Find which group each item belongs to (for classification color)
        item_to_group = {item: grp for grp, items in TRASH_GROUPS.items() for item in items}
        top["group"] = top["trash_item"].map(item_to_group).fillna("Misc")
        top["color"] = top["group"].map(lambda g:
            C["water"] if g in RECYCLABLE_GROUPS else
            C["brick"] if g in HEALTH_HAZARD_GROUPS else
            C["amber"] if g in FLOATABLE_GROUPS else C["green"])
        # Compute % of ALL items (not just top 15)
        grand_total = max(lf["n"].sum(), 1)
        top["pct"] = (100 * top["n"] / grand_total).round(1)
        top["label"] = [f"{int(v):,} ({p}%)" for v, p in zip(top["n"], top["pct"])]
        fig = go.Figure()
        for _, row in top.iterrows():
            fig.add_trace(go.Bar(
                x=[row["n"]], y=[row["trash_item"]], orientation="h",
                marker_color=row["color"], text=[row["label"]],
                textposition="outside", textfont=dict(size=10),
                showlegend=False, name=row["trash_item"]
            ))
        # Add right margin so labels don't clip
        fig.update_layout(
            height=460, paper_bgcolor="white", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=160, t=56, b=80),
            font=dict(family="DM Sans"),
            title=dict(text="Top 15 Items in the Current View", font=dict(
                family="Cormorant Garamond", size=15, color=C["text"]), x=0, xanchor="left"),
            xaxis=dict(title="Total Count", gridcolor=C["sand3"], gridwidth=1),
            yaxis=dict(title="", autorange=True),
            barmode="overlay"
        )
        show(fig,"ov_top")
        cat_color_legend()
        card_close()
    with c4:
        card_open("Trash by River Segment",
                  "Each bar shows how total items are distributed across trash categories within each mapped river segment in the current view.")
        if "seg" in lf.columns:
            sg=lf[lf["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            if len(sg) > 0:
                sg["seg"]=pd.Categorical(sg["seg"],SEG_ORDER,ordered=True); sg=sg.sort_values("seg")
                # Color each category by its environmental classification
                grp_color_map = {g:
                    C["water"] if g in RECYCLABLE_GROUPS else
                    C["brick"] if g in HEALTH_HAZARD_GROUPS else
                    C["amber"] if g in FLOATABLE_GROUPS else
                    C["green"] for g in sg["trash_group"].unique()}
                fig=px.bar(sg,x="seg",y="n",color="trash_group",barmode="stack",
                    color_discrete_map=grp_color_map,category_orders={"seg":SEG_ORDER})
                fig.update_layout(
                    legend=dict(orientation="h",yanchor="top",y=-0.16,xanchor="left",x=0,
                        font=dict(size=10,family="DM Sans"),title_text="Category",
                        bgcolor="rgba(255,255,255,.95)",bordercolor=C["divider"],borderwidth=1),
                    margin=dict(l=10,r=10,t=56,b=110))
                show(fig,"ov_seg")
            else:
                st.info(L("No river-segment data is available in the current scope for this figure."))
        card_close()

    section_title(T("why_title"))

    # Opening statement
    st.markdown(
        f'<p style="font-size:14px;color:{C["muted"]};line-height:1.85;margin:0 0 20px;' +
        f'font-style:italic;border-left:3px solid {C["mint"]};padding-left:16px;">' +
        T("why_sub")+
        "</p>",
        unsafe_allow_html=True
    )

    # 6 impact cards rendered with st.columns—works in Streamlit reliably
    _cards = [
        (C["forest"],  T("impact_reg_title"),    T("impact_reg")),
        (C["green"],   T("impact_grant_title"),  T("impact_grant")),
        (C["brick"],   T("impact_health_title"), T("impact_health")),
        (C["sage"],    T("impact_cleanup_title"),T("impact_cleanup")),
        (C["water"],   T("impact_policy_title"), T("impact_policy")),
        (C["earth"],   T("impact_refuge_title"), T("impact_refuge")),
    ]

    _ic1, _ic2, _ic3 = st.columns(3)
    for idx, (color, title, text) in enumerate(_cards):
        with [_ic1, _ic2, _ic3][idx % 3]:
            st.markdown(
                f'<div style="background:{C["sand"]};border-radius:10px;padding:18px 20px;' +
                f'border-top:3px solid {color};margin-bottom:16px;">' +
                f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:2px;' +
                f'text-transform:uppercase;color:{color};margin-bottom:8px;font-weight:700;">{title}</div>' +
                f'<div style="font-size:13px;color:{C["text"]};line-height:1.75;">{text}</div>' +
                '</div>',
                unsafe_allow_html=True
            )

    # Bottom callout bar
    _t1, _t2 = st.columns([1, 4])
    with _t1:
        st.markdown(
            f'<div style="background:linear-gradient(160deg,{C["forest"]},{C["green"]});' +
            f'border-radius:10px;padding:24px 20px;text-align:center;height:100%;' +
            f'display:flex;flex-direction:column;justify-content:center;">' +
            f'<div style="font-family:Cormorant Garamond,serif;font-size:3rem;font-weight:700;' +
            f'color:{C["mint"]};line-height:1;margin-bottom:6px;">32,144</div>' +
            f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:1.5px;' +
            f'text-transform:uppercase;color:rgba(255,255,255,.45);">items recorded</div>' +
            '</div>',
            unsafe_allow_html=True
        )
    with _t2:
        st.markdown(
            f'<div style="background:linear-gradient(160deg,{C["forest"]},{C["green"]});' +
            f'border-radius:10px;padding:24px 28px;height:100%;' +
            f'display:flex;flex-direction:column;justify-content:center;">' +
            f'<div style="font-size:14px;color:rgba(255,255,255,.78);line-height:1.85;">' +
            "Every item in this database was counted by hand, in the field, along the Santa Cruz River corridor "
            "— recorded by location, category, and date since September 2020. Four years of surveys "
            "across 136 sites. The numbers support permit compliance, grant applications, cleanup targeting, "
            "and the case for a Santa Cruz River Urban National Wildlife Refuge.</div></div>",
            unsafe_allow_html=True
        )

    section_title(T("cat_summary"))
    st.markdown('<div class="sec-sub">Total items, number of individual records, and average count per record for each trash category. Sorted by total count descending.</div>', unsafe_allow_html=True)
    cat_color_legend()
    summary=lf.groupby("trash_group")["n"].agg(Total="sum",Records="count",Average="mean").reset_index()
    summary["% of Total"]=(100*summary["Total"]/max(summary["Total"].sum(),1)).round(1)
    summary=summary.sort_values("Total",ascending=False).round(1).reset_index(drop=True)
    summary.index=range(1,len(summary)+1)
    summary.columns=[T("col_category"),T("col_total"),T("col_records"),T("col_avg"),T("col_pct")]
    st.dataframe(summary, use_container_width=True, height=380)
    tbl_note("Each row represents one trash category group. 'Records' = number of individual count entries in the database for that category. 'Avg per Record' = mean count per single data entry, not per survey event.")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# MAP
# ══════════════════════════════════════════════════════════════════
elif page == "Map":
    page_banner(T("map_ey"), T("map_title"), T("map_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Map")
    scope_et = make_et(scope_long)

    map_opt_seg = T("map_mode_seg")
    map_opt_burden = T("map_mode_burden")
    map_opt_events = L("Individual Events")
    map_mode = st.radio(
        T("map_mode_lbl") if T("map_mode_lbl")!="map_mode_lbl" else L("Map view"),
        [map_opt_seg, map_opt_burden, map_opt_events],
        horizontal=True
    )

    site_agg=scope_long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),lat=("lat","mean"),lon=("lon","mean")).reset_index()
    site_agg["avg_per_event"]=(site_agg["total"]/site_agg["events"]).round(1)
    wc=site_agg[site_agg["lat"].notna()&site_agg["lon"].notna()]

    m1,m2,m3,m4=st.columns(4)
    m1.metric(L("Sites with GPS"),len(wc))
    m2.metric(L("Total Sites in DB"),len(site_agg))
    m3.metric(L("Events Mapped"),int(wc["events"].sum()))
    m4.metric(L("Grand Avg Items/Site"),f"{site_agg['avg_per_event'].mean():.1f}" if len(site_agg)>0 else "—")

    if map_mode == map_opt_seg:
        render_map(wc,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total",seg_col="seg")
        color_legend("River Segment Colors", mode="segments")
    elif map_mode == map_opt_burden:
        render_map(wc,"lat","lon","site_label",["site_label","seg","total","events","avg_per_event"],"total")
        color_legend("Map Color = Trash Burden (Total Items)", mode="gradient")
    else:
        ev_geo=scope_et[scope_et["lat"].notna()&scope_et["lon"].notna()] if "lat" in scope_et.columns else pd.DataFrame()
        if len(ev_geo)>0:
            render_map(ev_geo,"lat","lon","site_label",["event_id","site_label","date","total"],"total",seg_col="seg")
        else:
            st.info(L("No individual event coordinates in database."))

    map_note = (
        f'{L("Map colors")}: <span style="color:#3182ce;font-weight:700;">{L("Blue")}</span> = {L("Low")}, ' 
        f'<span style="color:#f59534;font-weight:700;">{L("Orange")}</span>/' 
        f'<span style="color:#d64541;font-weight:700;">{L("Red")}</span> = {L("High")}. ' 
        f'{L("Click any circle to see site details and exact counts.")}'
        f'<br><br><strong>{L("How trash burden is calculated")}:</strong> ' 
        f'{L("Each site's color is determined by the total number of individual trash items recorded at that site across all survey events in the database. This is the sum of all 19 trash categories (food packaging, cups, clothing, nicotine products, construction debris, etc.) counted during every field visit to that location. Sites with more total items appear warmer (orange to red), while sites with fewer items appear cooler (blue to teal).")}'
        f'<br><br><strong>{L("Why logarithmic color scaling")}:</strong> ' 
        f'{L("A few high-count sites would compress all other sites into the same blue if a linear scale were used. Logarithmic spacing spreads the colors across the full range so differences among lower-count sites remain visible.")}'
        f'<br><br><strong>{L("What this metric represents")}:</strong> ' 
        f'{L("Cumulative litter load over time, not density per square meter or items per single visit. A site surveyed more often will naturally accumulate a higher total, so read this alongside the number of survey events shown in each popup.")}'
    )
    st.markdown(
        f'<div style="font-size:12.5px;color:{C["muted"]};padding:8px 14px;background:{C["sand"]};'
        f'border-radius:6px;margin:4px 0 12px;line-height:1.7;">{map_note}</div>',
        unsafe_allow_html=True
    )

    section_title(L("Sites with GPS Coordinates"))
    st.markdown(f'<div class="sec-sub">{L("All survey locations that have latitude/longitude data. Sorted by total items recorded descending.")}</div>', unsafe_allow_html=True)
    disp=wc[["site_label","seg","total","events","avg_per_event","lat","lon"]].copy()
    disp.columns=[L("Site Name"),L("River Segment"),L("Total Items"),L("# Events"),L("Avg Items/Event"),L("Latitude"),L("Longitude")]
    disp=disp.sort_values(L("Total Items"),ascending=False).round(2).reset_index(drop=True)
    disp.index=range(1,len(disp)+1)
    st.dataframe(disp, use_container_width=True, height=420)
    color_legend("Map Color = Trash Burden", mode="gradient")
    tbl_note(L("Latitude and longitude values are averaged from all records for that site. 'Avg Items/Event' = total items ÷ number of survey events at that location. Map circles: blue = lower trash burden, red = higher trash burden."))

    section_title(L("All Sites (Including Those Without GPS)"))
    st.markdown(f'<div class="sec-sub">{L("Complete list of all recorded locations in the database, with or without coordinates.")}</div>', unsafe_allow_html=True)
    all_sites_tbl=scope_long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique")).reset_index()
    all_sites_tbl["avg"]=(all_sites_tbl["total"]/all_sites_tbl["events"]).round(1)
    all_sites_tbl=all_sites_tbl.sort_values("total",ascending=False).reset_index(drop=True)
    all_sites_tbl.index=range(1,len(all_sites_tbl)+1)
    all_sites_tbl.columns=[L("Location"),L("River Segment"),L("Total Items"),L("# Events"),L("Avg Items/Event")]
    st.dataframe(all_sites_tbl, use_container_width=True, height=480)
    tbl_note(f"{L('Showing')} {len(all_sites_tbl)} {L("unique location names in the current analysis scope. Many may have slight spelling variations (e.g. 'Drexel and Irvington' vs 'Drexel and irvington') which cause them to appear as separate entries.")}")
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TRENDS
# ══════════════════════════════════════════════════════════════════
elif page == "Trends":
    page_banner(T("tr_ey"), T("tr_title"), T("tr_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Trends")
    with st.expander(T("filter_data"), expanded=False):
        lf=render_filters(scope_long, kp="tr", cats=False)
    stat_strip(scope_long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)

    TREND_FIGS = {
        "Monthly Item Count: Full Record": {
            "desc": "Total recorded trash items by calendar month. Green bars = survey conducted. Gray bars = no survey that month. Gold dashed line = 3-month rolling average.",
            "why": "Best figure for seeing the overall timeline of the program and identifying gaps in survey coverage.",
        },
        "Annual Totals by Year": {
            "desc": "Total items recorded within each calendar year, with exact counts labeled above each bar.",
            "why": "Useful for annual reporting and comparing year-over-year changes in overall burden.",
        },
        "Month by Month Comparison Across Years": {
            "desc": "Same calendar months compared across different survey years. Each color = one year.",
            "why": "Reveals seasonal patterns and whether a particular month is consistently heavy or light.",
        },
        "Average Items Per Survey Event Over Time": {
            "desc": "Monthly mean of total items per field visit. Dotted line = grand mean across the full record.",
            "why": "Adjusts for varying survey frequency—fairer than raw totals when the number of events per month changes.",
        },
        "Items by River Segment (Quarterly)": {
            "desc": "Quarterly item totals for each named river segment. Each color = one segment.",
            "why": "Shows whether segments are tracking together or whether certain reaches are getting heavier or lighter over time.",
        },
        "Weight of Trash Collected Over Time": {
            "desc": "Monthly total weight (oz) for events where weight data was recorded. Not all events have weight data.",
            "why": "Provides a physical mass perspective on the litter burden, complementing the item count view.",
        },
    }

    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:{C["muted"]};margin-bottom:4px;">↓ {L("Choose chart")}</div>', unsafe_allow_html=True)
    _trend_map = {L(k): k for k in TREND_FIGS.keys()}
    sel_trend_disp = st.selectbox(L("Select a figure to display"), list(_trend_map.keys()), key="trend_sel", label_visibility="collapsed")
    sel_trend = _trend_map[sel_trend_disp]

    # Description card
    fd = TREND_FIGS[sel_trend]
    st.markdown(f'<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["water"]};border-radius:0 8px 8px 0;padding:14px 20px;margin:12px 0 20px;"><div style="font-weight:700;font-size:14px;color:{C["text"]};margin-bottom:4px;">{L(sel_trend)}</div><p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>{L("What it shows")}:</strong> {L(fd["desc"])}</p><p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>{L("Why useful")}:</strong> {L(fd["why"])}</p></div>', unsafe_allow_html=True)

    if sel_trend == "Monthly Item Count: Full Record":
        ts=df.dropna(subset=["date"]).groupby(pd.Grouper(key="date",freq="MS"))["n"].sum().reset_index()
        full=pd.date_range(ts["date"].min(),ts["date"].max(),freq="MS")
        ts=ts.set_index("date").reindex(full).reset_index().rename(columns={"index":"date"})
        ts["gap"]=ts["n"].isna(); ts["n"]=ts["n"].fillna(0); ts["roll"]=ts["n"].rolling(3,min_periods=1).mean()
        fig=go.Figure()
        fig.add_bar(x=ts["date"],y=ts["n"],marker_color=[C["sand3"] if g else C["green"] for g in ts["gap"]],name="Monthly")
        fig.add_scatter(x=ts["date"],y=ts["roll"],name="3-Mo Rolling Avg",line=dict(color=C["amber"],width=2.5,dash="dot"),mode="lines")
        fb(fig,"Month","Total Items",h=460,title="Monthly Item Count: Full Survey Record"); show(fig,"tr_ts")
        last_updated_insight(df, chart_type="monthly")
        fig_note("Total recorded trash items by calendar month across all sites and categories.",
            "Best figure for seeing the broad timeline—peaks, gaps, and overall direction.",
            "Green bars = survey conducted. Gray = no survey that month. Gold line = 3-month rolling average.",
            "Gray bars do not mean zero trash—they mean no survey. Rolling average treats gaps as zero.")
        st.markdown(T("summer_note") if T("summer_note") != "summer_note" else '<div style="background:white;border:1px solid #e8a62044;border-left:4px solid #e8a620;border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0 16px;font-size:13px;line-height:1.75;color:#18180f;"><strong>About gaps in the monthly record:</strong> Gray bars or missing months—especially June, July, and August—<strong>do not mean there was no trash</strong> on the river. They mean no survey was conducted that month. Survey coverage typically decreases in summer due to reduced student volunteer availability, high heat, and lower program capacity. Trash accumulates year-round regardless of whether surveys are conducted. Do not interpret survey gaps as evidence of cleaner river conditions.</div>', unsafe_allow_html=True)

    elif sel_trend == "Annual Totals by Year":
        yr=df.dropna(subset=["year"]).groupby("year")["n"].sum().reset_index(); yr["year"]=yr["year"].astype(str)
        fig=px.bar(yr,x="year",y="n",color_discrete_sequence=[C["green"]],text="n")
        fig.update_traces(texttemplate="%{text:,}",textposition="outside")
        fb(fig,"Year","Total Items",h=420,title="Annual Totals by Survey Year"); show(fig,"tr_yr")
        last_updated_insight(df, chart_type="annual")
        fig_note("Total items across all events within each calendar year.",
            "Useful for year-over-year reporting.",
            "Taller bars = more total recorded items in that year.",
            "Annual totals reflect both trash burden and survey effort—years with more events may show higher counts.")

    elif sel_trend == "Month by Month Comparison Across Years":
        md=df.dropna(subset=["year","month"]).groupby(["year","month","month_name"],observed=False)["n"].sum().reset_index()
        md["year_str"]=md["year"].astype(int).astype(str)
        fig=px.bar(md,x="month_name",y="n",color="year_str",barmode="group",
            category_orders={"month_name":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]},
            color_discrete_sequence=PAL)
        fb(fig,"Month","Total Items",h=460,title="Month by Month Comparison Across Years"); show(fig,"tr_mby")
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
            fb(fig,"Month","Avg Items / Event",h=420,title="Average Items Per Survey Event (Monthly)"); show(fig,"tr_avg")
            last_updated_insight(df, chart_type="general")
            fig_note("Monthly mean of total items per field visit across all sites.",
                "More interpretable than raw totals when survey frequency varies between months.",
                "Points above the dotted line = heavier-than-average months.",
                "Grand mean = average across all months in the full record.")
        else: st.info(L("No event-level data available."))

    elif sel_trend == "Items by River Segment (Quarterly)":
        if "seg" in df.columns:
            sg=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(sg,x="date",y="n",color="seg",markers=True,color_discrete_map=SEG_COLORS)
            fb(fig,"Quarter","Items",h=420,title="Items by River Segment (Quarterly)"); show(fig,"tr_seg")
            color_legend("Segment Colors", mode="segments")
            last_updated_insight(df, chart_type="general")
            fig_note("Quarterly totals split by named river segment.",
                "Reveals whether segments track together or diverge over time.",
                "Each line = one segment. Rising = more trash in that reach. Crossing lines = relative burden shifting.",
                "Only sites with assigned segment labels are included.")
        else: st.info(L("No segment data available."))

    elif sel_trend == "Weight of Trash Collected Over Time":
        if not wt.empty and "weight_oz" in wt.columns:
            dated=wt.dropna(subset=["weight_oz","date"])
            if len(dated)>0:
                wtrend=dated.groupby(pd.Grouper(key="date",freq="MS"))["weight_oz"].sum().reset_index()
                fig=px.bar(wtrend,x="date",y="weight_oz",color_discrete_sequence=[C["earth"]])
                fb(fig,"Month","Weight (oz)",h=420,title="Weight of Trash Collected (Monthly)"); show(fig,"tr_wt")
                last_updated_insight(wt.rename(columns={"weight_oz":"n"}), chart_type="monthly")
                fig_note("Monthly total weight of trash collected (ounces).",
                    "Provides a physical mass perspective complementing the item count view.",
                    "Taller bars = more weight collected that month.",
                    "Not all survey events have weight data. Months with no bar may have item counts but no weight record.")
        else: st.info(L("No weight data in the database."))

    section_title("Annual Summary Table")
    st.markdown(f'<div class="sec-sub">{L("Total items, number of events, and average items per event by calendar year. Sorted most recent first.")}</div>', unsafe_allow_html=True)
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
    st.markdown(f'<div class="sec-sub">{L("Total items by calendar month across all years combined.")}</div>', unsafe_allow_html=True)
    mon=df.dropna(subset=["month_name"]).groupby("month_name",observed=False)["n"].agg(total="sum",records="count").reset_index()
    mon.columns=["Month","Total Items","# Records"]
    st.dataframe(mon, use_container_width=True, height=280)
    tbl_note("Months with low totals may reflect fewer surveys, not less trash. Do not interpret as evidence of cleaner months without checking survey coverage.")
    st.markdown('</div>', unsafe_allow_html=True)

elif page == "Categories":
    page_banner(T("cat_ey"), T("cat_title"), T("cat_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Categories")
    with st.expander(T("filter_data"), expanded=False):
        lf=render_filters(scope_long, kp="cat")
    stat_strip(scope_long,lf)

    df=lf.copy(); df["n"]=pd.to_numeric(df["n"],errors="coerce").fillna(0)

    # Interactive category toggle—lets user remove categories like Data Table
    all_cats_available = sorted(df["trash_group"].dropna().unique().tolist())
    with st.expander(L("Toggle Categories (include/exclude from all figures)"), expanded=False):
        sel_cats = st.multiselect(
            L("Categories to include in figures"),
            options=all_cats_available,
            default=all_cats_available,
            key="cat_toggle"
        )
        if sel_cats != all_cats_available:
            st.caption(f"Mostrando {len(sel_cats)} de {len(all_cats_available)} categorías." if st.session_state.get("lang","es")=="es" else f"Showing {len(sel_cats)} of {len(all_cats_available)} categories.")
    if sel_cats:
        df = df[df["trash_group"].isin(sel_cats)].copy()
    total_all=max(df["n"].sum(),1)

    CAT_FIGS = {
        "All 19 Categories: Total Items Ranked":               ("Totals & Overview",  "Every trash category ranked by cumulative item count. Colors encode environmental classification.", "The most important summary figure—use it to explain which categories drive the problem to any audience."),
        "All 56 Items: Total Count Ranked":         ("Totals & Overview",  "Every recorded item type ranked by total count from most to least common across all survey events.", "Pinpoints specific items for prevention campaigns, source identification, and partnership messaging."),
        "Category Share: Proportional Breakdown":              ("Totals & Overview",  "Donut chart showing each category as a percentage of all recorded items.", "Easy to present in reports—shows visually that Food Packaging dominates the composition."),
        "Top 10 Heaviest vs Bottom 9 Lightest Categories":      ("Totals & Overview",  "Side-by-side comparison of the 10 heaviest and 9 lightest categories.", "Shows the skewed distribution—a small number of categories account for the vast majority of items."),
        "Average Items per Survey Event by Category":           ("Totals & Overview",  "Mean items per event for each category, adjusting for number of surveys conducted.", "More meaningful than raw totals when comparing categories with different recording frequencies."),
        "Beverage Containers: Full Breakdown":                 ("Food & Beverage",    "All beverage categories (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Cups) with sub-item detail.", "Beverage containers are a major single-use plastics source. Understanding their composition supports policy work."),
        "Cups: Styrofoam vs Plastic vs Paper":                 ("Food & Beverage",    "Breakdown of Cups into Styrofoam (Polar Pop), Styrofoam (Qt), Styrofoam (Other), Plastic, and Paper.", "Styrofoam cups are non-recyclable, non-biodegradable, and fragment into microplastics in waterways."),
        "Food Packaging: All 11 Sub-Items":                    ("Food & Beverage",    "The largest category broken into 11 sub-types including wrappers, straws, 6-pack rings, plates, utensils.", "Food Packaging is the single largest category (10,694 items). Understanding its composition is critical."),
        "Alcohol Containers: Beer vs Liquor Over Time":        ("Food & Beverage",    "Quarterly time series comparing Beer and Liquor item counts across the survey record.", "Alcohol containers are associated with encampments and chronic littering—useful for community context."),
        "Recyclable vs Non-Recyclable: Item Counts":           ("Environmental Risk", "All categories split into Recyclable vs Non-Recyclable per City of Tucson recycling guidelines.", "~16% of items are technically recyclable but none are being recycled—a clear intervention target."),
        "Floatable vs Non-Floatable: River Health Risk":       ("Environmental Risk", "Categories classified by whether they float and enter waterways during rain or flooding events.", "~63% of items are floatable—directly relevant to ADEQ stormwater permits and EPA Section 319 reporting."),
        "Health Hazard Items: Rx, Drugs, Nicotine, Toiletries":("Environmental Risk", "Items with direct public health risk: syringes, drug packaging, cigarettes, lighters, and toiletries.", "Syringes create needle-stick hazard for field staff. These require special handling protocols."),
        "Bulk and Large Debris: Appliances, Construction, Auto": ("Environmental Risk", "Large items requiring equipment: appliances, furniture, tires, car parts, construction debris.", "By item count modest, but by weight and removal cost they far exceed smaller categories."),
        "Category Risk Profile: Composite View":               ("Environmental Risk", "Scatter plot showing each category's total volume crossed with its risk dimensions.", "Identifies categories that are both high-volume AND high-risk—the priority removal targets."),
        "Category Trends Over Time: Top 6 (Quarterly)":         ("Trends by Category", "Quarterly time series for the 6 highest-volume categories.", "Shows whether category composition is stable or shifting over the program period."),
        "Year over Year Change by Category":                    ("Trends by Category", "Heatmap + stacked bar showing each category's annual item total. Heatmap is the correct chart type—19 categories × 5 years would be 95 bars if grouped.", "Reveals which categories are increasing, decreasing, or stable year over year. Darker cells = more items."),
        "Category Composition: How Mix Changed by Year":       ("Trends by Category", "100% stacked bars showing each category's share per year—removes total survey size effect.", "More ecologically meaningful than raw totals for detecting true composition shifts."),
        "Category Mix by River Segment":                        ("Geographic",         "Stacked bars showing category composition across North, Central, South, and Rillito reaches.", "Different segments may have different dominant categories due to adjacent land use patterns."),
        "Segment Specialization: Top Categories per Reach":    ("Geographic",         "One tab per segment showing the top 10 categories and their share of that segment's total.", "Identifies segment-specific waste profiles for targeted cleanup planning."),
        "Full Item-Level Statistics Table":                     ("Data Tables",        "Every item with total, % of all items, records, mean, recyclable, floatable flags.", "The authoritative reference table for reporting, grant writing, and agency submissions."),
        "Category Group Summary Table":                         ("Data Tables",        "All 19 groups with total, rank, %, records, mean, and all environmental classifications.", "Use as the primary summary table in any report or presentation."),
    }

    st.markdown(f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:{C["muted"]};margin-bottom:4px;">↓ {L("Choose chart")}</div>', unsafe_allow_html=True)
    _cat_map = {L(k): k for k in CAT_FIGS.keys()}
    sel_cat_disp = st.selectbox(L("Select a figure to display"), list(_cat_map.keys()), key="cat_fig_sel", label_visibility="collapsed")
    sel_cat = _cat_map[sel_cat_disp]
    grp_label, desc, why = CAT_FIGS[sel_cat]

    # Description card
    st.markdown(
        f'<div style="background:white;border:1px solid {C["sand3"]};border-left:4px solid {C["water"]};'
        f'border-radius:0 8px 8px 0;padding:14px 20px;margin:12px 0 20px;">'
        f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};'
        f'font-family:DM Mono,monospace;margin-bottom:4px;">{L(grp_label)}</div>'
        f'<div style="font-weight:700;font-size:14px;color:{C["text"]};margin-bottom:4px;">{L(sel_cat)}</div>'
        f'<p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>{L("What it shows")}:</strong> {L(desc)}</p>'
        f'<p style="margin:3px 0;font-size:13px;color:{C["muted"]};"><strong>{L("Why it matters")}:</strong> {L(why)}</p>'
        f'</div>',
        unsafe_allow_html=True
    )

    # ── RENDER SELECTED FIGURE ─────────────────────────────────────────────

    if sel_cat == "All 19 Categories: Total Items Ranked":
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
            title="All 19 Trash Categories: Total Items Recorded"); show(fig,"cat_all19")
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
        cat_color_legend()
        fig_note(
            "Cumulative total of every recorded item in each of the 19 category groups across all survey events.",
            "Food Packaging dominates because it has 11 sub-types—but Clothing at #2 is a strong signal of encampment activity. Plastic Bags is technically its own group.",
            "Longer bars = more total items. Color encodes environmental risk classification.",
            "Raw totals are not adjusted for number of sub-items per category. A category with 11 items will naturally accumulate more than one with 1 item, all else being equal."
        )

    elif sel_cat == "All 56 Items: Total Count Ranked":
        top=df.groupby(["trash_group","trash_item"])["n"].sum().reset_index()
        top=top[top["n"]>0].sort_values("n",ascending=True)
        top["pct"]=(100*top["n"]/total_all).round(2)
        colors=[C["water"] if g in RECYCLABLE_GROUPS else C["brick"] if g in HEALTH_HAZARD_GROUPS else C["green"]
                for g in top["trash_group"]]
        fig=go.Figure(go.Bar(x=top["n"],y=top["trash_item"],orientation="h",
            marker_color=colors,
            customdata=top[["trash_group","pct"]].values,
            hovertemplate="<b>%{y}</b><br>Category: %{customdata[0]}<br>Total items: %{x:,.0f}<br>Share of all: %{customdata[1]}%<extra></extra>"))
        fb(fig,"Total Count","Item",h=max(900,20*len(top)),leg=False,
            title="All 56 Items by Total Count"); show(fig,"cat_all56")
        cat_color_legend()
        fig_note(
            "Every item type in the 56-item survey protocol, ranked from rarest to most common.",
            "Food Wrappers lead at 5,471 items. Syringes and drug paraphernalia appear low in count but are high in health significance.",
            "Hover for category and percentage. Items near the bottom may still matter for ecological or health risk beyond their count.",
            "Items recorded as zero across all events are excluded. A long tail of low-count items is scientifically important—presence/absence matters for biodiversity and pollution assessments."
        )

    elif sel_cat == "Category Share: Proportional Breakdown":
        ct2=df.groupby("trash_group")["n"].sum().sort_values(ascending=False).reset_index()
        ct2=ct2[ct2["n"]>0]
        fig=px.pie(ct2,values="n",names="trash_group",hole=.42,color_discrete_sequence=PAL)
        fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=10)
        fig.update_layout(height=540,paper_bgcolor="rgba(0,0,0,0)",font=dict(family="DM Sans"),
            margin=dict(l=8,r=8,t=36,b=8),
            title=dict(text="Category Composition: Share of All Recorded Items",
                font=dict(family="Cormorant Garamond, serif",size=16,color=C["green"]),x=0))
        show(fig,"cat_pie2")
        last_updated_insight(df,"general")
        cat_color_legend()
        fig_note("Proportional breakdown—each slice shows one category as a percentage of the total.",
            "Food Packaging at ~33% means 1 in 3 items found is food-related packaging.",
            "Hover for exact percentages. Small slices are not unimportant—Rx/Drugs at under 1% still carries major health risk.",
            "Always pair with the ranked bar chart—proportions hide absolute scale.")

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
        cat_color_legend()
        fig_note("The top 10 categories account for over 95% of all recorded items.",
            "Shows the skewed distribution—a few categories drive the problem while many others are present but minor.",
            "Left = heaviest. Right = lightest. Even the lightest categories—Rx/Drugs (189) and Auto (167)—have outsized ecological or safety impact.",
            "The top 3 alone (Food Packaging + Clothing + Plastic Bags) represent approximately 53% of all items.")

    elif sel_cat == "Average Items per Survey Event by Category":
        avg_cat=df.groupby("trash_group").agg(total=("n","sum"),events=("event_id","nunique")).reset_index()
        avg_cat["avg"]=(avg_cat["total"]/avg_cat["events"]).round(2)
        avg_cat=avg_cat.sort_values("avg",ascending=True)
        avg_cat["color"]=avg_cat["trash_group"].map(lambda g: C["brick"] if g in HEALTH_HAZARD_GROUPS else C["green"])
        fig=go.Figure(go.Bar(x=avg_cat["avg"],y=avg_cat["trash_group"],orientation="h",
            marker_color=avg_cat["color"],text=avg_cat["avg"].round(1),textposition="outside"))
        fb(fig,"Avg Items per Event","",h=max(560,32*len(avg_cat)),leg=False,
            title="Average Items per Survey Event: All Categories"); show(fig,"cat_avg2")
        cat_color_legend()
        fig_note("Mean total items per survey event for each category.",
            "Adjusts for recording frequency—a category recorded across 100 events is compared fairly to one recorded across 20.",
            "Higher = more items found per visit. Red = health hazard categories.",
            "Food Packaging will top this chart too—its high average is partly structural (11 sub-items) but also reflects genuine prevalence.")

    elif sel_cat == "Beverage Containers: Full Breakdown":
        bev=df[df["trash_group"].isin(BEVERAGE_GROUPS)].copy()
        c1c,c2c=st.columns([2,3])
        with c1c:
            bt=bev.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(bt,x="n",y="trash_group",orientation="h",
                color_discrete_sequence=[C["water"]],text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Category",h=380,leg=False,title="Beverage Categories: Totals"); show(fig,"bev_grp")
        with c2c:
            bi=bev.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(bi,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_sequence=PAL,text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=500,title="Beverage Items: All Sub-Types"); show(fig,"bev_items")
        last_updated_insight(df,"general")
        cat_color_legend()
        fig_note("All beverage container categories and their sub-type breakdown.",
            "Beverage containers represent single-use plastics and recyclables that ended up in the river corridor.",
            "Water bottles (1,635) are the most common single beverage item—many from encampments. Beer bottles lead alcohol.",
            "The presence of large quantities of Styrofoam cups is environmentally significant—Styrofoam does not biodegrade and fragments into microplastics.")

    elif sel_cat == "Cups: Styrofoam vs Plastic vs Paper":
        cups=df[df["trash_group"]=="Cups"].groupby("trash_item")["n"].sum().reset_index().sort_values("n",ascending=False)
        cups["pct"]=(100*cups["n"]/max(cups["n"].sum(),1)).round(1)
        c1c,c2c=st.columns(2)
        with c1c:
            fig=px.bar(cups.sort_values("n",ascending=True),x="n",y="trash_item",orientation="h",
                color="trash_item",color_discrete_sequence=PAL,text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Cup Type",h=340,leg=False,title="Cups: Sub-Type Breakdown"); show(fig,"cups_bar")
        with c2c:
            fig=px.pie(cups,values="n",names="trash_item",color_discrete_sequence=PAL,hole=.4)
            fig.update_traces(textposition="inside",textinfo="percent+label",textfont_size=11)
            fig.update_layout(height=340,paper_bgcolor="white",showlegend=False,
                margin=dict(l=8,r=8,t=8,b=8),font=dict(family="DM Sans"))
            show(fig,"cups_pie")
        cat_color_legend()
        fig_note("The Cups category broken into 5 sub-types.",
            "Styrofoam cups are particularly problematic—they fragment into microplastics, clog drainage, and are excluded from recycling.",
            "Polar Pop cups are the large convenience store cups associated with Circle K—useful for source attribution and retailer partnership conversations.",
            "Styrofoam (Other) is the most common sub-type—these are generic foam cups from a wide range of food service sources.")

    elif sel_cat == "Food Packaging: All 11 Sub-Items":
        fp=df[df["trash_group"]=="Food Packaging"].groupby("trash_item")["n"].sum().reset_index().sort_values("n",ascending=True)
        fp["pct"]=(100*fp["n"]/max(fp["n"].sum(),1)).round(1)
        fig=px.bar(fp,x="n",y="trash_item",orientation="h",color="trash_item",
            color_discrete_sequence=PAL,
            text=[f"{int(v):,} ({p}%)" for v,p in zip(fp["n"],fp["pct"])])
        fig.update_traces(textposition="outside")
        fb(fig,"Total Items","Item Type",h=max(440,36*len(fp)),leg=False,
            title="Food Packaging: All 11 Sub-Types"); show(fig,"fp_items")
        last_updated_insight(df,"category","Food Packaging")
        cat_color_legend()
        fig_note("Food Packaging is the single largest category at 10,694 items—spanning 11 distinct sub-types.",
            "Food Wrappers alone account for 51% of all Food Packaging (5,471 items). Straws are #3 at 860.",
            "6-pack rings and straws pose direct entanglement risk to birds and reptiles in the riparian corridor.",
            "Non-cup styrofoam (805) is especially harmful—it breaks into small beads that are indistinguishable from food particles to wildlife.")

    elif sel_cat == "Alcohol Containers: Beer vs Liquor Over Time":
        alc=df[df["trash_group"].isin(["Beer","Liquor"])].copy()
        if "date" in alc.columns and alc["date"].notna().any():
            ts_alc=alc.groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ts_alc,x="date",y="n",color="trash_group",markers=True,
                color_discrete_map={"Beer":C["amber"],"Liquor":C["brick"]})
            fb(fig,"Quarter","Items",h=440,title="Alcohol Containers: Beer vs Liquor (Quarterly)"); show(fig,"alc_ts")
            cat_color_legend()
            fig_note("Quarterly counts of Beer and Liquor items across the survey record.",
                "Alcohol containers are associated with encampments, informal gatherings, and chronic littering. Understanding their trajectory helps community engagement planning.",
                "Amber = Beer, Red = Liquor. Rising lines indicate increasing alcohol-related litter.",
                "Beer bottles (789 total) and Liquor glass (598) are heavy items that persist in the environment for decades.")
        else:
            st.info(L("No date data available for this figure."))

    elif sel_cat == "Recyclable vs Non-Recyclable: Item Counts":
        rec_df=df.copy()
        rec_df["recyclable"]=rec_df["trash_group"].map(lambda g:
            L("Recyclable") if g in RECYCLABLE_GROUPS else L("Non-Recyclable"))
        r_tot=rec_df.groupby("recyclable")["n"].sum().reset_index()
        r_tot["pct"]=(100*r_tot["n"]/max(r_tot["n"].sum(),1)).round(1)
        r_grp=rec_df.groupby(["recyclable","trash_group"])["n"].sum().reset_index()
        c1c,c2c=st.columns([1,2])
        with c1c:
            fig=px.pie(r_tot,values="n",names="recyclable",hole=.5,
                color_discrete_map={"Recyclable":C["water"],"Non-Recyclable":C["brick"]})
            fig.update_traces(textinfo="percent+label",textfont_size=12)
            fig.update_layout(height=300,paper_bgcolor="white",showlegend=False,
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
            f'" + L("Classification based on <strong>City of Tucson recycling guidelines</strong>.") + " '
            f'<span style="color:{C["water"]};font-weight:700;">" + L("Blue = Recyclable") + "</span> (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Paper Litter) &nbsp;|&nbsp; '
            f'<span style="color:{C["brick"]};font-weight:700;">" + L("Red = Non-Recyclable") + "</span>'
            f'</div>',
            unsafe_allow_html=True
        )
        fig_note("All 19 categories classified by City of Tucson recycling eligibility.",
            "Approximately 16% of items by count are technically recyclable—but none are being recycled because they end up in the river corridor.",
            "Blue = recyclable (Beer, Liquor, Soda, Water, Sports Drinks, Juice, Paper Litter). These represent a missed diversion opportunity.",
            "A beverage container deposit program (bottle bill) would directly target the recyclable fraction. This data can directly support such policy advocacy.")

    elif sel_cat == "Floatable vs Non-Floatable: River Health Risk":
        fl_df=df.copy()
        fl_df["floatable"]=fl_df["trash_group"].map(lambda g:
            L("Floatable") if g in FLOATABLE_GROUPS else L("Non-Floatable"))
        f_tot=fl_df.groupby("floatable")["n"].sum().reset_index()
        f_tot["pct"]=(100*f_tot["n"]/max(f_tot["n"].sum(),1)).round(1)
        f_grp=fl_df.groupby(["floatable","trash_group"])["n"].sum().reset_index()
        c1c,c2c=st.columns([1,2])
        with c1c:
            fig=px.pie(f_tot,values="n",names="floatable",hole=.5,
                color_discrete_map={"Floatable":"#2471a3","Non-Floatable":"#7f8c8d"})
            fig.update_traces(textinfo="percent+label",textfont_size=12)
            fig.update_layout(height=300,paper_bgcolor="white",showlegend=False,
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
            f'" + L("Floatable items travel downstream during rain events and reach waterways.") + " '
            f'<span style="color:#2471a3;font-weight:700;">" + L("Blue = Floatable") + "</span> &nbsp;|&nbsp; '
            f'<span style="color:#7f8c8d;font-weight:700;">" + L("Gray = Non-Floatable") + "</span> &nbsp;|&nbsp; '
            f'" + L("Based on Sonoran Institute field classification.") + "'
            f'</div>',
            unsafe_allow_html=True
        )
        fig_note("Items classified by ability to float and travel downstream during storm events.",
            "Approximately 63% of all recorded items are floatable—meaning the majority of Santa Cruz River litter is at risk of entering the water column during monsoon events.",
            "Blue = enters waterways during rain. Food Packaging, Plastic Bags, Cups, and all beverage bottles are floatable.",
            "This analysis directly supports ADEQ stormwater permit compliance, EPA Section 319 nonpoint source pollution reporting, and conservation grant applications.")

    elif sel_cat == "Health Hazard Items: Rx, Drugs, Nicotine, Toiletries":
        hh=df[df["trash_group"].isin(HEALTH_HAZARD_GROUPS)].copy()
        c1c,c2c=st.columns(2)
        with c1c:
            ht=hh.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(ht,x="n",y="trash_group",orientation="h",
                color="trash_group",
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Category",h=280,leg=False,title="Health Hazard Categories: Totals"); show(fig,"hh_grp")
        with c2c:
            hi=hh.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(hi,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=280,title="Health Hazard Items: Sub-Types"); show(fig,"hh_items")
        if "date" in hh.columns and hh["date"].notna().any():
            ts_hh=hh.groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ts_hh,x="date",y="n",color="trash_group",markers=True,
                color_discrete_map={"Rx, Drugs":C["brick"],"Nicotine":C["earth"],"Toiletries":C["amber"]})
            fb(fig,"Quarter","Items",h=320,title="Health Hazard Items Over Time"); show(fig,"hh_ts")
        cat_color_legend()
        fig_note("Three categories with direct public health risk: Rx/Drugs, Nicotine, and Toiletries.",
            "Syringes (101 recorded) and drug paraphernalia (88) create needle-stick hazard for field staff and community volunteers. Nicotine (1,255) is the most numerically prevalent hazard.",
            "All three require special handling protocols and personal protective equipment during removal events.",
            "These numbers should be treated as minimums—syringes are likely underreported due to safety concerns and incomplete detection during surveys.")

    elif sel_cat == "Bulk and Large Debris: Appliances, Construction, Auto":
        bk=df[df["trash_group"].isin(BULK_DEBRIS_GROUPS)].copy()
        c1c,c2c=st.columns(2)
        with c1c:
            bt2=bk.groupby("trash_group")["n"].sum().sort_values(ascending=True).reset_index()
            fig=px.bar(bt2,x="n",y="trash_group",orientation="h",
                color="trash_group",
                color_discrete_map={"Appliances":C["earth"],"Construction":C["sage"],"Auto":C["muted"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","",h=260,leg=False,title="Bulk Debris: Category Totals"); show(fig,"bk_grp")
        with c2c:
            bi2=bk.groupby(["trash_group","trash_item"])["n"].sum().reset_index().sort_values("n",ascending=True)
            fig=px.bar(bi2,x="n",y="trash_item",color="trash_group",orientation="h",
                color_discrete_map={"Appliances":C["earth"],"Construction":C["sage"],"Auto":C["muted"]},
                text="n")
            fig.update_traces(texttemplate="%{text:,.0f}",textposition="outside")
            fb(fig,"Total","Item",h=400,title="Bulk Debris: All Sub-Types"); show(fig,"bk_items")
        cat_color_legend()
        fig_note("Appliances (550), Construction (1,147), and Auto (167) are large items requiring equipment to remove.",
            "Construction debris—particularly Small Items (1,104)—indicates illegal dumping of building waste along the corridor.",
            "By item count these seem modest, but by weight and volunteer-hours required for removal they represent a disproportionate burden.",
            "Tires (48) create standing water that breeds mosquitoes. Shopping carts signal commercial area drainage. These require coordinated heavy equipment removal.")

    elif sel_cat == "Category Risk Profile: Composite View":
        risk_data=[]
        for g in GROUP_ORDER:
            if g not in df["trash_group"].unique(): continue
            total=df[df["trash_group"]==g]["n"].sum()
            risk_data.append({"Category":g,"Total Items":int(total),
                "Recyclable": L("Yes") if g in RECYCLABLE_GROUPS else L("No"),
                "Floatable":  L("Yes") if g in FLOATABLE_GROUPS else L("No"),
                "Health Hazard": L("Yes") if g in HEALTH_HAZARD_GROUPS else L("No"),
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
            title="Category Risk Profile: Volume vs Risk"); show(fig,"risk_scatter")
        cat_color_legend()
        fig_note("Each dot = a category flagged with a risk dimension. Larger and further right = more items.",
            "Shows which categories combine high volume with high environmental or health risk.",
            "Food Packaging is Floatable. Rx/Drugs is a Health Hazard. Construction is Bulk Debris. Beer is Recyclable.",
            "Categories that are BOTH high-volume AND high-risk are priority targets—e.g. Plastic Bags (3,649 items, Floatable, Non-Recyclable).")

    elif sel_cat == "Category Trends Over Time: Top 6 (Quarterly)":
        top6=df.groupby("trash_group")["n"].sum().nlargest(6).index.tolist()
        if "date" in df.columns and df["date"].notna().any():
            ct6=df[df["trash_group"].isin(top6)].groupby(["trash_group",pd.Grouper(key="date",freq="QS")])["n"].sum().reset_index()
            fig=px.line(ct6,x="date",y="n",color="trash_group",markers=True,color_discrete_sequence=PAL)
            fb(fig,"Quarter","Items",h=480,title="Top 6 Categories: Quarterly Item Counts"); show(fig,"cat_trend2")
            last_updated_insight(df,"general")
            cat_color_legend()
            fig_note("Quarterly trends for the 6 highest-volume categories.",
                "Reveals whether the category composition is stable or if specific categories are increasing.",
                "Lines diverging upward = that category is growing. Parallel lines = uniform change across categories.",
                "A declining Food Packaging trend would signal intervention success. An increasing Clothing trend may reflect changing encampment patterns along the corridor.")
        else:
            st.info(L("No date data available."))

    elif sel_cat == "Year over Year Change by Category":
        if "year" in df.columns and df["year"].notna().any():
            yoy=df.groupby(["year","trash_group"])["n"].sum().reset_index()
            yoy["year_str"]=yoy["year"].astype(int).astype(str)
            ord_cats=[g for g in GROUP_ORDER if g in yoy["trash_group"].unique()]

            # A: Heatmap—correct chart type for category × year matrix
            # Grouped bar with 19 cats × 5 years = 95 bars, completely unreadable
            pivot=yoy.pivot(index="trash_group",columns="year_str",values="n").fillna(0)
            pivot=pivot.reindex([g for g in reversed(GROUP_ORDER) if g in pivot.index])
            fig=go.Figure(go.Heatmap(
                z=pivot.values,
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                colorscale=[[0,"#f8f5ef"],[0.3,C["mint"]],[0.7,C["green"]],[1,C["forest"]]],
                hoverongaps=False,
                hovertemplate="<b>%{y}</b><br>Year: %{x}<br>Total items: %{z:,.0f}<extra></extra>",
                texttemplate="%{z:.0f}",
                textfont=dict(size=10),
                showscale=True,
                colorbar=dict(title=dict(text="Total Items",font=dict(size=11)))
            ))
            fb(fig,"Year","Category",h=580,leg=False,
                title="Annual Item Totals by Category (Heatmap)"); show(fig,"yoy_heat")

            # B: Stacked bar for total comparison across years
            fig2=px.bar(yoy,x="year_str",y="n",color="trash_group",barmode="stack",
                color_discrete_sequence=PAL,category_orders={"trash_group":ord_cats},
                text=None)
            fb(fig2,"Year","Total Items",h=420,
                title="Annual Category Totals: Stacked Bar"); show(fig2,"yoy_stack")

            cat_color_legend()
            fig_note(
                "Top: Heatmap shows each category's item count per year. Darker green = more items. Bottom: Stacked bar shows total burden per year with category breakdown.",
                "Heatmap is the correct chart type here—19 categories × 5 years would produce 95 bars in a grouped bar chart, making it unreadable.",
                "Heatmap: scan horizontally across a category to see if it is growing. Scan vertically down a year to compare categories within that year.",
                "Stacked bar: the height of the full bar = total items that year. The color slices show which categories contributed most."
            )
        else:
            st.info(L("No year data available."))

    elif sel_cat == "Category Composition: How Mix Changed by Year":
        if "year" in df.columns and df["year"].notna().any():
            yp=df.groupby(["year","trash_group"])["n"].sum().reset_index()
            yp_tot=yp.groupby("year")["n"].sum().reset_index(name="yr_total")
            yp=yp.merge(yp_tot,on="year")
            yp["share"]=100*yp["n"]/yp["yr_total"]
            yp["year_str"]=yp["year"].astype(int).astype(str)
            ord_cats=[g for g in GROUP_ORDER if g in yp["trash_group"].unique()]
            fig=px.bar(yp,x="year_str",y="share",color="trash_group",barmode="stack",
                color_discrete_sequence=PAL,category_orders={"trash_group":ord_cats})
            fb(fig,"Year","Share of Total (%)",h=500,title="Category Composition by Year: Proportional"); show(fig,"comp_yr")
            cat_color_legend()
            fig_note("100% stacked bars—each bar totals 100%, showing category SHARE each year.",
                "Removes the effect of varying survey effort and shows whether the MIX of items is changing.",
                "A growing color slice = that category is increasing as a proportion of all litter.",
                "This is more ecologically meaningful than raw totals for detecting genuine composition shifts independent of survey frequency.")
        else:
            st.info(L("No year data available."))

    elif sel_cat == "Category Mix by River Segment":
        if "seg" in df.columns:
            sg2=df[df["seg"].isin(SEG_ORDER[:-1])].groupby(["seg","trash_group"])["n"].sum().reset_index()
            ord_cats=[g for g in GROUP_ORDER if g in sg2["trash_group"].unique()]
            fig=px.bar(sg2,x="n",y="seg",color="trash_group",orientation="h",barmode="stack",
                color_discrete_sequence=PAL,
                category_orders={"seg":list(reversed(SEG_ORDER[:-1])),"trash_group":ord_cats})
            fb(fig,"Total Items","Segment",h=400,title="Category Composition by River Segment"); show(fig,"seg_cat")
            color_legend("Segment Colors", mode="segments")
            cat_color_legend()
            fig_note("Stacked bars showing category composition across the four named river reaches.",
                "Reveals whether certain reaches have distinctly different waste profiles due to adjacent land use.",
                "A segment with unusually high Clothing indicates encampments. High Construction suggests illegal dumping nearby.",
                "Only sites with confirmed segment labels are included. Unlabeled sites appear under 'Other' which is excluded here.")
        else:
            st.info(L("No segment data."))

    elif sel_cat == "Segment Specialization: Top Categories per Reach":
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
                        title=f"{seg}: All Categories ({seg_tot_n:,} total items)"); show(fig,f"seg_spec_{i}")
            cat_color_legend()
            fig_note("Top categories for each river segment shown in individual tabs.",
                "Identifies segment-specific waste profiles—useful for targeted cleanup events and reporting to local jurisdictions.",
                "Compare the relative share of each category across segments—a category dominant in one segment but minor in another points to local source patterns.",
                "Use alongside the Map page to connect geographic patterns with specific land uses, outfalls, or encampment locations along each reach.")
        else:
            st.info(L("No segment data."))

    elif sel_cat == "Full Item-Level Statistics Table":
        cat_color_legend()
        item_tbl=df.groupby(["trash_group","trash_item"])["n"].agg(Total="sum",Records="count",Mean="mean").reset_index()
        item_tbl["% of All Items"]=(100*item_tbl["Total"]/total_all).round(2)
        item_tbl["Recyclable"]=item_tbl["trash_group"].map(lambda g: L("Yes") if g in RECYCLABLE_GROUPS else L("No"))
        item_tbl["Floatable"]=item_tbl["trash_group"].map(lambda g: L("Yes") if g in FLOATABLE_GROUPS else L("No"))
        item_tbl["Health Hazard"]=item_tbl["trash_group"].map(lambda g: L("Yes") if g in HEALTH_HAZARD_GROUPS else L("No"))
        item_tbl=item_tbl[item_tbl["Total"]>0].sort_values("Total",ascending=False).round(2).reset_index(drop=True)
        item_tbl.index=range(1,len(item_tbl)+1)
        item_tbl.columns=["Category","Item","Total Count","# Records","Mean per Record","% of All Items","Recyclable","Floatable","Health Hazard"]
        st.dataframe(item_tbl, use_container_width=True, height=580)
        tbl_note("Every individual item type with cumulative statistics. Records = number of data entries. Mean per Record = average count per entry (not per event). % is relative to the current filter. Recyclable = City of Tucson standard. Floatable = river health risk. Health Hazard = direct human contact risk.")

    elif sel_cat == "Category Group Summary Table":
        cat_color_legend()
        grp_tbl=df.groupby("trash_group")["n"].agg(Total="sum",Records="count",Mean="mean").reset_index()
        grp_tbl["% of Total"]=(100*grp_tbl["Total"]/total_all).round(1)
        grp_tbl["Rank"]=grp_tbl["Total"].rank(ascending=False).astype(int)
        grp_tbl["Recyclable"]=grp_tbl["trash_group"].map(lambda g: L("Yes") if g in RECYCLABLE_GROUPS else L("No"))
        grp_tbl["Floatable"]=grp_tbl["trash_group"].map(lambda g: L("Yes") if g in FLOATABLE_GROUPS else L("No"))
        grp_tbl["Health Hazard"]=grp_tbl["trash_group"].map(lambda g: L("Yes") if g in HEALTH_HAZARD_GROUPS else L("No"))
        grp_tbl=grp_tbl[grp_tbl["Total"]>0].sort_values("Total",ascending=False).round(2).reset_index(drop=True)
        grp_tbl.index=range(1,len(grp_tbl)+1)
        grp_tbl.columns=["Category","Total Items","# Records","Mean per Record","% of Total","Rank","Recyclable","Floatable","Health Hazard"]
        st.dataframe(grp_tbl, use_container_width=True, height=500)
        tbl_note("All 19 categories with rank, statistics, and environmental classifications. Rank 1 = most items recorded. Recyclable = City of Tucson standard. Floatable = river health classification. Health Hazard = direct human exposure risk. Use this table in any report, grant application, or agency submission.")

    st.markdown('</div>', unsafe_allow_html=True)


elif page == "Locations":
    page_banner("Site-Level Analysis", "Where the Trash Is and How Much", "Trash burden across recorded survey locations. Sites are ordered North to South along the river corridor.", "https://sonoraninstitute.org/files/BHatch_02042018_1116-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Locations")

    if scope_is_strict:
        st.markdown(f'''<div style="background:white;border:1px solid {C["sand3"]};border-radius:10px;padding:18px 24px;margin-bottom:22px;font-size:13px;line-height:1.85;color:{C["text"]};">
        <div style="font-family:Cormorant Garamond,serif;font-size:1rem;font-weight:700;color:{C["green"]};margin-bottom:10px;">How to read the statistics on this page</div>
        <p style="margin:0 0 8px;"><strong>Strict triplicate rule:</strong> This page is using only exact triplicate sessions, one comparable session = exactly <strong>3 surveyed plots</strong>. Single plots, doubles, and larger mixed team days are excluded from the current view.</p>
        <p style="margin:0 0 8px;"><strong>Mean:</strong> For each strict session, the three plot totals are averaged first. The site mean is then the average of those triplicate session means. This is the most defensible number for comparing typical plot-level trash burden across sites.</p>
        <p style="margin:0 0 8px;"><strong>SD and SE:</strong> SD shows how much those triplicate session means vary over time. SE shows how precisely the site mean is estimated across independent strict sessions.</p>
        <p style="margin:0 0 8px;"><strong>CV:</strong> CV is SD divided by the mean. It helps compare variability across sites with different trash levels.</p>
        <p style="margin:0;"><strong>Why this matters:</strong> The raw trash counts are still real counted items. The correction here is about comparability and independence, not about saying the counts were false.</p>
        </div>''', unsafe_allow_html=True)
    else:
        st.markdown(f'''<div style="background:white;border:1px solid {C["sand3"]};border-radius:10px;padding:18px 24px;margin-bottom:22px;font-size:13px;line-height:1.85;color:{C["text"]};">
        <div style="font-family:Cormorant Garamond,serif;font-size:1rem;font-weight:700;color:{C["green"]};margin-bottom:10px;">How to read the statistics on this page</div>
        <p style="margin:0 0 8px;"><strong>All recorded plots view:</strong> This page is showing every recorded plot that matches the filters. That is useful for raw descriptive viewing, but repeated same-day plots can make the record look more independent than it really is.</p>
        <p style="margin:0 0 8px;"><strong>Mean:</strong> In this view, each recorded plot/event contributes directly to the site mean.</p>
        <p style="margin:0 0 8px;"><strong>SD and SE:</strong> These are still shown, but they are more optimistic because same-day replicate plots are included as separate observations.</p>
        <p style="margin:0;"><strong>Recommendation:</strong> Switch back to <strong>Strict triplicate sessions only</strong> for the more conservative reporting and paper-style comparison view.</p>
        </div>''', unsafe_allow_html=True)

    with st.expander(T("filter_data"), expanded=False):
        lf=render_filters(scope_long, kp="loc", cats=False)

    df_all=lf.copy()
    df_all["n"]=pd.to_numeric(df_all["n"],errors="coerce").fillna(0)
    df=keep_exact_triplicate_sessions(df_all) if scope_is_strict else df_all.copy()
    stat_strip(scope_long, df if len(df)>0 else df_all)

    ss=build_site_stats_ns(df_all) if scope_is_strict else build_site_stats_raw(df_all)
    site_st=df.groupby(["site_label","seg"]).agg(total=("n","sum"),plot_records=("event_id","nunique"),
        mean=("n","mean"),mx=("n","max"),mn_v=("n","min"),sd=("n","std")).reset_index() if len(df)>0 else pd.DataFrame(columns=["site_label","seg","total","plot_records","mean","mx","mn_v","sd"])
    if len(site_st)>0:
        site_st["avg_per_event"]=(site_st["total"]/site_st["plot_records"]).round(1)
        site_st["sd"]=site_st["sd"].fillna(0).round(1)
        site_st=site_st.sort_values("total",ascending=False).reset_index(drop=True)

    strict_sessions_n = len(strict_triplicate_sessions(df_all)) if len(df_all)>0 else 0
    if len(df)==0:
        st.warning("No rows match the current scope and filters on this page.")

    grand_mean = ss["mean"].mean() if len(ss)>0 else 0
    grand_sd   = ss["sd"].mean() if len(ss)>0 else 0
    max_site_total = int(site_st["total"].max()) if len(site_st)>0 else 0
    scope_sites_lbl = "Triplicate Sites" if scope_is_strict else "Sites in View"
    scope_sessions_lbl = "Triplicate Sessions" if scope_is_strict else "Plot Records"
    scope_session_val = strict_sessions_n if scope_is_strict else (df["event_id"].nunique() if len(df)>0 else 0)
    st.markdown(f"""<div class="stat-strip">
    <div class="stat-item"><span class="stat-v">{len(ss) if len(ss)>0 else 0}</span><span class="stat-l">{scope_sites_lbl}</span></div>
    <div class="stat-item"><span class="stat-v">{max_site_total:,}</span><span class="stat-l">Max Raw Items at One Site</span></div>
    <div class="stat-item"><span class="stat-v">{grand_mean:.1f}</span><span class="stat-l">Grand Mean / Plot</span></div>
    <div class="stat-item"><span class="stat-v">±{grand_sd:.1f}</span><span class="stat-l">Mean SD Across Sites</span></div>
    <div class="stat-item"><span class="stat-v">{scope_session_val:,}</span><span class="stat-l">{scope_sessions_lbl}</span></div>
    </div>""", unsafe_allow_html=True)

    color_legend("River Segment Colors", mode="segments")

    loc_tab1, loc_tab2, loc_tab3, loc_tab4 = st.tabs([
        "North to South: Mean", "North to South: Variability",
        "Segment Comparison", "Full Statistics Table"
    ])

    with loc_tab1:
        ns_show = pd.DataFrame()
        if len(ss)>0:
            card_open("Average Items per Plot: North to South",
                      "Each bar = one survey site. Height = mean items per event at that site. Sites are ordered geographically from northernmost (top) to southernmost (bottom). Color indicates river segment.")
            ns_show = ss[ss["lat_num"].notna()].sort_values("north_rank")
            if len(ns_show)>0:
                fig=px.bar(ns_show, x="mean", y="site_display", orientation="h",
                    color="seg", color_discrete_map=SEG_COLORS,
                    error_x="se",
                    category_orders={"site_display": ns_show["site_display"].tolist()})
                fig.update_yaxes(categoryorder="array", categoryarray=ns_show["site_display"].tolist(), autorange="reversed")
                fb(fig,"Mean Items per Plot","Site (North to South)",
                   h=max(560,26*len(ns_show)),
                   title="Mean Items per Plot: North to South"); show(fig,"ns_mean")
                last_updated_insight(df, chart_type="general")
            fig_note(
                "Mean number of items recorded per 10 m × 10 m plot at each site, using only exact triplicate sessions, ordered north to south by GPS latitude.",
                "Geographic ordering reveals whether trash burden is clustered in certain reaches of the corridor.",
                "Longer bars = heavier sites. Error bars show ±1 standard error (SE). Sites at the top are the northernmost. Only exact triplicate sessions are included.",
                "SE = SD ÷ √n. A small SE means the site mean is reliably estimated. A large SE means high variability between triplicate sessions at that site."
            )

        section_title("Site Statistics: North to South")
        st.markdown('<div class="sec-sub">Full statistical summary for sites with GPS coordinates, ordered north to south. N = number of exact triplicate sessions. Mean ± SD are computed across triplicate session means at each site.</div>', unsafe_allow_html=True)
        if len(ns_show)>0:
            tbl = ns_show[["north_rank","site_display","seg","n_plots","mean","sd","se","cv","range","total","lat_num","lon"]].copy()
            tbl = tbl.rename(columns={"north_rank":"Rank (N→S)","site_display":"Site","seg":"Segment",
                "n_plots":"N (triplicate sessions)","mean":"Mean","sd":"Std Dev","se":"Std Error",
                "cv":"CV (%)","range":"Range","total":"Total","lat_num":"Latitude","lon":"Longitude"})
            tbl["CV (%)"]=tbl["CV (%)"].apply(lambda x: f"{100*x:.1f}" if pd.notna(x) else "—")
            tbl = tbl.round(2)
            st.dataframe(tbl, use_container_width=True, height=500)
            tbl_note("Mean = average items per plot after averaging the 3 plots in each kept site-date session. SD = spread across exact triplicate sessions. SE = reliability of the site mean across those sessions. CV = coefficient of variation (SD÷Mean×100), higher % means more variable site. Range = max minus min across triplicate session means. Rank 1 = northernmost site with coordinates.")

    with loc_tab2:
        if len(ss)>0:
            ns_show = ss[ss["lat_num"].notna()].sort_values("north_rank")
            c1v,c2v = st.columns(2)
            with c1v:
                card_open("Standard Deviation: North to South",
                          "SD measures how much exact triplicate sessions vary at each site. A site with SD=0 had the same triplicate session mean every time. High SD = unpredictable or patchy litter.")
                fig=px.bar(ns_show,x="sd",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
                fig.update_yaxes(categoryorder="array",categoryarray=ns_show["site_display"].tolist(),autorange="reversed")
                fb(fig,"Standard Deviation","Site",h=max(500,24*len(ns_show)),title="Within-Site Variability: North to South"); show(fig,"ns_sd")
                fig_note("Standard deviation of triplicate session means at each site.",
                    "High SD indicates inconsistency, some triplicate sessions found a lot of trash, others very little.",
                    "Longer bars = more variable sites. A site can have a low mean but high SD if trash pulses are sporadic between triplicate sessions.",
                    "SD is not comparable across sites with very different means. Use CV for that.")
            with c2v:
                card_open("Coefficient of Variation: North to South",
                          "CV = SD ÷ Mean × 100. It normalizes variability so sites with different mean burden can be fairly compared.")
                ns_show_cv = ns_show[ns_show["cv"].notna()].copy()
                ns_show_cv["cv_pct"]=(ns_show_cv["cv"]*100).round(1)
                if len(ns_show_cv)>0:
                    fig=px.bar(ns_show_cv,x="cv_pct",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
                    fig.update_yaxes(categoryorder="array",categoryarray=ns_show_cv["site_display"].tolist(),autorange="reversed")
                    fb(fig,"CV (%)","Site",h=max(500,24*len(ns_show_cv)),title="Coefficient of Variation: North to South"); show(fig,"ns_cv")
                    fig_note("CV = (SD ÷ Mean) × 100, expressed as a percentage.",
                        "Unlike SD, CV adjusts for the size of the mean so you can compare variability across sites fairly.",
                        "CV < 30% = relatively consistent. CV 30–100% = moderate variability. CV > 100% = highly unpredictable.",
                        "A clean site with CV=150% is more unpredictable than a heavy site with CV=25%.")

            card_open("Range of Items: North to South",
                      "Range = maximum triplicate session mean minus minimum triplicate session mean at that site. Simple and easy to communicate in presentations.")
            fig=px.bar(ns_show,x="range",y="site_display",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
            fig.update_yaxes(categoryorder="array",categoryarray=ns_show["site_display"].tolist(),autorange="reversed")
            fb(fig,"Range (Max − Min)","Site",h=max(500,24*len(ns_show)),title="Range of Items: North to South"); show(fig,"ns_range")
            fig_note("The difference between the heaviest and lightest triplicate session means recorded at each site.",
                "Range is intuitive for non-technical audiences.",
                "A range of 0 means the same triplicate session mean every time. A large range means the site fluctuates dramatically.",
                "Range is sensitive to extreme outlier events, unlike SD or CV.")

    with loc_tab3:
        c1s,c2s = st.columns(2)
        with c1s:
            card_open("Total Items by River Segment",
                      "Sum of all recorded items across all events and sites within each named segment. Only sites with segment labels are included.")
            seg_tot=df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg")["n"].sum().reset_index()
            seg_tot["pct"]=(100*seg_tot["n"]/max(seg_tot["n"].sum(),1)).round(1)
            seg_tot["label"]=[f"{int(v):,} ({p}%)" for v,p in zip(seg_tot["n"],seg_tot["pct"])]
            fig=px.bar(seg_tot,x="seg",y="n",color="seg",text="label",color_discrete_map=SEG_COLORS,category_orders={"seg":SEG_ORDER})
            fig.update_traces(textposition="outside",textfont_size=10)
            fb(fig,"Segment","Total Items",h=340,leg=False,title="Total Items by River Segment"); show(fig,"loc_seg")
            fig_note("Cumulative sum of all recorded items within each river segment.",
                "Identifies which reach contributes most to the overall corridor burden.",
                "Taller bars = more total trash. This is influenced by both the number of sites and their individual burden.",
                "A segment with many lightly-visited sites can look heavy due to accumulated counts.")
        with c2s:
            card_open("Triplicate Sessions by River Segment",
                      "Number of independent exact triplicate sessions within each segment, showing conservative sampling effort distribution.")
            seg_ev=df[df["seg"].isin(SEG_ORDER[:-1])][["seg","site_label","date"]].drop_duplicates().groupby("seg").size().reset_index(name="events")
            fig=px.bar(seg_ev,x="seg",y="events",color="seg",color_discrete_map=SEG_COLORS)
            fb(fig,"Segment","# Sessions",h=320,leg=False,title="Triplicate Sessions by River Segment"); show(fig,"loc_segev")
            fig_note("Number of independent exact triplicate sessions per segment.",
                "Unequal sampling effort means direct total comparisons should be interpreted with care.",
                "Compare with total items chart, a segment with more triplicate sessions should be expected to have more items.",
                "Normalizing by session means is more fair when sampling effort differs substantially.")
        color_legend("Segment Colors", mode="segments")

        section_title("Segment Summary Table")
        seg_summary = df[df["seg"].isin(SEG_ORDER[:-1])].groupby("seg").agg(
            Total_Items=("n","sum"),
            Plot_Records=("event_id","nunique"),
            Sites=("site_label","nunique"),
            Mean_per_plot=("n","mean")
        ).reset_index().rename(columns={"seg":"River Segment","Total_Items":"Total Items",
            "Plot_Records":"# Plot Records","Sites":"# Sites","Mean_per_plot":"Mean per Plot"})
        seg_summary = seg_summary.round(1)
        st.dataframe(seg_summary, use_container_width=True, height=240)
        tbl_note("Mean per Plot is computed across the strict triplicate-only subset shown on this page. Raw totals remain real counted items from those kept plot records.")

        section_title("Top 20 Sites by Average Items per Plot")
        top20_avg=site_st.nlargest(20,"avg_per_event").sort_values("avg_per_event")
        card_open("Sites Ranked by Average Items per Plot",
                  "Average items per plot is a fairer metric than total count because it adjusts for how many strict triplicate sessions a site has.")
        fig=px.bar(top20_avg,x="avg_per_event",y="site_label",orientation="h",color="seg",color_discrete_map=SEG_COLORS)
        fb(fig,"Avg Items / Plot",None,h=max(460,22*len(top20_avg)),title="Top 20 Sites: Avg Items per Plot"); show(fig,"loc_avg")
        fig_note("Average items per plot at each site, using only exact triplicate sessions.",
            "Avoids penalizing well-sampled sites that appear heavier only because they were visited more.",
            "A site with heavier plot-level burden will rank higher even if another site simply has more total visits.",
            "Use alongside triplicate session counts, a high average based on very few sessions may not be reliable.")
        card_close()

    with loc_tab4:
        seg_filter2=st.selectbox(L("Filter by River Segment"),[L("All")]+SEG_ORDER[:-1], key="loc_seg_filter2")
        view_order=st.radio(L("Sort order"),[L("North to South (GPS)"),L("By Total Items"),L("By Mean per Plot")],horizontal=True)

        if len(ss)>0:
            tbl_full = ss.merge(site_st[["site_label","total","plot_records","avg_per_event"]],on="site_label",how="left",suffixes=("","_ev"))
            if seg_filter2!=L("All") and seg_filter2!="All": tbl_full=tbl_full[tbl_full["seg"]==seg_filter2]
            if view_order=="North to South (GPS)":
                tbl_full=tbl_full.sort_values(["north_rank","site_label"])
            elif view_order=="By Total Items":
                tbl_full=tbl_full.sort_values("total",ascending=False)
            else:
                tbl_full=tbl_full.sort_values("mean",ascending=False)

            disp=tbl_full[["site_display","seg","n_plots","mean","sd","se","cv","range","total","lat_num","lon"]].copy()
            disp["cv_pct"]=(disp["cv"]*100).round(1)
            disp=disp.drop(columns=["cv"])
            disp=disp.rename(columns={"site_display":"Site (N→S)","seg":"Segment","n_plots":"N Triplicate Sessions",
                "mean":"Mean","sd":"SD","se":"SE","cv_pct":"CV (%)","range":"Range",
                "total":"Total","lat_num":"Latitude","lon":"Longitude"})
            disp=disp.round(2).reset_index(drop=True); disp.index=range(1,len(disp)+1)
            st.dataframe(disp, use_container_width=True, height=600)
            tbl_note("N Triplicate Sessions = number of exact site-date triplicate sessions at this site. Mean ± SD are computed across triplicate session means. SE = SD÷√N. CV = SD÷Mean×100. Range = Max−Min across triplicate session means. Sites without GPS coordinates may not have a North to South rank.")
        else:
            filtered_st=site_st if seg_filter2 in (L("All"),"All") else site_st[site_st["seg"]==seg_filter2]
            disp=filtered_st[["site_label","seg","total","plot_records","avg_per_event","mean","sd","mx","mn_v"]].copy()
            disp.columns=["Location","Segment","Total Items","# Plot Records","Avg/Plot","Mean","SD","Max","Min"]
            disp=disp.round(1).reset_index(drop=True); disp.index=range(1,len(disp)+1)
            st.dataframe(disp, use_container_width=True, height=600)
            tbl_note("Mean and SD are computed from the strict triplicate-only subset used on this page.")

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# DATA TABLE
# ══════════════════════════════════════════════════════════════════
elif page == "Data Table":
    page_banner(T("dt_ey"), T("dt_title"), T("dt_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    scope_long, scope_is_strict = render_analysis_scope_selector(long, context_label="Data Table")
    with st.expander(T("filter_data"), expanded=True):
        lf=render_filters(scope_long, kp="dt", cats=True)  # cats=True enables category multiselect
    stat_strip(scope_long,lf)

    # Two view modes—long (default) and wide (Excel-like)
    dt_view = st.radio(
        L("Table format"),
        [L("Wide format—one row per event, each item as a column (like Excel)"),
         L("Long format—one row per item per event")],
        horizontal=True, key="dt_view_mode"
    )

    section_title(T("sec_raw"))
    if "Wide" in dt_view:
        st.markdown(f'<div class="sec-sub">{L("One row per survey event. Columns show each of the 56 recorded item types plus event metadata—exactly like the original Excel format. Zero = item was not found that visit.")}</div>', unsafe_allow_html=True)

        # Build pivot: one row per event, items as columns
        if "trash_item" in lf.columns and "n" in lf.columns and "event_id" in lf.columns:
            # Get event metadata
            meta_cols = [c for c in ["event_id","date","site_label","surveyed_m2","recorder","seg"] if c in lf.columns]
            meta = lf[meta_cols].drop_duplicates("event_id").copy()
            meta["date_str"] = meta["date"].dt.strftime("%Y-%m-%d") if "date" in meta.columns else ""

            # Build group-prefixed item key to avoid duplicates
            # (e.g. "Bottles" appears in Beer, Liquor, Soda, Water, Sports Drinks, Juice)
            lf_wide = lf.copy()
            lf_wide["item_col"] = lf_wide["trash_group"].fillna("") + "—" + lf_wide["trash_item"].fillna("")

            # Build ordered column list matching Excel group order
            item_order = []
            for grp, items in TRASH_GROUPS.items():
                for item in items:
                    col_name = f"{grp}—{item}"
                    item_order.append(col_name)

            # Pivot using the prefixed key—no duplicates possible
            pivot = lf_wide.pivot_table(
                index="event_id", columns="item_col", values="n", aggfunc="sum", fill_value=0
            ).reset_index()
            pivot.columns.name = None

            # Reorder columns to match Excel protocol order
            available_items = [i for i in item_order if i in pivot.columns]
            extra_items = [c for c in pivot.columns if c != "event_id" and c not in item_order]
            pivot = pivot[["event_id"] + available_items + extra_items]

            # Merge with metadata
            meta_sm = meta[["event_id","date_str","site_label","surveyed_m2"]].copy() if "surveyed_m2" in meta.columns else meta[["event_id","date_str","site_label"]].copy()
            meta_sm.columns = ["Event ID","Date","Location"] + (["Area (m²)"] if "surveyed_m2" in meta.columns else [])
            pivot = pivot.rename(columns={"event_id":"Event ID"})
            wide = meta_sm.merge(pivot, on="Event ID", how="left")
            wide = wide.sort_values("Date", ascending=False).reset_index(drop=True)
            wide.index = range(1, len(wide)+1)
            st.dataframe(wide, use_container_width=True, height=580)
            tbl_note(
                f"Showing {len(wide):,} events × {len(wide.columns)-1} columns. "
                "Columns follow the Excel survey protocol order. "
                "Each number = count of that item found during that event. "
                "0 = item was not recorded (not necessarily absent). "
                "Scroll right to see all 56 item columns. The rows shown here also follow the current analysis scope selector above."
            )
        else:
            st.info("Wide format requires item-level data. Check filters.")
    else:
        st.markdown('<div class="sec-sub">One row per trash item category per survey event. Use column headers to sort. Maximum 5,000 rows displayed.</div>', unsafe_allow_html=True)
        cols=[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in lf.columns]
        rename={"event_id":"Event ID","date":"Date","seg":"Segment","site_label":"Location",
                "trash_group":"Category","trash_item":"Item","n":"Count","surveyed_m2":"Area (m2)","recorder":"Recorder"}
        disp=lf[cols].rename(columns=rename).sort_values(["Date","Event ID"],na_position="last").head(5000)
        disp.index=range(1,len(disp)+1)
        st.dataframe(disp, use_container_width=True, height=560)
        tbl_note(f"Showing {min(len(lf),5000):,} of {len(lf):,} rows matching current filters. Each row = one item type at one survey event. Switch to Wide format above to see all items as columns like the original Excel sheet.")

    section_title(T("sec_filt_cat"))
    st.markdown('<div class="sec-sub">Aggregated view of the filtered records above, grouped by trash category.</div>', unsafe_allow_html=True)
    cat_color_legend()
    sum_cat=lf.groupby("trash_group")["n"].agg(Total="sum",Records="count").reset_index()
    sum_cat["% of Filtered Total"]=(100*sum_cat["Total"]/max(sum_cat["Total"].sum(),1)).round(1)
    sum_cat=sum_cat.sort_values("Total",ascending=False).reset_index(drop=True)
    sum_cat.index=range(1,len(sum_cat)+1)
    sum_cat.columns=["Category","Total Items","# Records","% of Filtered Total"]
    st.dataframe(sum_cat, use_container_width=True, height=360)
    tbl_note("This table summarizes the filtered records shown above. Change the scope selector or filters to update both this table and the raw records.")

    section_title(T("sec_filt_loc"))
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
    is_vol = prof.get("is_volunteer", False)
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    if is_vol:
        # Volunteer banner
        st.markdown(f'''<div style="background:{C["green"]}0f;border:1px solid {C["green"]}30;
        border-radius:8px;padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:14px;">
        <div style="width:10px;height:10px;border-radius:50%;background:{C["mint"]};flex-shrink:0;"></div>
        <div style="font-size:13px;color:{C["text"]};line-height:1.6;">
        Volunteer session: <strong>{prof.get("full_name","")}</strong>
        {" · " + prof.get("volunteer_org","") if prof.get("volunteer_org") else ""}
        &nbsp;·&nbsp; You can submit survey counts only.
        To access all features, <a href="/" style="color:{C["green"]};font-weight:600;">sign in with a staff account</a>.
        </div></div>''', unsafe_allow_html=True)
        page_banner(
            "Volunteer Survey Entry",
            "Submit Your Trash Counts",
            "Thank you for volunteering with the Sonoran Institute! Fill in the counts for each item found during your survey plot. Your submission goes directly into the live database.",
            "https://sonoraninstitute.org/files/BHatch_02042018_1152-1600x900.jpg"
        )
    else:
        page_banner(
            "Field Data Entry",
            "Survey Data Entry & Management",
            "Submit new survey entries and manage existing records. All changes are saved directly to the live database and reflected in every chart immediately.",
            "https://sonoraninstitute.org/files/BHatch_02042018_1152-1600x900.jpg"
        )

    if is_vol:
        # Volunteers only see the entry form—no tabs, no manage section
        entry_tab = st.container()
        manage_tab = None
    else:
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
                recorder=ec4.selectbox("Recorder",[""] + TEAM + ["Other—type below"])
                ec5,ec6=st.columns([2,2])
                existing=sorted(long["site_label"].dropna().astype(str).unique().tolist())
                site_sel=ec5.selectbox("Survey Location (existing)",[""] + existing)
                site_new=ec6.text_input("Or enter a new location name")
                # Always render the name field—Streamlit forms don't re-render on selectbox change
                # Field is always visible; label makes clear it's only needed for 'Other'
                rec_other = st.text_input(
                    'Full name (required if "Other" selected above)',
                    placeholder='Type your full name here',
                    help='Only needed when "Other—type below" is selected in the Recorder field above.',
                    key='rec_other_always'
                )
                st.markdown('</div>', unsafe_allow_html=True)

                recorder_final = rec_other.strip() if (rec_other.strip() and recorder == 'Other—type below') else (recorder if recorder and recorder != 'Other—type below' else '')
                site_final = site_new.strip() if site_new.strip() else site_sel
                site_final=site_new.strip() if site_new.strip() else site_sel

                st.markdown(f'''<div class="form-sec">
                <div class="form-sec-title">Trash Item Counts</div>
                <div style="font-size:12.5px;color:{C["muted"]};margin-bottom:14px;line-height:1.6;">
                Enter the count for each item found during the survey. Leave at 0 if the item was not present.
                Each category is labeled with its environmental classification.
                <span style="color:{C["water"]};font-weight:700;">Blue</span> = Recyclable &nbsp;
                <span style="color:{C["brick"]};font-weight:700;">Red</span> = Health Hazard &nbsp;
                <span style="color:{C["amber"]};font-weight:700;">Amber</span> = Floatable &nbsp;
                <span style="color:{C["green"]};font-weight:700;">Green</span> = Other
                </div>''', unsafe_allow_html=True)

                counts = {}
                # Group categories by classification for smarter visual ordering
                ENTRY_ORDER = [
                    ("Food & Beverage", ["Food Packaging","Cups","Beer","Liquor","Soda","Water","Sports Drinks","Juice"]),
                    ("Litter & Debris",  ["Plastic Bags","Misc","Paper Litter","Clothing","Nicotine"]),
                    ("Health Hazards",   ["Rx, Drugs","Toiletries"]),
                    ("Large & Bulk",     ["Construction","Appliances","Auto"]),
                    ("Other",            ["Toys, Games"]),
                ]
                for section_label, grp_list in ENTRY_ORDER:
                    st.markdown(
                        f'<div style="font-family:DM Mono,monospace;font-size:9px;letter-spacing:2px;' +
                        f'text-transform:uppercase;color:{C["muted"]};margin:18px 0 6px;padding-bottom:4px;' +
                        f'border-bottom:1px solid {C["sand3"]};">{section_label}</div>',
                        unsafe_allow_html=True
                    )
                    for grp_name in grp_list:
                        if grp_name not in TRASH_GROUPS: continue
                        items = TRASH_GROUPS[grp_name]
                        # Color by classification
                        grp_color = (
                            C["water"] if grp_name in RECYCLABLE_GROUPS else
                            C["brick"] if grp_name in HEALTH_HAZARD_GROUPS else
                            C["amber"] if grp_name in FLOATABLE_GROUPS else
                            C["green"]
                        )
                        # Display group header with color dot
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:8px;margin:10px 0 6px;">' +
                            f'<div style="width:8px;height:8px;border-radius:50%;background:{grp_color};flex-shrink:0;"></div>' +
                            f'<span style="font-size:12px;font-weight:700;color:{C["text"]};letter-spacing:.3px;">{grp_name}</span>' +
                            '</div>',
                            unsafe_allow_html=True
                        )
                        n = min(4, len(items))
                        cols = st.columns(n)
                        for idx, item in enumerate(items):
                            with cols[idx % n]:
                                counts[item] = st.number_input(
                                    item, min_value=0, value=0, step=1,
                                    key=f"c_{grp_name}_{item}"
                                )
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
                        "submitted_by": prof.get("full_name","Unknown"),
                        "submitted_by_username": prof.get("username",""),
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
                "Review Your Entry: Verify Everything Before Submitting" +
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
        f'<div style="background:white;border:1px solid {C["sand3"]};border-radius:8px;padding:14px 16px;">' +
        f'<div style="font-size:9px;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:1.5px;color:{C["muted"]};margin-bottom:6px;">Submitted By</div>' +
        f'<div style="font-size:1rem;font-family:Cormorant Garamond,serif;font-weight:700;color:{C["green"]};">{snap.get("submitted_by","Unknown")}</div>' +
        f'<div style="font-size:10px;color:{C["muted"]};">@{snap.get("submitted_by_username","")}</div></div>' +
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

            # Items recorded—only non-zero
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
                            "surveyed_m2":float(snap["area_m2"]) if snap["area_m2"] else None,
                            "submitted_by":snap.get("submitted_by",""),
                        }).execute()
                        all_counts=snap["counts"]
                        rows=[{"event_id":int(snap["event_id"]),"trash_group":g,"trash_item":item,"count_value":float(v)}
                              for g,items in TRASH_GROUPS.items() for item in items if (v:=all_counts.get(item,0)) and v>0]
                        if rows: sb.table("trash_counts").insert(rows).execute()
                        load_data.clear()
                        st.session_state["entry_step"]=1
                        st.session_state["entry_snapshot"]=None
                        st.success(
                            f"Saved—Event {snap['event_id']} · {snap['site_final']} · "
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
    if not is_vol and manage_tab is not None:
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
        # Pull recorder info from site_events for "Added By" column
        if not se.empty and "recorder" in se.columns:
            se_rec = se[["event_id","recorder"]].drop_duplicates("event_id")
            se_rec["event_id"] = se_rec["event_id"].astype(str)
        else:
            se_rec = pd.DataFrame(columns=["event_id","recorder"])
        # Also pull submitted_by if available
        if not se.empty and "submitted_by" in se.columns:
            se_sub = se[["event_id","submitted_by"]].drop_duplicates("event_id")
            se_sub["event_id"] = se_sub["event_id"].astype(str)
        else:
            se_sub = pd.DataFrame(columns=["event_id","submitted_by"])

        ev_summary = long.groupby(["event_id","date","site_label"]).agg(
            total_items=("n","sum"),
            categories=("trash_group","nunique")
        ).reset_index()
        ev_summary["event_id"] = ev_summary["event_id"].astype(str)
        ev_summary["date_str"] = ev_summary["date"].dt.strftime("%B %d, %Y").fillna("Unknown date")
        ev_summary = ev_summary.merge(se_rec, on="event_id", how="left")
        ev_summary = ev_summary.merge(se_sub, on="event_id", how="left")
        # Build "Added by" display: prefer submitted_by, fall back to recorder
        ev_summary["added_by"] = ev_summary["submitted_by"].fillna("").str.strip()
        no_sub = ev_summary["added_by"] == ""
        ev_summary.loc[no_sub, "added_by"] = ev_summary.loc[no_sub, "recorder"].fillna("Unknown")
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
        disp_ev = ev_filtered[["event_id","date_str","site_label","added_by","total_items","categories"]].copy()
        disp_ev.columns = ["Event ID","Date","Location","Added By","Total Items","Categories Recorded"]
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

        # ── ADD NEW CATEGORY ─────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        section_title("Add New Survey Category")
        st.markdown(
            f'<div style="font-size:13px;color:{C["muted"]};line-height:1.75;margin-bottom:16px;">'
            'The 19 survey categories are fixed in the field protocol, but new items can be added '
            'to an existing category, or a brand new category group can be created here. '
            'New entries appear immediately in the Data Entry form for all staff. '
            'Confirm with Luke Cole before adding groups to ensure naming aligns with field protocol.'
            '</div>',
            unsafe_allow_html=True
        )

        # Show existing custom categories
        try:
            existing_cc = pd.DataFrame(get_sb().table("custom_categories")
                .select("group_name,item_name,created_by,created_at")
                .order("created_at", desc=False).execute().data or [])
            if not existing_cc.empty:
                section_title("Custom Categories Already Added")
                disp_cc = existing_cc.copy()
                disp_cc.columns = ["Category Group","Item Name","Added By","Date Added"]
                disp_cc.index = range(1, len(disp_cc)+1)
                st.dataframe(disp_cc, use_container_width=True, height=min(300, 52+len(disp_cc)*35))
        except Exception:
            pass

        st.markdown(
            f'<div style="background:{C["sand"]};border:1px solid {C["sand3"]};border-radius:8px;' +
            f'padding:18px 20px;margin-top:12px;">',
            unsafe_allow_html=True
        )
        with st.form("add_category_form"):
            st.markdown(f'<div class="form-sec-title">New Category / Item</div>', unsafe_allow_html=True)
            nc1, nc2 = st.columns(2)

            # Group: either pick existing or type new
            all_existing_groups = sorted(list(TRASH_GROUPS.keys()))
            with nc1:
                grp_choice = st.selectbox(
                    "Category Group",
                    ["— Select existing group —", "+ Create new group"] + all_existing_groups,
                    help="Pick an existing group to add an item to it, or create a completely new group."
                )
            with nc2:
                new_grp_name = st.text_input(
                    "New group name (if creating new)",
                    placeholder="e.g. PPE & Safety Equipment",
                    help="Only fill this if you selected '+ Create new group' above."
                )

            new_item_name = st.text_input(
                "Item name *",
                placeholder="e.g. Face masks, N95 respirators",
                help="The specific item type. Be precise—this will appear on survey forms and in all charts."
            )
            new_cat_note = st.text_area(
                "Reason for adding (optional)",
                height=70,
                placeholder="e.g. Observed increasing volume of PPE waste since 2022, added per Luke Cole field note."
            )

            if st.form_submit_button("Add to Survey Protocol", use_container_width=True):
                # Determine final group name
                if grp_choice == "— Select existing group —":
                    st.error("Please select a category group.")
                elif grp_choice == "+ Create new group":
                    final_group = new_grp_name.strip()
                    if not final_group:
                        st.error("Please enter a name for the new group.")
                        final_group = None
                else:
                    final_group = grp_choice

                final_item = new_item_name.strip()
                if not final_item:
                    st.error("Item name is required.")
                    final_group = None

                if final_group and final_item:
                    # Check for duplicate
                    existing_items = TRASH_GROUPS.get(final_group, [])
                    if final_item in existing_items:
                        st.warning(f"'{final_item}' already exists in {final_group}.")
                    else:
                        try:
                            get_sb().table("custom_categories").insert({
                                "group_name": final_group,
                                "item_name": final_item,
                                "created_by": prof.get("full_name","Unknown"),
                                "created_at": datetime.now().isoformat(),
                            }).execute()
                            load_data.clear()
                            st.success(
                                f"Added: **{final_item}** → **{final_group}** category. "
                                "It will appear in the Data Entry form immediately after the page refreshes."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not save: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════
elif page == "Export":
    page_banner(T("ex_ey"), T("ex_title"), T("ex_sub"), "https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg")
    st.markdown('<div class="body fade-up">', unsafe_allow_html=True)

    long_exp=long[[c for c in ["event_id","date","seg","site_label","trash_group","trash_item","n","surveyed_m2","recorder"] if c in long.columns]].copy()
    long_exp=long_exp.rename(columns={"n":"count","seg":"river_segment","site_label":"location"})

    et_exp=make_et(long)

    site_exp=long.groupby(["site_label","seg"]).agg(total=("n","sum"),events=("event_id","nunique"),avg=("n","mean")).reset_index()
    site_exp=site_exp.sort_values("total",ascending=False)

    exports=[
        ("Long Format—Every Record",long_exp,"scr_trash_long_format.csv",
         "One row per item category per survey event. The most complete format—best for custom analysis in R, Python, or Excel pivot tables. Contains every count entry with its associated location, date, and segment.",
         f"{len(long_exp):,} rows · {len(long_exp.columns)} columns"),
        ("Event Totals",et_exp,"scr_trash_event_totals.csv",
         "One row per survey event with total item count and density (items/m² where area data is available). Best for comparing events or plotting overall trends without needing item-level detail.",
         f"{len(et_exp):,} rows · {len(et_exp.columns)} columns"),
        ("Site Summary",site_exp,"scr_trash_site_summary.csv",
         "One row per survey location with total items, number of events, and average. Best for spatial analysis, prioritizing cleanup sites, or importing into GIS software.",
         f"{len(site_exp):,} rows · {len(site_exp.columns)} columns"),
    ]
    for label,df_exp,fname,desc,sz in exports:
        st.markdown('<div style="background:#fff;border:1px solid '+C['sand3']+';border-radius:10px;padding:28px;margin-bottom:32px;box-shadow:0 2px 10px rgba(0,0,0,.04);">', unsafe_allow_html=True)
        ec1,ec2=st.columns([3,1])
        with ec1:
            st.markdown(f'<div class="sec-hd">{label}</div><div class="sec-sub">{desc}</div>', unsafe_allow_html=True)
            st.caption(sz)
        with ec2:
            if df_exp is not None and len(df_exp)>0:
                st.download_button(L("Download CSV"),data=df_exp.to_csv(index=False).encode(),
                    file_name=fname,mime="text/csv",use_container_width=True,key=f"dl_{fname}")
        if df_exp is not None and len(df_exp)>0:
            with st.expander(L("Preview first 30 rows")):
                st.dataframe(df_exp.head(30), use_container_width=True, height=220)
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# ABOUT
# ══════════════════════════════════════════════════════════════════
elif page == "About":

    st.markdown('<div class="about-shell fade-up">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="about-hero">
    <div style="position:absolute;inset:0;
    background:url('https://sonoraninstitute.org/files/246-Santa-Cruz-River-%C2%A9jeffsmith2014-1600x900.jpg')
    center/cover no-repeat;opacity:.18;border-radius:12px;"></div>
    <div style="position:relative;z-index:2;">
    <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:3px;text-transform:uppercase;
    color:{C['mint']};margin-bottom:16px;">{T("about_hero_eyebrow")}</div>
    <h1 style="font-family:'Cormorant Garamond',serif;font-size:3rem;font-weight:700;color:white;
    line-height:1.1;letter-spacing:-.02em;margin:0 0 16px;max-width:820px;">
    {T("about_hero_title")}</h1>
    <p style="font-size:15px;color:rgba(255,255,255,.75);max-width:680px;line-height:1.85;margin:0;">
    {T("about_hero_sub")}
    </p></div></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="about-body fade-up">', unsafe_allow_html=True)
    section_title(T("why_river_title"))
    c1, c2 = st.columns([3,2])
    with c1:
        st.markdown(f"""<div style="font-size:14px;color:{C['text']};line-height:1.9;">
        <p style="margin:0 0 14px;">{T("about_p1")}</p>
        <p style="margin:0 0 14px;">{T("about_p2")}</p>
        <p style="margin:0 0 14px;">{T("about_p3")}</p>
        <p style="margin:0;">{T("about_p4")}</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <img src="https://sonoraninstitute.org/files/BHatch_02042018_1036-1600x900.jpg"
        style="width:100%;border-radius:10px;margin-bottom:10px;box-shadow:0 4px 18px rgba(0,0,0,.15);">
        <div style="font-size:11px;color:{C['muted']};font-style:italic;text-align:center;margin-bottom:14px;">
        {T("about_photo_caption")}</div>

        """, unsafe_allow_html=True)

    # Horizontal scrollable photo carousel
    carousel_photos = [
        ("https://sonoraninstitute.org/files/Hatcher_181106_1751-scaled.jpg",
         "Annual fish survey, Santa Cruz River · ©Bill Hatcher / Sonoran Institute, 2020"),
        ("https://sonoraninstitute.org/files/Hatcher_181128_404-1600x900.jpg",
         "Riparian habitat restoration · ©Bill Hatcher / Sonoran Institute"),
        ("https://sonoraninstitute.org/files/BHatch_02042018_1116-1600x900.jpg",
         "Santa Cruz River, April 2018 · ©Bill Hatcher / Sonoran Institute"),
        ("https://sonoraninstitute.org/files/BHatch_02042018_1152-1600x900.jpg",
         "River corridor near Carmen, AZ · ©Bill Hatcher / Sonoran Institute"),
        ("https://sonoraninstitute.org/files/IMG_20190702_115922-1-1600x900.jpg",
         "Field survey crew, Santa Cruz River corridor, 2019"),
        ("https://sonoraninstitute.org/files/246-Santa-Cruz-River-%C2%A9jeffsmith2014-1600x900.jpg",
         "Santa Cruz River · ©Jeff Smith / Sonoran Institute, 2014"),
    ]
    imgs_html = "".join(
        f'<div style="flex:0 0 320px;scroll-snap-align:start;">' +
        f'<img src="{url}" style="width:320px;height:210px;object-fit:cover;' +
        f'border-radius:10px;box-shadow:0 3px 14px rgba(0,0,0,.13);">' +
        f'<div style="font-size:11px;color:{C["muted"]};font-style:italic;' +
        f'text-align:center;margin-top:7px;line-height:1.5;padding:0 4px;">{cap}</div></div>'
        for url, cap in carousel_photos
    )
    st.markdown(
        '<style>.scr2{scrollbar-width:thin}.scr2::-webkit-scrollbar{height:5px}'
        '</style>'
        f'<div class="scr2" style="display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:10px;">'
        + imgs_html +
        f'</div><div style="text-align:center;font-size:11px;color:{C["muted"]};margin-top:6px;">{T("about_scroll")}</div>',
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    section_title(T("about_db_title"))

    s1,s2,s3,s4 = st.columns(4)
    for col, val, lbl, note in zip([s1,s2,s3,s4],
        ["32,144+","395+","136","2020–2024"],
        [T("stat_items_lbl"),T("stat_events_lbl"),T("stat_locs_lbl"),T("stat_period_lbl")],
        [T("stat_items_note"),T("stat_events_note"),T("stat_locs_note"),T("stat_period_note")]):
        with col:
            st.markdown(f"""<div style="background:white;border:1px solid {C['sand3']};border-radius:10px;
            padding:24px 20px 20px;text-align:center;position:relative;overflow:hidden;
            box-shadow:0 2px 10px rgba(0,0,0,.04);">
            <div style="position:absolute;top:0;left:0;right:0;height:3px;
            background:linear-gradient(90deg,{C['green']},{C['mint']});"></div>
            <div style="font-family:'Cormorant Garamond',serif;font-size:2rem;font-weight:700;
            color:{C['green']};line-height:1.1;">{val}</div>
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
            color:{C['muted']};font-family:'DM Mono',monospace;margin-top:12px;">{lbl}</div>
            <div style="font-size:11px;color:{C['muted']};margin-top:6px;line-height:1.4;">{note}</div>
            </div>""", unsafe_allow_html=True)

    _ab1, _ab2 = st.columns([1, 2])
    with _ab1:
        st.markdown(f"""
        <img src="https://sonoraninstitute.org/files/IMG_20190702_115922-1-1600x900.jpg"
          style="width:100%;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.15);display:block;margin-top:8px;">
        <div style="font-size:11px;color:{C['muted']};font-style:italic;text-align:center;margin-top:8px;line-height:1.5;">
          {T("about_field_caption")}</div>""", unsafe_allow_html=True)
    with _ab2:
        st.markdown(f"""
        <div style="font-size:14px;color:{C['text']};line-height:1.9;padding-top:8px;">
          <p style="margin:0 0 16px;">{T("about_db_p1")}</p>
          <p style="margin:0 0 16px;">{T("about_db_p2")}</p>
          <p style="margin:0 0 16px;">{T("about_db_p3")}</p>
          <p style="margin:0;">{T("about_db_p4")}</p>
        </div>""", unsafe_allow_html=True)

    section_title(T("about_why_title"))

    reasons = [
        (C["water"],  T("reason_reg_title"),     T("reason_reg")),
        (C["green"],  T("reason_grant_title"),   T("reason_grant")),
        (C["amber"],  T("reason_cleanup_title"), T("reason_cleanup")),
        (C["brick"],  T("reason_health_title"),  T("reason_health")),
        (C["sage"],   T("reason_policy_title"),  T("reason_policy")),
        (C["earth"],  T("reason_refuge_title"),  T("reason_refuge")),
    ]
    rc1, rc2 = st.columns(2)
    for i, (color, title, text) in enumerate(reasons):
        with (rc1 if i%2==0 else rc2):
            st.markdown(f"""<div style="background:white;border:1px solid {C['sand3']};
            border-left:4px solid {color};border-radius:0 10px 10px 0;
            padding:16px 18px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.04);">
            <div style="font-family:'Cormorant Garamond',serif;font-size:1rem;font-weight:700;
            color:{C['text']};margin-bottom:5px;">{title}</div>
            <div style="font-size:13px;color:{C['muted']};line-height:1.7;">{text}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown(f"""<div style="background:white;border:1px solid {C['sand3']};border-radius:10px;
    padding:20px 36px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.04);">
    <div style="font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:600;
    color:{C['green']};line-height:1.3;margin-bottom:14px;font-style:italic;max-width:700px;margin:0 auto 14px;">
    {T("about_quote")}</div>
    <div style="font-size:11px;color:{C['muted']};font-family:'DM Mono',monospace;
    text-transform:uppercase;letter-spacing:1px;">{T("about_quote_attr")}</div>
    </div>""", unsafe_allow_html=True)

    section_title(T("about_team_title"))
    tc1, tc2, tc3 = st.columns(3)
    for col, name, role, desc, color in zip([tc1,tc2,tc3],
        ["Luke Cole","Kevin Robles",T("team_name_field")],
        [T("team_role_luke"),T("team_role_kevin"),T("team_role_field")],
        [T("team_desc_luke"),T("team_desc_kevin"),T("team_desc_field")],
        [C["green"],C["water"],C["sage"]]):
        with col:
            st.markdown(f"""<div style="background:white;border:1px solid {C['sand3']};
            border-top:4px solid {color};border-radius:10px;
            padding:28px;margin-bottom:20px;box-shadow:0 2px 10px rgba(0,0,0,.04);">
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.05rem;font-weight:700;
            color:{C['text']};margin-bottom:12px;">{name}</div>
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;
            color:{color};font-family:'DM Mono',monospace;margin-bottom:16px;">{role}</div>
            <div style="font-size:13.5px;color:{C['muted']};line-height:1.95;letter-spacing:.01em;">{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div style="background:{C['sand']};border:1px solid {C['sand3']};border-radius:10px;
    padding:16px 22px;margin-top:12px;font-size:13px;color:{C['muted']};line-height:1.8;">
    <strong style="color:{C['text']};">Sonoran Institute</strong> · 5049 E Broadway Blvd., Suite 127,
    Tucson, AZ 85711 · (520) 290-0828 ·
    <a href="https://sonoraninstitute.org/card/santacruz/" target="_blank"
    style="color:{C['green']};text-decoration:none;font-weight:600;">
    sonoraninstitute.org/card/santacruz</a></div>""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────
st.markdown(f"""<div class="ftr"><div class="ftr-in">

  <!-- Row 1: Logo + tagline + social icons -->
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:24px;margin-bottom:20px;">
    <div>
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">
        <img src="{LOGO_W}" style="height:36px;opacity:.85;">
        <div>
          <div style="font-family:'Cormorant Garamond',serif;font-size:1.05rem;font-weight:700;
          color:rgba(255,255,255,1);line-height:1.2;">Sonoran Institute</div>
          <div style="font-family:'DM Mono',monospace;font-size:8.5px;letter-spacing:2px;
          text-transform:uppercase;color:rgba(255,255,255,.95);margin-top:2px;">{L("Santa Cruz River Program")}</div>
        </div>
      </div>
      <div class="ftr-copy">
        5049 E Broadway Blvd., Suite 127 · Tucson, AZ 85711<br>
        {T("ftr_phone")}: (520) 290-0828
      </div>
    </div>
    <div style="text-align:right;">
      <span class="ftr-section-lbl">{T("ftr_connect")}</span>
      <div>
        <a href="https://www.facebook.com/SonoranInstitute/" target="_blank" class="ftr-social-icon" title="Facebook">f</a>
        <a href="https://twitter.com/SonoranInst/" target="_blank" class="ftr-social-icon" title="Twitter / X">𝕏</a>
        <a href="https://www.youtube.com/@SonoranInstituteFlix" target="_blank" class="ftr-social-icon" title="YouTube">▶</a>
        <a href="https://www.instagram.com/sonoraninstitute/" target="_blank" class="ftr-social-icon" title="Instagram">◈</a>
      </div>
    </div>
  </div>

  <hr class="ftr-divider">

  <!-- Row 2: Navigation links -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:22px 36px;margin-bottom:20px;">
    <div>
      <span class="ftr-section-lbl">{T("ftr_our_work")}</span>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/card/santacruz/" target="_blank" class="ftr-a ftr-copy">{L("Santa Cruz River")}</a>
        <a href="https://sonoraninstitute.org/card/colorado-river-delta-program/" target="_blank" class="ftr-a ftr-copy">{L("Colorado River Delta")}</a>
        <a href="https://sonoraninstitute.org/card/growingwatersmart/" target="_blank" class="ftr-a ftr-copy">{L("Growing Water Smart")}</a>
        <a href="https://sonoraninstitute.org/2022/one-basin/" target="_blank" class="ftr-a ftr-copy">{L("One Basin")}</a>
        <a href="https://sonoraninstitute.org/resources/" target="_blank" class="ftr-a ftr-copy">{L("Resources")}</a>
      </div>
    </div>
    <div>
      <span class="ftr-section-lbl">{T("ftr_about_us")}</span>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/our-story/mission-vision/" target="_blank" class="ftr-a ftr-copy">{T("ftr_mission")}</a>
        <a href="https://sonoraninstitute.org/our-story/people/" target="_blank" class="ftr-a ftr-copy">{T("ftr_people")}</a>
        <a href="https://sonoraninstitute.org/our-story/board/" target="_blank" class="ftr-a ftr-copy">{L("Board")}</a>
        <a href="https://sonoraninstitute.org/our-story/partners/" target="_blank" class="ftr-a ftr-copy">{L("Partners")}</a>
        <a href="https://sonoraninstitute.org/our-story/financials/" target="_blank" class="ftr-a ftr-copy">{L("Financials")}</a>
        <a href="https://sonoraninstitute.org/careers/" target="_blank" class="ftr-a ftr-copy">{L("Careers")}</a>
      </div>
    </div>
    <div>
      <span class="ftr-section-lbl">{T("ftr_updates")}</span>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/sign-up/" target="_blank" class="ftr-a ftr-copy">{T("ftr_newsletter")}</a>
        <a href="https://sonoraninstitute.org/donations/membership/" target="_blank" class="ftr-a ftr-copy">{T("ftr_sustainer")}</a>
        <a href="https://sonoraninstitute.org/blogs/" target="_blank" class="ftr-a ftr-copy">{T("ftr_blog")}</a>
        <a href="https://sonoraninstitute.org/events/" target="_blank" class="ftr-a ftr-copy">{T("ftr_events")}</a>
      </div>
      <span class="ftr-section-lbl" style="margin-top:16px;">{T("ftr_resources")}</span>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/category/sonoran-post/" target="_blank" class="ftr-a ftr-copy">{L("Sonoran Updates")}</a>
        <a href="https://sonoraninstitute.org/resilient-west/" target="_blank" class="ftr-a ftr-copy">Resilient West</a>
        <a href="https://sonoraninstitute.org/careers/" target="_blank" class="ftr-a ftr-copy">{L("Careers")}</a>
        <a href="https://sonoraninstitute.org/contact/" target="_blank" class="ftr-a ftr-copy">{T("ftr_contact")}</a>
      </div>
    </div>
    <div>
      <span class="ftr-section-lbl">{T("ftr_support")}</span>
      <div style="margin-bottom:12px;">
        <a href="https://sonoraninstitute.org/support/donate/" target="_blank"
        style="display:inline-block;background:{C["mint"]};color:white;font-family:'DM Mono',monospace;
        font-size:9.5px;letter-spacing:1.5px;text-transform:uppercase;padding:8px 18px;
        border-radius:20px;text-decoration:none;transition:background .15s;">
        Donate →</a>
      </div>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/donations/riversocks/" target="_blank" class="ftr-a ftr-copy">#RiverSocks</a>
        <a href="https://sonoraninstitute.org/2024/ar-mer/" target="_blank" class="ftr-a ftr-copy">{L("Endangered Rivers Report")}</a>
        <a href="http://santacruzriver.org/letter-of-support/" target="_blank" class="ftr-a ftr-copy">{L("Urban Wildlife Refuge")}</a>
      </div>
      <span class="ftr-section-lbl" style="margin-top:16px;">{T("ftr_reports")}</span>
      <div class="ftr-links-row" style="flex-direction:column;gap:5px;">
        <a href="https://sonoraninstitute.org/files/a-living-river-2025.pdf" target="_blank" class="ftr-a ftr-copy">{L("Downtown Tucson to Marana 2025")}</a>
        <a href="https://sonoraninstitute.org/files/a-living-river-supplementary-2025.pdf" target="_blank" class="ftr-a ftr-copy">{L("Supplementary Data 2025")}</a>
        <a href="https://sonoraninstitute.org/files/un-rio-vivo-2025.pdf" target="_blank" class="ftr-a ftr-copy">{L("Un Río Vivo—Español 2025")}</a>
      </div>
    </div>
  </div>

  <hr class="ftr-divider">

  <!-- Row 3: Bottom bar -->
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
    <div style="font-family:DM Mono,monospace;font-size:10px;color:rgba(255,255,255,.90);letter-spacing:.5px;">
      {T("ftr_copyright")}
    </div>
    <div style="font-family:DM Mono,monospace;font-size:10px;text-align:right;">
      <a href="https://sonoraninstitute.org/card/santacruz/" target="_blank"
         style="color:rgba(255,255,255,.95);text-decoration:none;letter-spacing:.3px;
         transition:color .15s;"
         onmouseover="this.style.color='#ffffff'" onmouseout="this.style.color='rgba(255,255,255,.55)'">
        sonoraninstitute.org/card/santacruz
      </a>
    </div>
  </div>

</div></div>""", unsafe_allow_html=True)

with st.expander(T("acct_session")):
    st.markdown(
        f'<div style="font-size:13px;color:{C["text"]};margin-bottom:8px;">' +
        f'{T("acct_signed_in")} <strong>{prof.get("full_name","")}</strong> &nbsp;·&nbsp; ' +
        f'{T("acct_username")}: <code>{prof.get("username","")}</code> &nbsp;·&nbsp; ' +
        f'{T("acct_role")}: {prof.get("position_title","")}</div>',
        unsafe_allow_html=True
    )
    _a1, _a2, _a3 = st.columns(3)
    with _a1:
        if st.button(T("acct_refresh"), key="_ftr_refresh"): load_data.clear(); st.rerun()
    with _a2:
        if st.button(T("acct_signout"), key="_ftr_signout"):
            st.session_state["auth"]=False; st.session_state["prof"]=None; st.rerun()
    with _a3:
        st.caption(T("acct_signout_note"))
