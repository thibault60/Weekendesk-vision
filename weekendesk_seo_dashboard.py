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
#  STATIC SEO CLICKS DATA
#  (year, month_int) → clicks
#  Note: Mars 2026 = données partielles (~18j)
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
#  HELPERS
# ─────────────────────────────────────────────

def build_clicks_df() -> pd.DataFrame:
    rows = []
    for (year, month), clicks in SEO_CLICKS_RAW.items():
        rows.append({
            "year":  year,
            "month": month,
            "month_label": MONTH_NUM_TO_FR[month],
            "period": f"{MONTH_NUM_TO_FR[month][:3]}-{str(year)[2:]}",
            "date":  pd.Timestamp(year=year, month=month, day=1),
            "clicks": clicks,
            "partial": (year == 2026 and month == 3),
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
    dim_col     = next((c for c in raw.columns if "dimension" in c.lower()), None)
    date_col    = next((c for c in raw.columns if "date" in c.lower()), None)
    mname_col   = next((c for c in raw.columns if "measure name" in c.lower() or "mesure" in c.lower()), None)
    mvalue_col  = next((c for c in raw.columns if "measure value" in c.lower() or "valeur" in c.lower()), None)

    missing = [n for n, c in [("Dimension 1", dim_col), ("Date", date_col),
                               ("Measure Names", mname_col), ("Measure Values", mvalue_col)] if c is None]
    if missing:
        st.error(f"Colonnes introuvables dans le fichier : {', '.join(missing)}. "
                 f"Colonnes détectées : {list(raw.columns)}")
        return None

    # Filter seo only
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
        help="Format attendu : Dimension 1 | Date | Measure Names | Measure Values",
    )

    st.markdown("---")
    st.markdown("### Filtres")
    available_years = sorted({y for (y, _) in SEO_CLICKS_RAW.keys()})
    selected_years = st.multiselect(
        "Années à afficher", available_years, default=available_years
    )

    st.markdown("---")
    st.caption("Données clics SEO : statiques | Business : fichier CSV")
    st.caption("Traitement 100% local – aucune donnée envoyée.")


# ─────────────────────────────────────────────
#  DATA PREPARATION
# ─────────────────────────────────────────────
clicks_df = build_clicks_df()
clicks_filtered = clicks_df[clicks_df["year"].isin(selected_years)].copy()

biz_df   = None
merged   = None

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
st.markdown(
    "Suivi des **clics SEO** et de la **performance business** par mois."
)

if clicks_df[clicks_df["partial"]].shape[0] > 0:
    st.info("ℹ️ Mars 2026 : données partielles (≈ 18 premiers jours du mois).", icon="📅")

# ─────────────────────────────────────────────
#  KPI ROW – latest full month
# ─────────────────────────────────────────────
latest = clicks_df[~clicks_df["partial"]].iloc[-1]
prev   = clicks_df[~clicks_df["partial"]].iloc[-2]
yoy_ref = clicks_df[
    (clicks_df["year"]  == latest["year"] - 1) &
    (clicks_df["month"] == latest["month"])
]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        f"Clics SEO – {latest['period']}",
        fmt_number(latest["clicks"]),
        delta=fmt_pct((latest["clicks"] / prev["clicks"] - 1) * 100) + " vs mois préc.",
    )
with col2:
    yoy_val = yoy_ref["clicks"].values[0] if not yoy_ref.empty else None
    yoy_delta = fmt_pct((latest["clicks"] / yoy_val - 1) * 100) + " YoY" if yoy_val else "–"
    st.metric("Clics SEO – YoY", fmt_number(yoy_val) if yoy_val else "–", delta=yoy_delta)
with col3:
    total_2025 = clicks_df[clicks_df["year"] == 2025]["clicks"].sum()
    st.metric("Total clics 2025", fmt_number(total_2025))
with col4:
    ytd_2026 = clicks_df[(clicks_df["year"] == 2026)]["clicks"].sum()
    st.metric("Total clics 2026 (YTD)", fmt_number(ytd_2026))

st.markdown("---")

# ─────────────────────────────────────────────
#  TABS
# ─────────────────────────────────────────────
tab_clicks, tab_yoy, tab_biz, tab_corr = st.tabs([
    "📈 Évolution Clics SEO",
    "📊 Comparaison YoY",
    "💼 Performance Business",
    "🔗 Corrélations",
])

