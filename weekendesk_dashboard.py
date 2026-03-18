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
    "Mar-26": 50700,  # Mars 2026 partiel
}

MONTH_MAP = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
             "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
MONTH_FR  = {1:"Jan",2:"Fév",3:"Mar",4:"Avr",5:"Mai",6:"Jun",
             7:"Jul",8:"Aoû",9:"Sep",10:"Oct",11:"Nov",12:"Déc"}

BRAND_ORANGE = "#FF6B00"
BRAND_BLUE   = "#1E3A5F"
PARTIAL_KEY  = "Mar-26"   # mois incomplet

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
            "date_key": key,
            "date": pd.Timestamp(year=year, month=mnum, day=1),
            "month_abbr": abbr,
            "year": year,
            "month_num": mnum,
            "seo_clicks": clicks,
            "partial": key == PARTIAL_KEY,
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

MONTH_NAMES_FULL = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec"
}

def normalize_date_key(raw):
    """Convertit 'March 2026' ou 'Mar-26' → 'Mar-26'."""
    s = str(raw).strip()
    # Format "March 2026" (export Tableau complet)
    m = re.match(r'^([A-Za-z]+)\s+(\d{4})$', s)
    if m:
        short = MONTH_NAMES_FULL.get(m.group(1).lower())
        if short:
            return f"{short}-{m.group(2)[2:]}"
    # Format court "Mar-26" déjà correct
    m2 = re.match(r'^([A-Za-z]{3})-(\d{2})$', s)
    if m2:
        return f"{m2.group(1).capitalize()}-{m2.group(2)}"
    return None

def parse_csv(uploaded):
    """Parse le CSV Tableau (unpivot) et renvoie un DataFrame pivoté."""
    try:
        df = pd.read_csv(uploaded, encoding="utf-8")
    except UnicodeDecodeError:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="latin-1")

    # Détection flexible des colonnes
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

    # Filtre seo
    df = df[df[col_map["dim"]].astype(str).str.strip().str.lower() == "seo"].copy()
    if df.empty:
        st.warning("Aucune ligne avec Dimension 1 = 'seo' trouvée.")
        return None

    # Normalise la date → date_key
    df["date_key"] = df[col_map["date"]].apply(normalize_date_key)
    df = df.dropna(subset=["date_key"])

    # Conversion valeurs
    df[col_map["mvalue"]] = pd.to_numeric(
        df[col_map["mvalue"]].astype(str).str.replace(",", ".").str.replace(" ", ""),
        errors="coerce"
    )

    # Strip des Measure Names avant pivot
    df[col_map["mname"]] = df[col_map["mname"]].astype(str).str.strip()

    # Pivot
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
        return f"{v:,.0f}".replace(",", " ")
    return f"{v:,.{decimals}f}".replace(",", " ")

def delta_arrow(v):
    if pd.isna(v):
        return ""
    return f"{'↑' if v >= 0 else '↓'} {abs(v):.1f}%"

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Weekendesk_logo.svg/320px-Weekendesk_logo.svg.png",
             use_column_width=True)
    st.markdown("---")
    st.markdown("### 📂 Importer les données")
    uploaded = st.file_uploader("Fichier CSV (export Tableau)", type=["csv"])
    st.markdown("---")
    st.markdown("### 🔍 Filtres")
    years_available = sorted({2000+int(k.split("-")[1]) for k in SEO_CLICKS_RAW})
    selected_years = st.multiselect("Années", years_available, default=years_available)
    st.markdown("---")
    st.caption("🏖️ Weekendesk SEO Vision v1.0")

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🏖️ Weekendesk SEO Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Monitoring des performances SEO & Business</p>', unsafe_allow_html=True)
st.markdown("---")

# ── BUILD DATA ────────────────────────────────────────────────────────────────
seo_df = build_seo_df()
seo_filtered = seo_df[seo_df["year"].isin(selected_years)]

