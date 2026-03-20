import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import re

st.set_page_config(
    page_title="Weekendesk SEO Dashboard",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {font-size:2rem; font-weight:700; color:#FF6B00; margin-bottom:0}
    .sub-header {font-size:1rem; color:#888; margin-top:0}
    .metric-card {background:#fff; border-radius:10px; padding:1rem; border-left:4px solid #FF6B00; box-shadow:0 2px 6px rgba(0,0,0,0.08)}
    .stTabs [data-baseweb="tab"] {font-size:1rem; font-weight:600}
</style>
""", unsafe_allow_html=True)

# ── DONNÉES SEO STATIQUES ─────────────────────────────────────────────────────
SEO_CLICKS_RAW = {
    "Dec-24": 304665,
    "Jan-25": 177076,
    "Feb-25": 168099,
    "Mar-25": 138749,
    "Apr-25": 135189,
    "May-25": 144194,
    "Jun-25": 125659,
    "Jul-25": 158100,
    "Aug-25": 183872,
    "Sep-25": 158867,
    "Oct-25": 224557,
    "Nov-25": 277362,
    "Dec-25": 300356,
    "Jan-26": 143541,
    "Feb-26": 134778,
    "Mar-26": 50700,   # Mars 2026 partiel
}

# ── CLICS HORS MARQUE (non-brand) ─────────────────────────────────────────────
SEO_HORS_MARQUE = {
    "Dec-24": 272173,
    "Jan-25": 146443,
    "Feb-25": 133246,
    "Mar-25": 109981,
    "Apr-25": 108310,
    "May-25": 110358,
    "Jun-25": 97174,
    "Jul-25": 126792,
    "Aug-25": 151396,
    "Sep-25": 128022,
    "Oct-25": 189749,
    "Nov-25": 255439,
    "Dec-25": 280385,
    "Jan-26": 125385,
    "Feb-26": 115359,
    "Mar-26": 42996,   # partiel
}

# ── CLICS MARQUE (brand) ──────────────────────────────────────────────────────
SEO_MARQUE = {
    "Dec-24": 32492,
    "Jan-25": 30633,
    "Feb-25": 34853,
    "Mar-25": 28768,
    "Apr-25": 26879,
    "May-25": 33836,
    "Jun-25": 28485,
    "Jul-25": 31308,
    "Aug-25": 32476,
    "Sep-25": 30845,
    "Oct-25": 34808,
    "Nov-25": 21923,
    "Dec-25": 19971,
    "Jan-26": 18156,
    "Feb-26": 19419,
    "Mar-26": 7704,    # partiel
}

# ── TOP PAGES 2025 ─────────────────────────────────────────────────────────────
TOP_PAGES_2025 = [
    {"page": "Idées WE",    "clics": 897074},
    {"page": "Séjour",      "clics": 616771},
    {"page": "Home",        "clics": 311461},
    {"page": "Hôtels",      "clics": 189581},
    {"page": "Villes",      "clics": 143927},
    {"page": "Last minute", "clics": 106691},
]

MONTH_MAP = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
             "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
MONTH_FR  = {1:"Jan",2:"Fév",3:"Mar",4:"Avr",5:"Mai",6:"Jun",
             7:"Jul",8:"Aoû",9:"Sep",10:"Oct",11:"Nov",12:"Déc"}

BRAND_ORANGE = "#FF6B00"
BRAND_BLUE   = "#1E3A5F"
COLOR_HM     = "#FF6B00"   # orange = hors marque
COLOR_M      = "#2ca02c"   # vert   = marque
PARTIAL_KEY  = "Mar-26"

DELTA_MAP = {
    "Purchases":     "% Δ Purchases",
    "AOV":           "% Δ AOV",
    "Gross Revenue": "% Δ Gross Revenue",
    "GBV":           "% Δ GBV vs LP",
    "CVR":           "% Δ CVR",
    "Sessions":      "% Δ Sessions",
}

def build_seo_df():
    rows = []
    for key, clicks in SEO_CLICKS_RAW.items():
        abbr, yr = key.split("-")
        year  = 2000 + int(yr)
        mnum  = MONTH_MAP[abbr]
        rows.append({
            "date_key":   key,
            "date":       pd.Timestamp(year=year, month=mnum, day=1),
            "month_abbr": abbr,
            "year":       year,
            "month_num":  mnum,
            "seo_clicks": clicks,
            "hm_clicks":  SEO_HORS_MARQUE.get(key, 0),
            "m_clicks":   SEO_MARQUE.get(key, 0),
            "partial":    key == PARTIAL_KEY,
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

MONTH_NAMES_FULL = {
    "january":"Jan","february":"Feb","march":"Mar","april":"Apr",
    "may":"May","june":"Jun","july":"Jul","august":"Aug",
    "september":"Sep","october":"Oct","november":"Nov","december":"Dec"
}

def normalize_date_key(raw):
    """Convertit 'March 2026' ou 'Mar-26' → 'Mar-26'."""
    s = str(raw).strip()
    m = re.match(r'^([A-Za-z]+)\s+(\d{4})$', s)
    if m:
        short = MONTH_NAMES_FULL.get(m.group(1).lower())
        if short:
            return f"{short}-{m.group(2)[2:]}"
    m2 = re.match(r'^([A-Za-z]{3})-(\d{2})$', s)
    if m2:
        return f"{m2.group(1).capitalize()}-{m2.group(2)}"
    return None

def parse_csv(uploaded):
    """Parse le CSV Tableau (unpivot) et renvoie un DataFrame pivoté.
    Seules les lignes Dimension 1 = 'seo' sont conservées."""
    try:
        df = pd.read_csv(uploaded, encoding="utf-8")
    except UnicodeDecodeError:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="latin-1")

    col_map = {}
    for c in df.columns:
        cl = c.strip().lower()
        if "dimension" in cl:
            col_map["dim"] = c
        elif cl == "date":
            col_map["date"] = c
        elif "measure" in cl and "name" in cl:
            col_map["mname"] = c
        elif "measure" in cl and "value" in cl:
            col_map["mvalue"] = c

    missing = [k for k in ["dim","date","mname","mvalue"] if k not in col_map]
    if missing:
        st.error(f"Colonnes manquantes dans le CSV : {missing}. Colonnes trouvées : {list(df.columns)}")
        return None

    # Filtre Dimension 1 = 'seo' uniquement
    df = df[df[col_map["dim"]].astype(str).str.strip().str.lower() == "seo"].copy()
    if df.empty:
        st.warning("Aucune ligne avec Dimension 1 = 'seo' trouvée.")
        return None

    df["date_key"] = df[col_map["date"]].apply(normalize_date_key)
    df = df.dropna(subset=["date_key"])

    df[col_map["mvalue"]] = pd.to_numeric(
        df[col_map["mvalue"]].astype(str).str.replace(",", ".").str.replace(" ", ""),
        errors="coerce"
    )
    df[col_map["mname"]] = df[col_map["mname"]].astype(str).str.strip()

    pivot = df.pivot_table(
        index="date_key",
        columns=col_map["mname"],
        values=col_map["mvalue"],
        aggfunc="first"
    ).reset_index()
    pivot.columns.name = None
    pivot.columns = [c.strip() if isinstance(c, str) else c for c in pivot.columns]
    return pivot

def fmt_num(v, decimals=0):
    if pd.isna(v):
        return "—"
    if decimals == 0:
        return f"{v:,.0f}".replace(",", "\u202f")
    return f"{v:,.{decimals}f}".replace(",", "\u202f")

def delta_arrow(v):
    if pd.isna(v):
        return ""
    return f"{'↑' if v >= 0 else '↓'} {abs(v):.1f}%"

MONTH_TICKS = list(range(1,13))
MONTH_LABELS = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Weekendesk_logo.svg/320px-Weekendesk_logo.svg.png",
             use_column_width=True)
    st.markdown("---")
    st.markdown("### 📂 Importer les données")
    uploaded = st.file_uploader(
        "Fichier CSV (export Tableau)", type=["csv"],
        help="Seules les lignes Dimension 1 = 'seo' sont utilisées."
    )
    st.markdown("---")
    st.markdown("### 🔍 Filtres")
    years_available = sorted({2000+int(k.split("-")[1]) for k in SEO_CLICKS_RAW})
    selected_years = st.multiselect("Années", years_available, default=years_available)
    st.markdown("---")
    st.caption("🏖️ Weekendesk SEO Vision v2.0")

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🏖️ Weekendesk SEO Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Monitoring des performances SEO & Business — Marque / Hors Marque</p>', unsafe_allow_html=True)
st.markdown("---")

# ── BUILD DATA ────────────────────────────────────────────────────────────────
seo_df = build_seo_df()
seo_filtered = seo_df[seo_df["year"].isin(selected_years)]

if seo_df[seo_df["partial"]].shape[0] > 0:
    st.info("ℹ️ Mars 2026 : données partielles (≈ 18 premiers jours du mois).", icon="📅")

biz_df = None
merged_df = None
if uploaded:
    biz_df = parse_csv(uploaded)
    if biz_df is not None:
        merged_df = seo_df.merge(biz_df, on="date_key", how="inner")
        merged_df = merged_df.sort_values("date").reset_index(drop=True)
        if merged_df.empty:
            st.warning("Aucune correspondance entre les dates du CSV et les données SEO.")
            merged_df = None

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab_yoy, tab2, tab3, tab_top = st.tabs([
    "📈 Clics SEO",
    "📊 Comparaison YoY",
    "💼 Performance Business",
    "🔗 Corrélations",
    "🏆 Top Pages 2025",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CLICS SEO (Marque / Hors Marque / Total)
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    # KPIs
    last_full = seo_df[~seo_df["partial"]]
    latest = last_full.iloc[-1]
    prev   = last_full.iloc[-2]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        d = (latest["hm_clicks"] / prev["hm_clicks"] - 1) * 100
        st.metric("Clics Hors Marque (dernier mois)", fmt_num(latest["hm_clicks"]),
                  f"{d:+.1f}% vs mois préc.")
    with col2:
        d = (latest["m_clicks"] / prev["m_clicks"] - 1) * 100
        st.metric("Clics Marque (dernier mois)", fmt_num(latest["m_clicks"]),
                  f"{d:+.1f}% vs mois préc.")
    with col3:
        hm_2025 = seo_df[seo_df["year"] == 2025]["hm_clicks"].sum()
        st.metric("Total Hors Marque 2025", fmt_num(hm_2025))
    with col4:
        hm_ytd = seo_df[seo_df["year"] == 2026]["hm_clicks"].sum()
        hm_same = seo_df[
            (seo_df["year"] == 2025) &
            (seo_df["month_num"].isin(seo_df[seo_df["year"] == 2026]["month_num"]))
        ]["hm_clicks"].sum()
        d_ytd = (hm_ytd / hm_same - 1) * 100 if hm_same else 0
        st.metric("Hors Marque 2026 (YTD)", fmt_num(hm_ytd), f"{d_ytd:+.1f}% YoY")

    st.markdown("---")

    # Sélecteur de séries
    series_choice = st.multiselect(
        "Séries à afficher",
        ["Total SEO", "Hors Marque", "Marque"],
        default=["Total SEO", "Hors Marque", "Marque"],
    )

    series_cfg = {
        "Total SEO":   ("seo_clicks", BRAND_BLUE,   "solid"),
        "Hors Marque": ("hm_clicks",  COLOR_HM,     "solid"),
        "Marque":      ("m_clicks",   COLOR_M,       "dot"),
    }

    st.markdown("#### Évolution des clics SEO par mois")
    fig_line = go.Figure()
    for label in series_choice:
        col_k, color, dash = series_cfg[label]
        for yr in sorted(seo_filtered["year"].unique()):
            sub = seo_filtered[seo_filtered["year"] == yr].copy()
            solid   = sub[~sub["partial"]]
            partial = sub[sub["partial"]]
            trace_name = f"{label} {yr}"
            if not solid.empty:
                fig_line.add_trace(go.Scatter(
                    x=solid["month_num"], y=solid[col_k],
                    mode="lines+markers", name=trace_name,
                    line=dict(color=color, width=2.5, dash=dash),
                    marker=dict(size=7),
                    hovertemplate=f"%{{y:,.0f}} clics<extra>{trace_name}</extra>"
                ))
            if not partial.empty:
                fig_line.add_trace(go.Scatter(
                    x=partial["month_num"], y=partial[col_k],
                    mode="markers", name=f"{trace_name} (partiel)",
                    marker=dict(symbol="circle-open", size=10,
                                color=color, line=dict(width=2)),
                    showlegend=True
                ))
    fig_line.update_layout(
        xaxis=dict(tickvals=MONTH_TICKS, ticktext=MONTH_LABELS),
        yaxis_title="Clics SEO", plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.25), hovermode="x unified",
        height=560
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # Heatmap Hors Marque
    st.markdown("#### Heatmap – Clics Hors Marque")
    hm_pivot = seo_filtered.pivot_table(index="year", columns="month_num",
                                        values="hm_clicks", aggfunc="first")
    hm_pivot.columns = MONTH_LABELS[:len(hm_pivot.columns)]
    fig_hm = px.imshow(hm_pivot, text_auto=True, aspect="auto",
                       color_continuous_scale=[[0,"#fff"],[1, BRAND_ORANGE]],
                       labels=dict(color="Clics HM"))
    fig_hm.update_traces(texttemplate="%{z:,.0f}")
    fig_hm.update_layout(height=200 + 80*len(hm_pivot))
    st.plotly_chart(fig_hm, use_container_width=True)

    # Heatmap Marque
    st.markdown("#### Heatmap – Clics Marque")
    m_pivot = seo_filtered.pivot_table(index="year", columns="month_num",
                                       values="m_clicks", aggfunc="first")
    m_pivot.columns = MONTH_LABELS[:len(m_pivot.columns)]
    fig_mp = px.imshow(m_pivot, text_auto=True, aspect="auto",
                       color_continuous_scale=[[0,"#fff"],[1, COLOR_M]],
                       labels=dict(color="Clics M"))
    fig_mp.update_traces(texttemplate="%{z:,.0f}")
    fig_mp.update_layout(height=200 + 80*len(m_pivot))
    st.plotly_chart(fig_mp, use_container_width=True)

    with st.expander("📋 Tableau des données SEO"):
        disp = seo_filtered[["date_key","year","month_abbr","seo_clicks","hm_clicks","m_clicks","partial"]].copy()
        disp.columns = ["Clé Date","Année","Mois","Total SEO","Hors Marque","Marque","Partiel"]
        st.dataframe(disp.style.format({"Total SEO":"{:,.0f}","Hors Marque":"{:,.0f}","Marque":"{:,.0f}"}),
                     use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB YoY — COMPARAISON 2025 vs 2026
# ═══════════════════════════════════════════════════════════════════════════════
with tab_yoy:
    st.markdown("#### Comparaison YoY – 2025 vs 2026")

    yoy_type = st.radio(
        "Type de clics", ["Total SEO", "Hors Marque", "Marque"], horizontal=True
    )
    yoy_col_map = {
        "Total SEO": ("seo_clicks", "Clics Total SEO"),
        "Hors Marque": ("hm_clicks", "Clics Hors Marque"),
        "Marque": ("m_clicks", "Clics Marque"),
    }
    yoy_col, yoy_label = yoy_col_map[yoy_type]

    df25 = seo_df[seo_df["year"] == 2025].set_index("month_num")[yoy_col]
    df26 = seo_df[seo_df["year"] == 2026].set_index("month_num")[yoy_col]
    common = sorted(set(df25.index) & set(df26.index))

    if common:
        bar_df = pd.DataFrame({
            "Mois": [MONTH_LABELS[m-1] for m in common],
            "2025": [df25[m] for m in common],
            "2026": [df26[m] for m in common],
        })
        bar_df["Δ YoY (%)"] = (bar_df["2026"] / bar_df["2025"] - 1) * 100

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=bar_df["Mois"], y=bar_df["2025"], name="2025",
                                 marker_color="#aec7e8"))
        fig_bar.add_trace(go.Bar(x=bar_df["Mois"], y=bar_df["2026"], name="2026",
                                 marker_color=BRAND_ORANGE))
        fig_bar.update_layout(barmode="group", height=520, plot_bgcolor="white",
                               yaxis_title=yoy_label, hovermode="x unified",
                               title=f"{yoy_label} — 2025 vs 2026")
        st.plotly_chart(fig_bar, use_container_width=True)

        fig_delta = go.Figure(go.Bar(
            x=bar_df["Mois"], y=bar_df["Δ YoY (%)"],
            marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in bar_df["Δ YoY (%)"]],
            text=[f"{v:+.1f}%" for v in bar_df["Δ YoY (%)"]],
            textposition="outside",
        ))
        fig_delta.add_hline(y=0, line_dash="dash", line_color="grey")
        fig_delta.update_layout(
            title=f"Variation YoY % — {yoy_label}",
            yaxis_title="% Δ", plot_bgcolor="white", height=420
        )
        st.plotly_chart(fig_delta, use_container_width=True)
    else:
        st.info("Pas assez de données communes entre 2025 et 2026.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PERFORMANCE BUSINESS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    if merged_df is None:
        st.info(
            "👆 Importe un fichier CSV dans la sidebar pour voir les métriques business.\n\n"
            "**Format attendu :** `Dimension 1 | Date | Measure Names | Measure Values`\n\n"
            "ℹ️ Seules les lignes `Dimension 1 = seo` sont utilisées."
        )
    else:
        METRICS_ABS   = ["Purchases", "AOV", "Gross Revenue", "GBV", "CVR", "Sessions"]
        METRICS_DELTA = ["% Δ Purchases", "% Δ AOV", "% Δ Gross Revenue",
                         "% Δ GBV vs LP", "% Δ CVR", "% Δ Sessions"]

        available_abs   = [m for m in METRICS_ABS   if m in merged_df.columns]
        available_delta = [m for m in METRICS_DELTA if m in merged_df.columns]

        last = merged_df.dropna(subset=available_abs[:1]).iloc[-1] if available_abs else None
        if last is not None:
            st.markdown("#### KPIs — Dernier mois disponible")
            kpi_cols = st.columns(len(available_abs))
            for i, m in enumerate(available_abs):
                val = last.get(m, np.nan)
                val_display = val * 100 if m == "CVR" else val
                decimals = 2 if m in ("AOV", "CVR") else 0
                suffix = " %" if m == "CVR" else (" €" if m in ("AOV","Gross Revenue","GBV") else "")
                delta_col = DELTA_MAP.get(m)
                dval = last.get(delta_col, np.nan) if delta_col and delta_col in merged_df.columns else np.nan
                with kpi_cols[i]:
                    st.metric(m, fmt_num(val_display, decimals) + suffix,
                              f"{dval*100:+.1f}%" if m == "CVR" and not pd.isna(dval) else
                              (f"{dval:+.1f}%" if not pd.isna(dval) else None))

        st.markdown("#### Clics SEO (HM + Marque) vs Métriques Business")
        merged_display = merged_df.copy()
        if "CVR" in merged_display.columns:
            merged_display["CVR"] = merged_display["CVR"] * 100

        for metric in available_abs:
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            # Barres empilées HM + Marque
            fig2.add_trace(go.Bar(
                x=merged_display["date_key"], y=merged_display["hm_clicks"],
                name="Hors Marque", marker_color=BRAND_ORANGE, opacity=0.7
            ), secondary_y=False)
            fig2.add_trace(go.Bar(
                x=merged_display["date_key"], y=merged_display["m_clicks"],
                name="Marque", marker_color="#aec7e8", opacity=0.7
            ), secondary_y=False)
            # Ligne métrique
            fig2.add_trace(go.Scatter(
                x=merged_display["date_key"], y=merged_display[metric],
                name=metric, mode="lines+markers",
                line=dict(color=BRAND_BLUE, width=2.5), marker=dict(size=7)
            ), secondary_y=True)
            # Annotations % Δ
            dkey = DELTA_MAP.get(metric, f"% Δ {metric}")
            if dkey in merged_df.columns:
                for _, row in merged_df.iterrows():
                    if not pd.isna(row.get(dkey)):
                        color = "green" if row[dkey] >= 0 else "red"
                        fig2.add_annotation(
                            x=row["date_key"], y=merged_display.loc[row.name, metric],
                            text=f"{row[dkey]:+.1f}%",
                            showarrow=False, yref="y2",
                            font=dict(size=9, color=color), yshift=14
                        )
            fig2.update_layout(
                title=f"Clics SEO & {metric}", barmode="stack",
                plot_bgcolor="white", height=500,
                legend=dict(orientation="h", y=-0.2)
            )
            fig2.update_yaxes(title_text="Clics SEO (empilés)", secondary_y=False)
            fig2.update_yaxes(title_text=metric, secondary_y=True)
            st.plotly_chart(fig2, use_container_width=True)

        if available_delta:
            st.markdown("#### Évolution des variations (%)")
            fig_delta = go.Figure()
            for m in available_delta:
                fig_delta.add_trace(go.Scatter(
                    x=merged_df["date_key"], y=merged_df[m],
                    name=m, mode="lines+markers"
                ))
            fig_delta.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_delta.update_layout(plot_bgcolor="white", height=460, yaxis_title="%")
            st.plotly_chart(fig_delta, use_container_width=True)

        with st.expander("📋 Tableau complet fusionné"):
            st.dataframe(merged_df.rename(columns={
                "seo_clicks": "Total SEO", "hm_clicks": "Hors Marque", "m_clicks": "Marque"
            }), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CORRÉLATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    if merged_df is None:
        st.info("👆 Importe un fichier CSV dans la sidebar pour voir les corrélations.")
    else:
        available_abs = [m for m in ["Purchases","AOV","Gross Revenue","GBV","CVR","Sessions"]
                         if m in merged_df.columns]

        corr_type = st.radio(
            "Corrélation avec", ["Total SEO", "Hors Marque", "Marque"], horizontal=True
        )
        corr_col_map = {
            "Total SEO": "seo_clicks", "Hors Marque": "hm_clicks", "Marque": "m_clicks"
        }
        corr_col = corr_col_map[corr_type]

        corr_data = []
        for m in available_abs:
            sub = merged_df[[corr_col, m]].dropna()
            if len(sub) < 3:
                continue
            r = np.corrcoef(sub[corr_col], sub[m])[0, 1]
            corr_data.append({"Métrique": m, "r": r, "R²": r**2, "N": len(sub),
                               "Interprétation": (
                                   "Forte +" if r > 0.7 else
                                   "Modérée +" if r > 0.4 else
                                   "Forte −" if r < -0.7 else
                                   "Modérée −" if r < -0.4 else "Faible")})

        if corr_data:
            corr_df = pd.DataFrame(corr_data)
            st.markdown(f"#### Tableau de synthèse — corrélation avec {corr_type}")
            st.dataframe(corr_df.style.format({"r":"{:.3f}","R²":"{:.3f}"}),
                         use_container_width=True)

            fig_r = px.bar(corr_df, x="Métrique", y="r",
                           color="r", color_continuous_scale=["red","white","green"],
                           range_color=[-1, 1],
                           title=f"Coefficients de corrélation (r) — {corr_type}")
            fig_r.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_r.update_layout(plot_bgcolor="white", height=440)
            st.plotly_chart(fig_r, use_container_width=True)

            # ── FOCUS GBV ────────────────────────────────────────────────────
            if "GBV" in merged_df.columns:
                st.markdown("---")
                st.markdown("#### 🎯 Impact des clics sur la GBV — Hors Marque vs Marque")

                # Évolution temporelle : GBV + HM + Marque (double axe) + annotations MoM
                sub_gbv = merged_df[["date_key", "hm_clicks", "m_clicks", "GBV"]].dropna().reset_index(drop=True)
                if not sub_gbv.empty:
                    # Calcul des évolutions MoM
                    sub_gbv["δ_hm"]  = sub_gbv["hm_clicks"].pct_change() * 100
                    sub_gbv["δ_m"]   = sub_gbv["m_clicks"].pct_change() * 100
                    sub_gbv["δ_gbv"] = sub_gbv["GBV"].pct_change() * 100

                    fig_gbv_time = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_gbv_time.add_trace(go.Bar(
                        x=sub_gbv["date_key"], y=sub_gbv["hm_clicks"],
                        name="Hors Marque", marker_color=BRAND_ORANGE, opacity=0.7
                    ), secondary_y=False)
                    fig_gbv_time.add_trace(go.Bar(
                        x=sub_gbv["date_key"], y=sub_gbv["m_clicks"],
                        name="Marque", marker_color=COLOR_M, opacity=0.7
                    ), secondary_y=False)
                    fig_gbv_time.add_trace(go.Scatter(
                        x=sub_gbv["date_key"], y=sub_gbv["GBV"],
                        name="GBV", mode="lines+markers",
                        line=dict(color=BRAND_BLUE, width=3),
                        marker=dict(size=8, symbol="diamond"),
                    ), secondary_y=True)

                    # Annotations MoM Hors Marque (au-dessus des barres)
                    for _, row in sub_gbv.iterrows():
                        if pd.isna(row["δ_hm"]):
                            continue
                        fig_gbv_time.add_annotation(
                            x=row["date_key"],
                            y=row["hm_clicks"] + row["m_clicks"],
                            text=f"HM {row['δ_hm']:+.1f}%",
                            showarrow=False, yref="y",
                            font=dict(size=8, color="darkorange"),
                            yshift=18,
                        )
                    # Annotations MoM GBV (au-dessus de la ligne GBV)
                    for _, row in sub_gbv.iterrows():
                        if pd.isna(row["δ_gbv"]):
                            continue
                        fig_gbv_time.add_annotation(
                            x=row["date_key"],
                            y=row["GBV"],
                            text=f"GBV {row['δ_gbv']:+.1f}%",
                            showarrow=False, yref="y2",
                            font=dict(size=8, color="green" if row["δ_gbv"] >= 0 else "red"),
                            yshift=16,
                        )

                    fig_gbv_time.update_layout(
                        barmode="stack", plot_bgcolor="white", height=580,
                        hovermode="x unified", legend=dict(orientation="h", y=-0.15),
                        title="GBV vs Clics Hors Marque & Marque — évolutions MoM (%)",
                        margin=dict(t=60),
                    )
                    fig_gbv_time.update_yaxes(title_text="Clics SEO (empilés)", secondary_y=False)
                    fig_gbv_time.update_yaxes(title_text="GBV (€)", secondary_y=True)
                    st.plotly_chart(fig_gbv_time, use_container_width=True)

                # ── Janvier & Février — comparaison N-1 ─────────────────────
                # Paires N-1 à comparer : (label, clé N-1, clé N)
                compare_pairs = [
                    ("Décembre", "Dec-24", "Dec-25"),
                    ("Janvier",  "Jan-25", "Jan-26"),
                    ("Février",  "Feb-25", "Feb-26"),
                ]
                rows_yoy = []
                for month_label, key_n1, key_n in compare_pairs:
                    for year_key, year_label in [(key_n1, "N-1"), (key_n, "N")]:
                        row = merged_df[merged_df["date_key"] == year_key]
                        if row.empty:
                            continue
                        r = row.iloc[0]
                        rows_yoy.append({
                            "Mois": month_label,
                            "Année": year_label,
                            "Clé": year_key,
                            "Hors Marque": r.get("hm_clicks", np.nan),
                            "Marque":      r.get("m_clicks",  np.nan),
                            "GBV":         r.get("GBV",        np.nan),
                        })

                if rows_yoy:
                    yoy_df = pd.DataFrame(rows_yoy)
                    # Calcul des variations N-1 par mois
                    yoy_summary = []
                    for mois in ["Décembre", "Janvier", "Février"]:
                        sub_m = yoy_df[yoy_df["Mois"] == mois].set_index("Année")
                        if "N-1" not in sub_m.index or "N" not in sub_m.index:
                            continue
                        for col, label in [("Hors Marque", "HM"), ("Marque", "M"), ("GBV", "GBV")]:
                            v25 = sub_m.loc["N-1", col]
                            v26 = sub_m.loc["N",   col]
                            delta = (v26 / v25 - 1) * 100 if v25 else np.nan
                            yoy_summary.append({
                                "Mois": mois, "Métrique": col,
                                "N-1": v25, "N": v26, "Δ% N-1": delta
                            })

                    st.markdown("#### 📅 Déc / Jan / Fév — comparaison N-1")

                    # Graphique barres groupées : HM, Marque, GBV × mois × année
                    # Labels lisibles pour l'axe X
                    label_map = {
                        "Dec-24": "Déc 2024", "Dec-25": "Déc 2025",
                        "Jan-25": "Jan 2025", "Jan-26": "Jan 2026",
                        "Feb-25": "Fév 2025", "Feb-26": "Fév 2026",
                    }
                    yoy_df["x_label"] = yoy_df["Clé"].map(label_map)
                    # Ordre chronologique
                    order = ["Déc 2024","Déc 2025","Jan 2025","Jan 2026","Fév 2025","Fév 2026"]
                    yoy_df["x_label"] = pd.Categorical(yoy_df["x_label"], categories=order, ordered=True)
                    yoy_df = yoy_df.sort_values("x_label")

                    fig_jf = make_subplots(specs=[[{"secondary_y": True}]])

                    # Barres empilées HM + Marque
                    for metric, color, name in [
                        ("Hors Marque", BRAND_ORANGE, "Hors Marque"),
                        ("Marque",      COLOR_M,      "Marque"),
                    ]:
                        fig_jf.add_trace(go.Bar(
                            x=yoy_df["x_label"],
                            y=yoy_df[metric],
                            name=name,
                            marker_color=color,
                            opacity=0.8,
                        ), secondary_y=False)

                    # Ligne GBV
                    fig_jf.add_trace(go.Scatter(
                        x=yoy_df["x_label"],
                        y=yoy_df["GBV"],
                        name="GBV (€)",
                        mode="lines+markers",
                        line=dict(color=BRAND_BLUE, width=3),
                        marker=dict(size=9, symbol="diamond"),
                    ), secondary_y=True)

                    # Annotations Δ% entre N-1 et N pour clics et GBV
                    for entry in yoy_summary:
                        if pd.isna(entry["Δ% N-1"]):
                            continue
                        mois = entry["Mois"]
                        metric = entry["Métrique"]
                        # x du point N
                        x_n = yoy_df[yoy_df["Mois"] == mois].sort_values("x_label")["x_label"].iloc[-1]
                        is_gbv = metric == "GBV"
                        y_val = entry["N"] if not pd.isna(entry.get("N")) else 0
                        color_d = "green" if entry["Δ% N-1"] >= 0 else "red"
                        prefix = "GBV" if is_gbv else ("HM" if metric == "Hors Marque" else "M")
                        fig_jf.add_annotation(
                            x=x_n,
                            y=y_val,
                            text=f"<b>{prefix} {entry['Δ% N-1']:+.1f}%</b>",
                            showarrow=True,
                            arrowhead=2, arrowsize=0.8,
                            ax=30, ay=-30 if is_gbv else -50,
                            yref="y2" if is_gbv else "y",
                            font=dict(size=10, color=color_d),
                        )

                    fig_jf.update_layout(
                        barmode="stack", plot_bgcolor="white", height=560,
                        hovermode="x unified",
                        legend=dict(orientation="h", y=-0.15),
                        title="Déc / Jan / Fév — Clics HM + Marque & GBV (N-1 vs N)",
                        xaxis=dict(categoryorder="array", categoryarray=order),
                    )
                    fig_jf.update_yaxes(title_text="Clics SEO (empilés)", secondary_y=False)
                    fig_jf.update_yaxes(title_text="GBV (€)", secondary_y=True)
                    st.plotly_chart(fig_jf, use_container_width=True)

                # Scatter côte à côte : GBV vs HM | GBV vs Marque
                col_left, col_right = st.columns(2)
                for col_ui, click_col, label, color in [
                    (col_left,  "hm_clicks", "Hors Marque", BRAND_ORANGE),
                    (col_right, "m_clicks",  "Marque",      COLOR_M),
                ]:
                    sub = merged_df[["date_key", click_col, "GBV"]].dropna()
                    if len(sub) < 3:
                        continue
                    x, y = sub[click_col].values, sub["GBV"].values
                    z = np.polyfit(x, y, 1)
                    p_fn = np.poly1d(z)
                    r = np.corrcoef(x, y)[0, 1]
                    x_line = np.linspace(x.min(), x.max(), 100)

                    fig_sc = go.Figure()
                    fig_sc.add_trace(go.Scatter(
                        x=x, y=y, mode="markers+text",
                        text=sub["date_key"], textposition="top center",
                        marker=dict(color=color, size=10),
                        name="Données"
                    ))
                    fig_sc.add_trace(go.Scatter(
                        x=x_line, y=p_fn(x_line), mode="lines",
                        line=dict(color=BRAND_BLUE, dash="dash", width=2),
                        name="Tendance"
                    ))
                    fig_sc.update_layout(
                        title=f"GBV vs {label}<br>r={r:.3f} | R²={r**2:.3f}",
                        xaxis_title=f"Clics {label}", yaxis_title="GBV (€)",
                        plot_bgcolor="white", height=500, showlegend=False
                    )
                    with col_ui:
                        st.plotly_chart(fig_sc, use_container_width=True)

                # ── Export XLS ───────────────────────────────────────────────
                if not sub_gbv.empty:
                    export_df = sub_gbv.rename(columns={
                        "date_key": "Mois",
                        "hm_clicks": "Clics Hors Marque",
                        "m_clicks":  "Clics Marque",
                        "GBV":       "GBV (€)",
                        "δ_hm":      "Δ% Hors Marque MoM",
                        "δ_m":       "Δ% Marque MoM",
                        "δ_gbv":     "Δ% GBV MoM",
                    })

                    # Corrélations HM/Marque vs GBV
                    corr_rows = []
                    for lbl, col_k in [("Hors Marque", "Clics Hors Marque"),
                                        ("Marque",      "Clics Marque")]:
                        sub_c = export_df[["GBV (€)", col_k]].dropna()
                        if len(sub_c) >= 3:
                            r_val = np.corrcoef(sub_c[col_k], sub_c["GBV (€)"])[0, 1]
                            corr_rows.append({
                                "Segment": lbl,
                                "r (Pearson)": round(r_val, 4),
                                "R²": round(r_val**2, 4),
                                "N": len(sub_c),
                            })
                    corr_export = pd.DataFrame(corr_rows)

                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                        export_df.to_excel(writer, sheet_name="Données GBV", index=False)
                        corr_export.to_excel(writer, sheet_name="Corrélations", index=False)
                    buf.seek(0)

                    st.download_button(
                        label="📥 Exporter en Excel — Impact clics sur GBV",
                        data=buf,
                        file_name="weekendesk_gbv_clics.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                st.markdown("---")

            st.markdown(f"#### Scatter plots — {corr_type} vs Métriques")
            cols_scatter = st.columns(min(len(available_abs), 2))
            for i, m in enumerate(available_abs):
                sub = merged_df[["date_key", corr_col, m]].dropna()
                if len(sub) < 3:
                    continue
                x, y = sub[corr_col].values, sub[m].values
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                r = np.corrcoef(x, y)[0, 1]
                x_line = np.linspace(x.min(), x.max(), 100)

                fig_s = go.Figure()
                fig_s.add_trace(go.Scatter(
                    x=x, y=y, mode="markers+text",
                    text=sub["date_key"], textposition="top center",
                    marker=dict(color=BRAND_ORANGE, size=9), name="Données"
                ))
                fig_s.add_trace(go.Scatter(
                    x=x_line, y=p(x_line), mode="lines",
                    line=dict(color=BRAND_BLUE, dash="dash"), name="Tendance"
                ))
                fig_s.update_layout(
                    title=f"{m} — r={r:.3f} | R²={r**2:.3f}",
                    xaxis_title=corr_type, yaxis_title=m,
                    plot_bgcolor="white", height=500, showlegend=False
                )
                with cols_scatter[i % 2]:
                    st.plotly_chart(fig_s, use_container_width=True)

            st.markdown("#### Matrice de corrélation")
            all_num_cols = ["seo_clicks", "hm_clicks", "m_clicks"] + available_abs
            present_cols = [c for c in all_num_cols if c in merged_df.columns]
            corr_matrix = merged_df[present_cols].rename(columns={
                "seo_clicks": "Total SEO", "hm_clicks": "Hors Marque", "m_clicks": "Marque"
            }).corr()
            fig_mat = px.imshow(
                corr_matrix, text_auto=".2f",
                color_continuous_scale="RdBu", zmin=-1, zmax=1,
                title="Corrélations toutes métriques"
            )
            fig_mat.update_layout(height=460)
            st.plotly_chart(fig_mat, use_container_width=True)
        else:
            st.warning("Pas assez de données pour calculer les corrélations.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB TOP PAGES — CLASSEMENT ANNUEL 2025
# ═══════════════════════════════════════════════════════════════════════════════
with tab_top:
    st.markdown("#### 🏆 Classement annuel des pages SEO – 2025 (12 mois)")

    df_top = pd.DataFrame(TOP_PAGES_2025)
    total_top = df_top["clics"].sum()
    df_top["% du total"] = (df_top["clics"] / total_top * 100).round(1)
    df_top["rang"] = range(1, len(df_top) + 1)

    fig_top = go.Figure(go.Bar(
        x=df_top["clics"],
        y=df_top["page"],
        orientation="h",
        marker=dict(
            color=df_top["clics"],
            colorscale=[[0, "#ffe0cc"], [1, BRAND_ORANGE]],
            showscale=False,
        ),
        text=[
            f"{c:,.0f}\u202f  ({p}%)".replace(",", "\u202f")
            for c, p in zip(df_top["clics"], df_top["% du total"])
        ],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Clics : %{x:,.0f}<extra></extra>",
    ))
    fig_top.update_layout(
        xaxis_title="Clics SEO (annuel 2025)",
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        height=500,
        margin=dict(l=120, r=200),
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("#### Détail")
    df_display = df_top[["rang", "page", "clics", "% du total"]].copy()
    df_display["clics_fmt"] = df_display["clics"].apply(fmt_num)
    df_display["% du total"] = df_display["% du total"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(
        df_display[["rang", "page", "clics_fmt", "% du total"]].rename(columns={
            "rang": "Rang", "page": "Page",
            "clics_fmt": "Clics SEO 2025", "% du total": "Part du total",
        }),
        use_container_width=True, hide_index=True,
    )

    total_seo_2025 = seo_df[seo_df["year"] == 2025]["seo_clicks"].sum()
    st.caption(
        f"Total top 6 pages : {fmt_num(total_top)} clics  |  "
        f"Total SEO global 2025 : {fmt_num(total_seo_2025)} clics"
    )
