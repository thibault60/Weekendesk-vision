import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Weekendesk – SEO Dashboard",
    page_icon="🏨",
    layout="wide",
)

# ─────────────────────────────────────────────
#  STATIC SEO CLICKS DATA – TOTAL
#  (year, month_int) → clicks
#  Note: Mars 2026 = données partielles
# ─────────────────────────────────────────────
SEO_CLICKS_RAW = {
    (2024, 12): 304_665,
    (2025,  1): 177_076,
    (2025,  2): 168_099,
    (2025,  3): 138_749,
    (2025,  4): 135_189,
    (2025,  5): 144_194,
    (2025,  6): 125_659,
    (2025,  7): 158_100,
    (2025,  8): 183_872,
    (2025,  9): 158_867,
    (2025, 10): 224_557,
    (2025, 11): 277_362,
    (2025, 12): 300_356,
    (2026,  1): 143_541,
    (2026,  2): 134_778,
    (2026,  3):  50_700,   # partiel
}

# ─────────────────────────────────────────────
#  CLICS HORS MARQUE (non-brand)
# ─────────────────────────────────────────────
SEO_HORS_MARQUE = {
    (2024, 12): 272_173,
    (2025,  1): 146_443,
    (2025,  2): 133_246,
    (2025,  3): 109_981,
    (2025,  4): 108_310,
    (2025,  5): 110_358,
    (2025,  6):  97_174,
    (2025,  7): 126_792,
    (2025,  8): 151_396,
    (2025,  9): 128_022,
    (2025, 10): 189_749,
    (2025, 11): 255_439,
    (2025, 12): 280_385,
    (2026,  1): 125_385,
    (2026,  2): 115_359,
    (2026,  3):  42_996,   # partiel
}

# ─────────────────────────────────────────────
#  CLICS MARQUE (brand)
# ─────────────────────────────────────────────
SEO_MARQUE = {
    (2024, 12):  32_492,
    (2025,  1):  30_633,
    (2025,  2):  34_853,
    (2025,  3):  28_768,
    (2025,  4):  26_879,
    (2025,  5):  33_836,
    (2025,  6):  28_485,
    (2025,  7):  31_308,
    (2025,  8):  32_476,
    (2025,  9):  30_845,
    (2025, 10):  34_808,
    (2025, 11):  21_923,
    (2025, 12):  19_971,
    (2026,  1):  18_156,
    (2026,  2):  19_419,
    (2026,  3):   7_704,   # partiel
}

MONTH_ABBR_FR = {
    "Jan": 1, "Fév": 2, "Mar": 3, "Avr": 4,
    "Mai": 5, "Jui": 6, "Jul": 7, "Aoû": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Déc": 12,
}
MONTH_ABBR_EN = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
MONTH_NUM_TO_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}

BUSINESS_METRICS = [
    "Purchases", "% Δ Purchases",
    "AOV", "% Δ AOV",
    "Gross Revenue", "% Δ Gross Revenue",
    "GBV", "% Total GBV",
    "CVR", "% Δ CVR",
]

DELTA_METRICS = [m for m in BUSINESS_METRICS if m.startswith("% Δ") or m == "% Total GBV"]
ABS_METRICS   = [m for m in BUSINESS_METRICS if m not in DELTA_METRICS]

COLORS = {
    "clicks":        "#1f77b4",
    "clicks_hm":     "#e07b39",
    "clicks_m":      "#2ca02c",
    "purchases":     "#2ca02c",
    "revenue":       "#ff7f0e",
    "gbv":           "#9467bd",
    "cvr":           "#e377c2",
    "aov":           "#8c564b",
    "delta_pos":     "#2ca02c",
    "delta_neg":     "#d62728",
    "bg_card":       "#f0f4ff",
}