biz_df = None
merged_df = None
if uploaded:
    biz_df = parse_csv(uploaded)
    if biz_df is not None:
        merged_df = seo_df.merge(biz_df, on="date_key", how="inner")
        merged_df = merged_df.sort_values("date").reset_index(drop=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Clics SEO", "💼 Performance Business", "🔗 Corrélations"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CLICS SEO
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    total = seo_filtered["seo_clicks"].sum()
    best_row = seo_filtered.loc[seo_filtered["seo_clicks"].idxmax()]
    last2 = seo_df.tail(2)
    delta_pct = ((last2.iloc[-1]["seo_clicks"] - last2.iloc[-2]["seo_clicks"])
                 / last2.iloc[-2]["seo_clicks"] * 100) if len(last2) == 2 else None

    with col1:
        st.metric("Total clics (sélection)", fmt_num(total))
    with col2:
        st.metric("Meilleur mois", f"{best_row['month_abbr']}-{str(best_row['year'])[2:]}",
                  fmt_num(best_row["seo_clicks"]))
    with col3:
        st.metric("Dernier mois", f"{seo_df.iloc[-1]['date_key']}",
                  fmt_num(seo_df.iloc[-1]["seo_clicks"]))
    with col4:
        if delta_pct is not None:
            st.metric("Évolution M/M", f"{delta_pct:+.1f}%")

    st.markdown("#### Évolution des clics SEO par année")
    fig_line = go.Figure()
    colors_year = {2024: "#aaa", 2025: BRAND_BLUE, 2026: BRAND_ORANGE}
    for yr in sorted(seo_filtered["year"].unique()):
        sub = seo_filtered[seo_filtered["year"] == yr].copy()
        solid = sub[~sub["partial"]]
        partial = sub[sub["partial"]]
        fig_line.add_trace(go.Scatter(
            x=solid["month_num"], y=solid["seo_clicks"],
            mode="lines+markers", name=str(yr),
            line=dict(color=colors_year.get(yr, "#888"), width=2.5),
            marker=dict(size=7),
            hovertemplate="%{y:,.0f} clics<extra>" + str(yr) + "</extra>"
        ))
        if not partial.empty:
            fig_line.add_trace(go.Scatter(
                x=partial["month_num"], y=partial["seo_clicks"],
                mode="markers", name=f"{yr} (partiel)",
                marker=dict(symbol="circle-open", size=10,
                            color=colors_year.get(yr, "#888"), line=dict(width=2)),
                showlegend=True
            ))
    fig_line.update_layout(
        xaxis=dict(tickvals=list(range(1,13)),
                   ticktext=["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]),
        yaxis_title="Clics SEO", plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.2), hovermode="x unified",
        height=420
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # Barres groupées
    st.markdown("#### Clics SEO par mois — vue groupée")
    fig_bar = px.bar(
        seo_filtered, x="month_num", y="seo_clicks", color="year",
        barmode="group",
        color_discrete_sequence=[BRAND_BLUE, BRAND_ORANGE, "#aaa"],
        labels={"month_num":"Mois","seo_clicks":"Clics SEO","year":"Année"}
    )
    fig_bar.update_layout(
        xaxis=dict(tickvals=list(range(1,13)),
                   ticktext=["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]),
        plot_bgcolor="white", height=380
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Heatmap
    st.markdown("#### Heatmap mensuelle")
    heat_pivot = seo_filtered.pivot_table(index="year", columns="month_num",
                                          values="seo_clicks", aggfunc="first")
    heat_pivot.columns = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"][:len(heat_pivot.columns)]
    fig_heat = px.imshow(
        heat_pivot, text_auto=True, aspect="auto",
        color_continuous_scale=[[0,"#fff"],[1, BRAND_ORANGE]],
        labels=dict(color="Clics SEO")
    )
    fig_heat.update_layout(height=200 + 60*len(heat_pivot))
    st.plotly_chart(fig_heat, use_container_width=True)

    # Tableau
    with st.expander("📋 Tableau des données SEO"):
        disp = seo_filtered[["date_key","year","month_abbr","seo_clicks","partial"]].copy()
        disp.columns = ["Clé Date","Année","Mois","Clics SEO","Partiel"]
        st.dataframe(disp.style.format({"Clics SEO": "{:,.0f}"}), use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PERFORMANCE BUSINESS
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    if merged_df is None:
        st.info("👆 Importe un fichier CSV dans la sidebar pour voir les métriques business.")
    else:
        METRICS_ABS   = ["Purchases", "AOV", "Gross Revenue", "GBV", "CVR", "Sessions"]
        METRICS_DELTA = ["% Δ Purchases", "% Δ AOV", "% Δ Gross Revenue", "% Δ GBV vs LP", "% Δ CVR", "% Δ Sessions"]
        SPECIAL = {"% Total GBV"}

        available_abs   = [m for m in METRICS_ABS   if m in merged_df.columns]
        available_delta = [m for m in METRICS_DELTA if m in merged_df.columns]

        # KPI cards — dernière ligne complète
        last = merged_df.dropna(subset=available_abs[:1]).iloc[-1] if available_abs else None
        if last is not None:
            st.markdown("#### KPIs — Dernier mois disponible")
            kpi_cols = st.columns(len(available_abs))
            for i, m in enumerate(available_abs):
                val = last.get(m, np.nan)
                # CVR : ratio décimal → multiplier par 100
                val_display = val * 100 if m == "CVR" else val
                decimals = 2 if m in ("AOV", "CVR") else 0
                suffix = " %" if m == "CVR" else (" €" if m in ("AOV", "Gross Revenue", "GBV") else "")
                delta_col = DELTA_MAP.get(m)
                dval = last.get(delta_col, np.nan) if delta_col and delta_col in merged_df.columns else np.nan
                with kpi_cols[i]:
                    st.metric(m, fmt_num(val_display, decimals) + suffix,
                              f"{dval*100:+.1f}%" if m == "CVR" and not pd.isna(dval) else
                              (f"{dval:+.1f}%" if not pd.isna(dval) else None))

        # Graphiques double-axe
        st.markdown("#### Clics SEO vs Métriques Business")
        # Copie pour affichage CVR en %
        merged_display = merged_df.copy()
        if "CVR" in merged_display.columns:
            merged_display["CVR"] = merged_display["CVR"] * 100
        for metric in available_abs:
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(go.Bar(
                x=merged_display["date_key"], y=merged_display["seo_clicks"],
                name="Clics SEO", marker_color=BRAND_ORANGE, opacity=0.6
            ), secondary_y=False)
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
                title=f"Clics SEO & {metric}",
                plot_bgcolor="white", height=380,
                legend=dict(orientation="h", y=-0.2)
            )
            fig2.update_yaxes(title_text="Clics SEO", secondary_y=False)
            fig2.update_yaxes(title_text=metric, secondary_y=True)
            st.plotly_chart(fig2, use_container_width=True)

        # Graphique variations %
        if available_delta:
            st.markdown("#### Évolution des variations (%)")
            fig_delta = go.Figure()
            for m in available_delta:
                fig_delta.add_trace(go.Scatter(
                    x=merged_df["date_key"], y=merged_df[m],
                    name=m, mode="lines+markers"
                ))
            fig_delta.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_delta.update_layout(plot_bgcolor="white", height=380,
                                    yaxis_title="%")
            st.plotly_chart(fig_delta, use_container_width=True)

        with st.expander("📋 Tableau complet fusionné"):
            st.dataframe(merged_df, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CORRÉLATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    if merged_df is None:
        st.info("👆 Importe un fichier CSV dans la sidebar pour voir les corrélations.")
    else:
        available_abs = [m for m in ["Purchases","AOV","Gross Revenue","GBV","CVR","Sessions"]
                         if m in merged_df.columns]
        corr_data = []
        for m in available_abs:
            sub = merged_df[["seo_clicks", m]].dropna()
            if len(sub) < 3:
                continue
            r = np.corrcoef(sub["seo_clicks"], sub[m])[0, 1]
            corr_data.append({"Métrique": m, "r": r, "R²": r**2, "N": len(sub),
                               "Interprétation": (
                                   "Forte +" if r > 0.7 else
                                   "Modérée +" if r > 0.4 else
                                   "Forte −" if r < -0.7 else
                                   "Modérée −" if r < -0.4 else "Faible")})

        if corr_data:
            corr_df = pd.DataFrame(corr_data)
            st.markdown("#### Tableau de synthèse")
            st.dataframe(corr_df.style.format({"r":"{:.3f}","R²":"{:.3f}"}),
                         use_container_width=True)

            # Bar chart coefficients
            fig_r = px.bar(corr_df, x="Métrique", y="r",
                           color="r", color_continuous_scale=["red","white","green"],
                           range_color=[-1, 1], title="Coefficients de corrélation (r)")
            fig_r.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_r.update_layout(plot_bgcolor="white", height=350)
            st.plotly_chart(fig_r, use_container_width=True)

            # Scatter plots
            st.markdown("#### Scatter plots — Clics SEO vs Métriques")
            cols_scatter = st.columns(min(len(available_abs), 2))
            for i, m in enumerate(available_abs):
                sub = merged_df[["date_key","seo_clicks", m]].dropna()
                if len(sub) < 3:
                    continue
                x, y = sub["seo_clicks"].values, sub[m].values
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                r = np.corrcoef(x, y)[0,1]
                x_line = np.linspace(x.min(), x.max(), 100)

                fig_s = go.Figure()
                fig_s.add_trace(go.Scatter(
                    x=x, y=y, mode="markers+text",
                    text=sub["date_key"], textposition="top center",
                    marker=dict(color=BRAND_ORANGE, size=9),
                    name="Données"
                ))
                fig_s.add_trace(go.Scatter(
                    x=x_line, y=p(x_line), mode="lines",
                    line=dict(color=BRAND_BLUE, dash="dash"), name="Tendance"
                ))
                fig_s.update_layout(
                    title=f"{m} — r={r:.3f} | R²={r**2:.3f}",
                    xaxis_title="Clics SEO", yaxis_title=m,
                    plot_bgcolor="white", height=380,
                    showlegend=False
                )
                with cols_scatter[i % 2]:
                    st.plotly_chart(fig_s, use_container_width=True)

            # Matrice de corrélation
            st.markdown("#### Matrice de corrélation")
            all_num_cols = ["seo_clicks"] + available_abs
            corr_matrix = merged_df[all_num_cols].corr()
            fig_mat = px.imshow(
                corr_matrix, text_auto=".2f",
                color_continuous_scale="RdBu", zmin=-1, zmax=1,
                title="Corrélations toutes métriques"
            )
            fig_mat.update_layout(height=400)
            st.plotly_chart(fig_mat, use_container_width=True)
        else:
            st.warning("Pas assez de données pour calculer les corrélations.")