# ══════════════════════════════════════════════
#  TAB 1 – ÉVOLUTION CLICS SEO
# ══════════════════════════════════════════════
with tab_clicks:
    st.subheader("Évolution mensuelle des clics SEO")

    fig = go.Figure()
    for year in selected_years:
        df_y = clicks_filtered[clicks_filtered["year"] == year].copy()
        if df_y.empty:
            continue
        fig.add_trace(go.Scatter(
            x=df_y["date"],
            y=df_y["clicks"],
            mode="lines+markers",
            name=str(year),
            line=dict(width=2),
            marker=dict(size=7),
            hovertemplate="<b>%{x|%b %Y}</b><br>Clics : %{y:,.0f}<extra></extra>",
        ))
    fig.update_layout(
        xaxis_title="Mois",
        yaxis_title="Clics SEO",
        hovermode="x unified",
        legend_title="Année",
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Monthly heatmap
    st.subheader("Heatmap clics SEO par mois / année")
    heatmap_data = clicks_df.pivot_table(
        index="month", columns="year", values="clicks", aggfunc="first"
    )
    heatmap_data.index = [MONTH_NUM_TO_FR[m] for m in heatmap_data.index]

    fig_h = px.imshow(
        heatmap_data,
        color_continuous_scale="Blues",
        text_auto=True,
        aspect="auto",
        labels={"color": "Clics"},
    )
    fig_h.update_traces(texttemplate="%{z:,.0f}")
    fig_h.update_layout(height=400)
    st.plotly_chart(fig_h, use_container_width=True)

    with st.expander("📋 Données brutes – Clics SEO"):
        display = clicks_filtered.copy()
        display["clicks_fmt"] = display["clicks"].apply(fmt_number)
        display["partial_flag"] = display["partial"].apply(lambda x: "⚠️ partiel" if x else "")
        st.dataframe(
            display[["period", "year", "month_label", "clicks_fmt", "partial_flag"]]
            .rename(columns={
                "period": "Période", "year": "Année",
                "month_label": "Mois", "clicks_fmt": "Clics SEO",
                "partial_flag": "Note",
            }),
            use_container_width=True, hide_index=True,
        )


# ══════════════════════════════════════════════
#  TAB 2 – COMPARAISON YoY
# ══════════════════════════════════════════════
with tab_yoy:
    st.subheader("Comparaison YoY – 2025 vs 2026")

    df_2025 = clicks_df[clicks_df["year"] == 2025].set_index("month")["clicks"]
    df_2026 = clicks_df[clicks_df["year"] == 2026].set_index("month")["clicks"]
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
            barmode="group", height=380,
            yaxis_title="Clics SEO",
            hovermode="x unified",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Delta chart
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
            title="Variation YoY en % (2026 vs 2025)",
            yaxis_title="% Δ",
            height=320,
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
            "| seo | Mar-26 | AOV | 89.5 | …"
        )
    else:
        present_metrics = [m for m in BUSINESS_METRICS if m in merged.columns]
        abs_present   = [m for m in ABS_METRICS   if m in present_metrics]
        delta_present = [m for m in DELTA_METRICS if m in present_metrics]

        if not present_metrics:
            st.warning("Aucune métrique business reconnue dans le fichier.")
        else:
            # Latest period KPIs
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

            # Dual axis charts: clicks + each abs metric
            for metric in abs_present:
                st.subheader(f"Clics SEO vs {metric}")
                fig2 = make_subplots(specs=[[{"secondary_y": True}]])
                fig2.add_trace(go.Bar(
                    x=merged["date"], y=merged["clicks"],
                    name="Clics SEO", marker_color="#aec7e8", opacity=0.6,
                ), secondary_y=False)
                fig2.add_trace(go.Scatter(
                    x=merged["date"], y=merged[metric],
                    name=metric, mode="lines+markers",
                    line=dict(color=COLORS["revenue"], width=2),
                    marker=dict(size=7),
                ), secondary_y=True)
                fig2.update_yaxes(title_text="Clics SEO", secondary_y=False)
                fig2.update_yaxes(title_text=metric, secondary_y=True)
                fig2.update_layout(height=340, hovermode="x unified", legend_title="")
                st.plotly_chart(fig2, use_container_width=True)

            # Delta metrics evolution
            if delta_present:
                st.subheader("Évolution des indicateurs de variation (%)")
                fig_d = go.Figure()
                for metric in delta_present:
                    fig_d.add_trace(go.Scatter(
                        x=merged["date"], y=merged[metric],
                        mode="lines+markers", name=metric,
                    ))
                fig_d.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_d.update_layout(height=350, yaxis_title="%", hovermode="x unified")
                st.plotly_chart(fig_d, use_container_width=True)

            with st.expander("📋 Données fusionnées complètes"):
                disp_cols = ["period", "clicks"] + present_metrics
                st.dataframe(
                    merged[[c for c in disp_cols if c in merged.columns]],
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
            st.subheader("Corrélation Clics SEO ↔ Métriques business")

            corr_data = {}
            for metric in abs_cols:
                sub = merged[["clicks", metric]].dropna()
                if len(sub) >= 3:
                    corr_data[metric] = sub["clicks"].corr(sub[metric])

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
                    height=320,
                    yaxis_title="Coefficient de Pearson (r)",
                )
                st.plotly_chart(fig_c, use_container_width=True)

            # Scatter plots
            selected_metric = st.selectbox("Choisir une métrique pour le scatter", abs_cols)
            if selected_metric:
                sub = merged[["period", "clicks", selected_metric]].dropna()
                fig_s = px.scatter(
                    sub, x="clicks", y=selected_metric,
                    text="period",
                    trendline="ols",
                    labels={"clicks": "Clics SEO", selected_metric: selected_metric},
                    title=f"Clics SEO vs {selected_metric}",
                )
                fig_s.update_traces(textposition="top center")
                fig_s.update_layout(height=420)
                st.plotly_chart(fig_s, use_container_width=True)