# ─────────────────────────────────────────────
#  TOP PAGES 2025 – CLASSEMENT ANNUEL
# ─────────────────────────────────────────────
TOP_PAGES_2025 = [
    {"page": "Idées WE",    "clics": 897_074},
    {"page": "Séjour",      "clics": 616_771},
    {"page": "Home",        "clics": 311_461},
    {"page": "Hôtels",      "clics": 189_581},
    {"page": "Villes",      "clics": 143_927},
    {"page": "Last minute", "clics": 106_691},
]


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def build_clicks_df() -> pd.DataFrame:
    rows = []
    for (year, month), clicks in SEO_CLICKS_RAW.items():
        rows.append({
            "year":        year,
            "month":       month,
            "month_label": MONTH_NUM_TO_FR[month],
            "period":      f"{MONTH_NUM_TO_FR[month][:3]}-{str(year)[2:]}",
            "date":        pd.Timestamp(year=year, month=month, day=1),
            "clicks":      clicks,
            "clicks_hm":   SEO_HORS_MARQUE.get((year, month), 0),
            "clicks_m":    SEO_MARQUE.get((year, month), 0),
            "partial":     (year == 2026 and month == 3),
        })
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    return df


def parse_date_label(label: str) -> pd.Timestamp | None:
    """Parse 'Mar-26' or 'Mar-2026' → Timestamp."""
    try:
        parts = str(label).strip().split("-")
        if len(parts) != 2:
            return None
        abbr, yr = parts[0].strip().capitalize(), parts[1].strip()
        year = int("20" + yr) if len(yr) == 2 else int(yr)
        month = MONTH_ABBR_EN.get(abbr) or MONTH_ABBR_FR.get(abbr)
        if month is None:
            return None
        return pd.Timestamp(year=year, month=month, day=1)
    except Exception:
        return None


def load_csv(file) -> pd.DataFrame | None:
    """
    Parse Tableau-style CSV export:
      Columns: Dimension 1 | Date | Measure Names | Measure Values
    Filters on Dimension 1 == 'seo', pivots Measure Names.
    """
    try:
        raw = pd.read_csv(file, sep=None, engine="python", encoding="utf-8")
    except UnicodeDecodeError:
        try:
            raw = pd.read_csv(file, sep=None, engine="python", encoding="latin-1")
        except Exception as e:
            st.error(f"Impossible de lire le fichier : {e}")
            return None
    except Exception as e:
        st.error(f"Impossible de lire le fichier : {e}")
        return None

    raw.columns = [str(c).strip() for c in raw.columns]

    # Detect column names flexibly
    dim_col    = next((c for c in raw.columns if "dimension" in c.lower()), None)
    date_col   = next((c for c in raw.columns if "date" in c.lower()), None)
    mname_col  = next((c for c in raw.columns if "measure name" in c.lower() or "mesure" in c.lower()), None)
    mvalue_col = next((c for c in raw.columns if "measure value" in c.lower() or "valeur" in c.lower()), None)

    missing = [n for n, c in [("Dimension 1", dim_col), ("Date", date_col),
                               ("Measure Names", mname_col), ("Measure Values", mvalue_col)] if c is None]
    if missing:
        st.error(f"Colonnes introuvables dans le fichier : {', '.join(missing)}. "
                 f"Colonnes détectées : {list(raw.columns)}")
        return None

    # Filter seo only (Dimension 1 == 'seo')
    df = raw[raw[dim_col].astype(str).str.strip().str.lower() == "seo"].copy()
    if df.empty:
        st.warning("Aucune ligne avec Dimension 1 = 'seo' trouvée.")
        return None

    df["date"] = df[date_col].apply(parse_date_label)
    df = df.dropna(subset=["date"])
    df[mvalue_col] = pd.to_numeric(df[mvalue_col], errors="coerce")

    pivot = df.pivot_table(
        index="date",
        columns=mname_col,
        values=mvalue_col,
        aggfunc="first",
    ).reset_index()
    pivot.columns.name = None
    return pivot


def merge_with_clicks(clicks_df: pd.DataFrame, biz_df: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge(clicks_df, biz_df, on="date", how="inner")
    return merged.sort_values("date").reset_index(drop=True)


def fmt_number(n, decimals=0):
    if pd.isna(n):
        return "–"
    if decimals == 0:
        return f"{int(n):,}".replace(",", "\u202f")
    return f"{n:,.{decimals}f}".replace(",", "\u202f")


def fmt_pct(n):
    if pd.isna(n):
        return "–"
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.1f}%"


def delta_color(val):
    if pd.isna(val):
        return "gray"
    return COLORS["delta_pos"] if val >= 0 else COLORS["delta_neg"]


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/"
        "Weekendesk_logo.svg/320px-Weekendesk_logo.svg.png",
        use_container_width=True,
    )
    st.markdown("## 🏨 SEO Dashboard")
    st.markdown("---")

    uploaded_file = st.file_uploader(
        "📂 Importer le fichier CSV",
        type=["csv"],
        help="Format attendu : Dimension 1 | Date | Measure Names | Measure Values\n"
             "Seules les lignes Dimension 1 = 'seo' sont utilisées.",
    )

    st.markdown("---")
    st.markdown("### Filtres")
    available_years = sorted({y for (y, _) in SEO_CLICKS_RAW.keys()})
    selected_years = st.multiselect(
        "Années à afficher", available_years, default=available_years
    )

    st.markdown("---")
    st.caption("Données clics SEO : statiques | Business : fichier CSV (filtre seo)")
    st.caption("Traitement 100% local – aucune donnée envoyée.")


# ─────────────────────────────────────────────
#  DATA PREPARATION
# ─────────────────────────────────────────────
clicks_df = build_clicks_df()
clicks_filtered = clicks_df[clicks_df["year"].isin(selected_years)].copy()

biz_df = None
merged = None

if uploaded_file:
    with st.spinner("Chargement du fichier…"):
        biz_df = load_csv(uploaded_file)
    if biz_df is not None:
        merged = merge_with_clicks(clicks_df, biz_df)
        if merged.empty:
            st.warning("Aucune correspondance entre les dates du fichier et les données SEO.")
            merged = None


# ─────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────
st.title("🏨 Weekendesk – Tableau de bord SEO")
st.markdown("Suivi des **clics SEO** (Marque / Hors Marque) et de la **performance business** par mois.")

if clicks_df[clicks_df["partial"]].shape[0] > 0:
    st.info("ℹ️ Mars 2026 : données partielles (≈ 18 premiers jours du mois).", icon="📅")

# ─────────────────────────────────────────────
#  KPI ROW – latest full month
# ─────────────────────────────────────────────
latest = clicks_df[~clicks_df["partial"]].iloc[-1]
prev   = clicks_df[~clicks_df["partial"]].iloc[-2]

col1, col2, col3, col4 = st.columns(4)
with col1:
    delta_hm = fmt_pct((latest["clicks_hm"] / prev["clicks_hm"] - 1) * 100) + " vs mois préc."
    st.metric(
        f"Clics Hors Marque – {latest['period']}",
        fmt_number(latest["clicks_hm"]),
        delta=delta_hm,
    )
with col2:
    delta_m = fmt_pct((latest["clicks_m"] / prev["clicks_m"] - 1) * 100) + " vs mois préc."
    st.metric(
        f"Clics Marque – {latest['period']}",
        fmt_number(latest["clicks_m"]),
        delta=delta_m,
    )
with col3:
    total_hm_2025 = clicks_df[clicks_df["year"] == 2025]["clicks_hm"].sum()
    total_m_2025  = clicks_df[clicks_df["year"] == 2025]["clicks_m"].sum()
    st.metric("Total HM 2025", fmt_number(total_hm_2025))
with col4:
    ytd_hm_2026 = clicks_df[clicks_df["year"] == 2026]["clicks_hm"].sum()
    ytd_m_2026  = clicks_df[clicks_df["year"] == 2026]["clicks_m"].sum()
    st.metric("Total HM 2026 (YTD)", fmt_number(ytd_hm_2026),
              delta=fmt_pct((ytd_hm_2026 / clicks_df[
                  (clicks_df["year"] == 2025) &
                  (clicks_df["month"].isin(clicks_df[clicks_df["year"] == 2026]["month"]))
              ]["clicks_hm"].sum() - 1) * 100) + " YoY")

st.markdown("---")

# ─────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────
tab_clicks, tab_yoy, tab_biz, tab_corr, tab_top = st.tabs([
    "📈 Évolution Clics SEO",
    "📊 Comparaison YoY",
    "💼 Performance Business",
    "🔗 Corrélations",
    "🏆 Top Pages 2025",
])

# ══════════════════════════════════════════════
#  TAB 1 – ÉVOLUTION CLICS SEO
# ══════════════════════════════════════════════
with tab_clicks:
    st.subheader("Évolution mensuelle des clics SEO")

    series_choice = st.multiselect(
        "Séries à afficher",
        options=["Total SEO", "Hors Marque", "Marque"],
        default=["Total SEO", "Hors Marque", "Marque"],
    )

    fig = go.Figure()
    series_map = {
        "Total SEO":   ("clicks",    COLORS["clicks"],    "solid"),
        "Hors Marque": ("clicks_hm", COLORS["clicks_hm"], "solid"),
        "Marque":      ("clicks_m",  COLORS["clicks_m"],  "dot"),
    }

    for label in series_choice:
        col_key, color, dash = series_map[label]
        df_s = clicks_filtered[["date", col_key]].dropna()
        fig.add_trace(go.Scatter(
            x=df_s["date"],
            y=df_s[col_key],
            mode="lines+markers",
            name=label,
            line=dict(width=2.5, color=color, dash=dash),
            marker=dict(size=7),
            hovertemplate=f"<b>%{{x|%b %Y}}</b><br>{label} : %{{y:,.0f}}<extra></extra>",
        ))

    fig.update_layout(
        xaxis_title="Mois",
        yaxis_title="Clics SEO",
        hovermode="x unified",
        legend_title="Série",
        height=560,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Monthly heatmap – Hors Marque
    st.subheader("Heatmap – Clics Hors Marque par mois / année")
    heatmap_hm = clicks_df.pivot_table(
        index="month", columns="year", values="clicks_hm", aggfunc="first"
    )
    heatmap_hm.index = [MONTH_NUM_TO_FR[m] for m in heatmap_hm.index]
    fig_h = px.imshow(
        heatmap_hm,
        color_continuous_scale="Oranges",
        text_auto=True,
        aspect="auto",
        labels={"color": "Clics HM"},
    )
    fig_h.update_traces(texttemplate="%{z:,.0f}")
    fig_h.update_layout(height=500)
    st.plotly_chart(fig_h, use_container_width=True)

    # Monthly heatmap – Marque
    st.subheader("Heatmap – Clics Marque par mois / année")
    heatmap_m = clicks_df.pivot_table(
        index="month", columns="year", values="clicks_m", aggfunc="first"
    )
    heatmap_m.index = [MONTH_NUM_TO_FR[m] for m in heatmap_m.index]
    fig_hm2 = px.imshow(
        heatmap_m,
        color_continuous_scale="Greens",
        text_auto=True,
        aspect="auto",
        labels={"color": "Clics M"},
    )
    fig_hm2.update_traces(texttemplate="%{z:,.0f}")
    fig_hm2.update_layout(height=500)
    st.plotly_chart(fig_hm2, use_container_width=True)

    with st.expander("📋 Données brutes – Clics SEO (Total / HM / Marque)"):
        display = clicks_filtered.copy()
        display["Total"]        = display["clicks"].apply(fmt_number)
        display["Hors Marque"]  = display["clicks_hm"].apply(fmt_number)
        display["Marque"]       = display["clicks_m"].apply(fmt_number)
        display["Note"]         = display["partial"].apply(lambda x: "⚠️ partiel" if x else "")
        st.dataframe(
            display[["period", "year", "month_label", "Total", "Hors Marque", "Marque", "Note"]]
            .rename(columns={"period": "Période", "year": "Année", "month_label": "Mois"}),
            use_container_width=True, hide_index=True,
        )


# ══════════════════════════════════════════════
#  TAB 2 – COMPARAISON YoY
# ══════════════════════════════════════════════
with tab_yoy:
    st.subheader("Comparaison YoY – 2025 vs 2026")

    yoy_type = st.radio(
        "Type de clics",
        options=["Total SEO", "Hors Marque", "Marque"],
        horizontal=True,
    )
    yoy_col_map = {
        "Total SEO":   ("clicks",    "Clics Total SEO"),
        "Hors Marque": ("clicks_hm", "Clics Hors Marque"),
        "Marque":      ("clicks_m",  "Clics Marque"),
    }
    yoy_col, yoy_label = yoy_col_map[yoy_type]

    df_2025 = clicks_df[clicks_df["year"] == 2025].set_index("month")[yoy_col]
    df_2026 = clicks_df[clicks_df["year"] == 2026].set_index("month")[yoy_col]
    common_months = sorted(set(df_2025.index) & set(df_2026.index))

    if common_months:
        bar_df = pd.DataFrame({
            "Mois": [MONTH_NUM_TO_FR[m] for m in common_months],
            "2025": [df_2025[m] for m in common_months],
            "2026": [df_2026[m] for m in common_months],
        })
        bar_df["Δ YoY (%)"] = (bar_df["2026"] / bar_df["2025"] - 1) * 100

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=bar_df["Mois"], y=bar_df["2025"], name="2025",
            marker_color="#aec7e8",
        ))
        fig_bar.add_trace(go.Bar(
            x=bar_df["Mois"], y=bar_df["2026"], name="2026",
            marker_color=COLORS["clicks"],
        ))
        fig_bar.update_layout(
            barmode="group", height=520,
            yaxis_title=yoy_label,
            hovermode="x unified",
            title=f"{yoy_label} – 2025 vs 2026",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        fig_delta = go.Figure(go.Bar(
            x=bar_df["Mois"],
            y=bar_df["Δ YoY (%)"],
            marker_color=[COLORS["delta_pos"] if v >= 0 else COLORS["delta_neg"]
                          for v in bar_df["Δ YoY (%)"]],
            text=[fmt_pct(v) for v in bar_df["Δ YoY (%)"]],
            textposition="outside",
        ))
        fig_delta.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_delta.update_layout(
            title=f"Variation YoY en % (2026 vs 2025) – {yoy_label}",
            yaxis_title="% Δ",
            height=420,
        )
        st.plotly_chart(fig_delta, use_container_width=True)
    else:
        st.info("Pas assez de données communes entre 2025 et 2026 pour comparer.")


# ══════════════════════════════════════════════
#  TAB 3 – PERFORMANCE BUSINESS
# ══════════════════════════════════════════════
with tab_biz:
    if merged is None:
        st.info(
            "📂 Importez un fichier CSV dans la barre latérale pour afficher "
            "les indicateurs business.\n\n"
            "**Format attendu :**\n"
            "| Dimension 1 | Date | Measure Names | Measure Values |\n"
            "|---|---|---|---|\n"
            "| seo | Mar-26 | Purchases | 1234 |\n"
            "| seo | Mar-26 | AOV | 89.5 | …\n\n"
            "ℹ️ Seules les lignes `Dimension 1 = seo` sont utilisées."
        )
    else:
        present_metrics = [m for m in BUSINESS_METRICS if m in merged.columns]
        abs_present   = [m for m in ABS_METRICS   if m in present_metrics]
        delta_present = [m for m in DELTA_METRICS if m in present_metrics]

        if not present_metrics:
            st.warning("Aucune métrique business reconnue dans le fichier.")
        else:
            last_row = merged.iloc[-1]
            st.subheader(f"KPIs – {last_row['period']}")
            kpi_cols = st.columns(len(abs_present)) if abs_present else []
            for col, metric in zip(kpi_cols, abs_present):
                val = last_row.get(metric)
                delta_key = f"% Δ {metric}"
                delta_val = last_row.get(delta_key)
                with col:
                    st.metric(
                        metric,
                        fmt_number(val, decimals=2 if "AOV" in metric else 0),
                        delta=fmt_pct(delta_val) if not pd.isna(delta_val) else None,
                    )

            st.markdown("---")

            for metric in abs_present:
                st.subheader(f"Clics SEO vs {metric}")
                fig2 = make_subplots(specs=[[{"secondary_y": True}]])
                fig2.add_trace(go.Bar(
                    x=merged["date"], y=merged["clicks_hm"],
                    name="Clics Hors Marque", marker_color="#f0c080", opacity=0.7,
                ), secondary_y=False)
                fig2.add_trace(go.Bar(
                    x=merged["date"], y=merged["clicks_m"],
                    name="Clics Marque", marker_color="#aec7e8", opacity=0.7,
                ), secondary_y=False)
                fig2.add_trace(go.Scatter(
                    x=merged["date"], y=merged[metric],
                    name=metric, mode="lines+markers",
                    line=dict(color=COLORS["revenue"], width=2.5),
                    marker=dict(size=8),
                ), secondary_y=True)
                fig2.update_yaxes(title_text="Clics SEO", secondary_y=False)
                fig2.update_yaxes(title_text=metric, secondary_y=True)
                fig2.update_layout(
                    barmode="stack", height=500,
                    hovermode="x unified", legend_title="",
                )
                st.plotly_chart(fig2, use_container_width=True)

            if delta_present:
                st.subheader("Évolution des indicateurs de variation (%)")
                fig_d = go.Figure()
                for metric in delta_present:
                    fig_d.add_trace(go.Scatter(
                        x=merged["date"], y=merged[metric],
                        mode="lines+markers", name=metric,
                    ))
                fig_d.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_d.update_layout(height=460, yaxis_title="%", hovermode="x unified")
                st.plotly_chart(fig_d, use_container_width=True)

            with st.expander("📋 Données fusionnées complètes"):
                disp_cols = ["period", "clicks", "clicks_hm", "clicks_m"] + present_metrics
                st.dataframe(
                    merged[[c for c in disp_cols if c in merged.columns]].rename(columns={
                        "clicks": "Total SEO", "clicks_hm": "Hors Marque", "clicks_m": "Marque",
                    }),
                    use_container_width=True, hide_index=True,
                )


# ══════════════════════════════════════════════
#  TAB 4 – CORRÉLATIONS
# ══════════════════════════════════════════════
with tab_corr:
    if merged is None:
        st.info("📂 Importez un fichier CSV pour afficher les corrélations.")
    else:
        abs_cols = [m for m in ABS_METRICS if m in merged.columns]
        if not abs_cols:
            st.warning("Aucune métrique absolute disponible pour calculer les corrélations.")
        else:
            corr_type = st.radio(
                "Corrélation avec", ["Total SEO", "Hors Marque", "Marque"],
                horizontal=True,
            )
            corr_col_map = {
                "Total SEO": "clicks", "Hors Marque": "clicks_hm", "Marque": "clicks_m"
            }
            corr_col = corr_col_map[corr_type]

            st.subheader(f"Corrélation {corr_type} ↔ Métriques business")

            corr_data = {}
            for metric in abs_cols:
                sub = merged[[corr_col, metric]].dropna()
                if len(sub) >= 3:
                    corr_data[metric] = sub[corr_col].corr(sub[metric])

            if corr_data:
                corr_df = pd.DataFrame.from_dict(
                    corr_data, orient="index", columns=["Corrélation (r)"]
                ).sort_values("Corrélation (r)", ascending=False)

                fig_c = go.Figure(go.Bar(
                    x=corr_df.index,
                    y=corr_df["Corrélation (r)"],
                    marker_color=[
                        COLORS["delta_pos"] if v >= 0 else COLORS["delta_neg"]
                        for v in corr_df["Corrélation (r)"]
                    ],
                    text=[f"{v:.2f}" for v in corr_df["Corrélation (r)"]],
                    textposition="outside",
                ))
                fig_c.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_c.update_layout(
                    yaxis=dict(range=[-1.1, 1.1]),
                    height=440,
                    yaxis_title="Coefficient de Pearson (r)",
                )
                st.plotly_chart(fig_c, use_container_width=True)

            selected_metric = st.selectbox("Choisir une métrique pour le scatter", abs_cols)
            if selected_metric:
                sub = merged[["period", corr_col, selected_metric]].dropna()
                fig_s = px.scatter(
                    sub, x=corr_col, y=selected_metric,
                    text="period",
                    trendline="ols",
                    labels={corr_col: corr_type, selected_metric: selected_metric},
                    title=f"{corr_type} vs {selected_metric}",
                )
                fig_s.update_traces(textposition="top center")
                fig_s.update_layout(height=560)
                st.plotly_chart(fig_s, use_container_width=True)


# ══════════════════════════════════════════════
#  TAB 5 – TOP PAGES 2025
# ══════════════════════════════════════════════
with tab_top:
    st.subheader("🏆 Classement annuel des pages SEO – 2025 (12 mois)")

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
            colorscale="Blues",
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
        height=500,
        margin=dict(l=120, r=200),
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("Détail")
    df_display = df_top[["rang", "page", "clics", "% du total"]].copy()
    df_display["clics_fmt"] = df_display["clics"].apply(fmt_number)
    df_display["% du total"] = df_display["% du total"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(
        df_display[["rang", "page", "clics_fmt", "% du total"]].rename(columns={
            "rang": "Rang", "page": "Page",
            "clics_fmt": "Clics SEO 2025", "% du total": "Part du total",
        }),
        use_container_width=True,
        hide_index=True,
    )

    total_seo_2025 = clicks_df[clicks_df["year"] == 2025]["clicks"].sum()
    st.caption(
        f"Total top 6 pages : {fmt_number(total_top)} clics  |  "
        f"Total SEO global 2025 : {fmt_number(total_seo_2025)} clics"
    )
