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

# ── STATIC SEO CLICKS DATA ────────────────────────────────────────────────────
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
    "Mar-26": 50700,   # March 2026 partial
}

# ── NON-BRAND CLICKS ──────────────────────────────────────────────────────────
SEO_NON_BRAND = {
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
    "Mar-26": 42996,   # partial
}

# ── BRAND CLICKS ──────────────────────────────────────────────────────────────
SEO_BRAND = {
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
    "Mar-26": 7704,    # partial
}

# ── TOP PAGES 2025 ────────────────────────────────────────────────────────────
TOP_PAGES_2025 = [
    {"page": "Weekend Ideas", "clics": 897074},
    {"page": "Stay",          "clics": 616771},
    {"page": "Home",          "clics": 311461},
    {"page": "Hotels",        "clics": 189581},
    {"page": "Cities",        "clics": 143927},
    {"page": "Last minute",   "clics": 106691},
]

MONTH_MAP = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
             "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}

BRAND_ORANGE = "#FF6B00"
BRAND_BLUE   = "#1E3A5F"
COLOR_NB     = "#FF6B00"   # orange = non-brand
COLOR_B      = "#2ca02c"   # green  = brand
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
            "nb_clicks":  SEO_NON_BRAND.get(key, 0),
            "b_clicks":   SEO_BRAND.get(key, 0),
            "partial":    key == PARTIAL_KEY,
        })
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

MONTH_NAMES_FULL = {
    "january":"Jan","february":"Feb","march":"Mar","april":"Apr",
    "may":"May","june":"Jun","july":"Jul","august":"Aug",
    "september":"Sep","october":"Oct","november":"Nov","december":"Dec"
}

def normalize_date_key(raw):
    """Convert 'March 2026' or 'Mar-26' → 'Mar-26'."""
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
    """Parse Tableau unpivot CSV export. Only keeps rows where Dimension 1 = 'seo'."""
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
        st.error(f"Missing columns in CSV: {missing}. Found: {list(df.columns)}")
        return None

    # Filter Dimension 1 = 'seo' only
    df = df[df[col_map["dim"]].astype(str).str.strip().str.lower() == "seo"].copy()
    if df.empty:
        st.warning("No rows found with Dimension 1 = 'seo'.")
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

MONTH_TICKS  = list(range(1, 13))
MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Weekendesk_logo.svg/320px-Weekendesk_logo.svg.png",
             use_column_width=True)
    st.markdown("---")
    st.markdown("### 📂 Import Data")
    uploaded = st.file_uploader(
        "CSV file (Tableau export)", type=["csv"],
        help="Only rows with Dimension 1 = 'seo' are used."
    )
    st.markdown("---")
    st.markdown("### 🔍 Filters")
    years_available = sorted({2000+int(k.split("-")[1]) for k in SEO_CLICKS_RAW})
    selected_years = st.multiselect("Years", years_available, default=years_available)
    st.markdown("---")
    st.caption("🏖️ Weekendesk SEO Vision v2.0")

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🏖️ Weekendesk SEO Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">SEO & Business Performance Monitoring — Brand / Non-Brand</p>', unsafe_allow_html=True)
st.markdown("---")

# ── BUILD DATA ────────────────────────────────────────────────────────────────
seo_df = build_seo_df()
seo_filtered = seo_df[seo_df["year"].isin(selected_years)]

if seo_df[seo_df["partial"]].shape[0] > 0:
    st.info("ℹ️ March 2026: partial data (≈ first 18 days of the month).", icon="📅")

biz_df = None
merged_df = None
if uploaded:
    biz_df = parse_csv(uploaded)
    if biz_df is not None:
        merged_df = seo_df.merge(biz_df, on="date_key", how="inner")
        merged_df = merged_df.sort_values("date").reset_index(drop=True)
        if merged_df.empty:
            st.warning("No match found between CSV dates and SEO data.")
            merged_df = None

# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab_yoy, tab2, tab3, tab_top = st.tabs([
    "📈 SEO Clicks",
    "📊 YoY Comparison",
    "💼 Business Performance",
    "🔗 Correlations",
    "🏆 Top Pages 2025",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SEO CLICKS (Brand / Non-Brand / Total)
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    last_full = seo_df[~seo_df["partial"]]
    latest = last_full.iloc[-1]
    prev   = last_full.iloc[-2]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        d = (latest["nb_clicks"] / prev["nb_clicks"] - 1) * 100
        st.metric("Non-Brand Clicks (latest month)", fmt_num(latest["nb_clicks"]),
                  f"{d:+.1f}% vs prev. month")
    with col2:
        d = (latest["b_clicks"] / prev["b_clicks"] - 1) * 100
        st.metric("Brand Clicks (latest month)", fmt_num(latest["b_clicks"]),
                  f"{d:+.1f}% vs prev. month")
    with col3:
        nb_2025 = seo_df[seo_df["year"] == 2025]["nb_clicks"].sum()
        st.metric("Total Non-Brand 2025", fmt_num(nb_2025))
    with col4:
        nb_ytd = seo_df[seo_df["year"] == 2026]["nb_clicks"].sum()
        nb_same = seo_df[
            (seo_df["year"] == 2025) &
            (seo_df["month_num"].isin(seo_df[seo_df["year"] == 2026]["month_num"]))
        ]["nb_clicks"].sum()
        d_ytd = (nb_ytd / nb_same - 1) * 100 if nb_same else 0
        st.metric("Non-Brand 2026 (YTD)", fmt_num(nb_ytd), f"{d_ytd:+.1f}% YoY")

    st.markdown("---")

    series_choice = st.multiselect(
        "Series to display",
        ["Total SEO", "Non-Brand", "Brand"],
        default=["Total SEO", "Non-Brand", "Brand"],
    )

    series_cfg = {
        "Total SEO": ("seo_clicks", BRAND_BLUE,   "solid"),
        "Non-Brand": ("nb_clicks",  COLOR_NB,      "solid"),
        "Brand":     ("b_clicks",   COLOR_B,        "dot"),
    }

    st.markdown("#### Monthly SEO Click Trends")
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
                    hovertemplate=f"%{{y:,.0f}} clicks<extra>{trace_name}</extra>"
                ))
            if not partial.empty:
                fig_line.add_trace(go.Scatter(
                    x=partial["month_num"], y=partial[col_k],
                    mode="markers", name=f"{trace_name} (partial)",
                    marker=dict(symbol="circle-open", size=10,
                                color=color, line=dict(width=2)),
                    showlegend=True
                ))
    fig_line.update_layout(
        xaxis=dict(tickvals=MONTH_TICKS, ticktext=MONTH_LABELS),
        yaxis_title="SEO Clicks", plot_bgcolor="white",
        legend=dict(orientation="h", y=-0.25), hovermode="x unified",
        height=560
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("#### Heatmap – Non-Brand Clicks")
    nb_pivot = seo_filtered.pivot_table(index="year", columns="month_num",
                                        values="nb_clicks", aggfunc="first")
    nb_pivot.columns = MONTH_LABELS[:len(nb_pivot.columns)]
    fig_nb = px.imshow(nb_pivot, text_auto=True, aspect="auto",
                       color_continuous_scale=[[0,"#fff"],[1, BRAND_ORANGE]],
                       labels=dict(color="Non-Brand Clicks"))
    fig_nb.update_traces(texttemplate="%{z:,.0f}")
    fig_nb.update_layout(height=200 + 80*len(nb_pivot))
    st.plotly_chart(fig_nb, use_container_width=True)

    st.markdown("#### Heatmap – Brand Clicks")
    b_pivot = seo_filtered.pivot_table(index="year", columns="month_num",
                                       values="b_clicks", aggfunc="first")
    b_pivot.columns = MONTH_LABELS[:len(b_pivot.columns)]
    fig_bp = px.imshow(b_pivot, text_auto=True, aspect="auto",
                       color_continuous_scale=[[0,"#fff"],[1, COLOR_B]],
                       labels=dict(color="Brand Clicks"))
    fig_bp.update_traces(texttemplate="%{z:,.0f}")
    fig_bp.update_layout(height=200 + 80*len(b_pivot))
    st.plotly_chart(fig_bp, use_container_width=True)

    with st.expander("📋 Raw SEO Data"):
        disp = seo_filtered[["date_key","year","month_abbr","seo_clicks","nb_clicks","b_clicks","partial"]].copy()
        disp.columns = ["Date Key","Year","Month","Total SEO","Non-Brand","Brand","Partial"]
        st.dataframe(disp.style.format({"Total SEO":"{:,.0f}","Non-Brand":"{:,.0f}","Brand":"{:,.0f}"}),
                     use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB YoY — YEAR-OVER-YEAR COMPARISON
# ═══════════════════════════════════════════════════════════════════════════════
with tab_yoy:
    st.markdown("#### YoY Comparison – 2025 vs 2026")

    yoy_type = st.radio(
        "Click type", ["Total SEO", "Non-Brand", "Brand"], horizontal=True
    )
    yoy_col_map = {
        "Total SEO": ("seo_clicks", "Total SEO Clicks"),
        "Non-Brand": ("nb_clicks",  "Non-Brand Clicks"),
        "Brand":     ("b_clicks",   "Brand Clicks"),
    }
    yoy_col, yoy_label = yoy_col_map[yoy_type]

    df25 = seo_df[seo_df["year"] == 2025].set_index("month_num")[yoy_col]
    df26 = seo_df[seo_df["year"] == 2026].set_index("month_num")[yoy_col]
    common = sorted(set(df25.index) & set(df26.index))

    if common:
        bar_df = pd.DataFrame({
            "Month": [MONTH_LABELS[m-1] for m in common],
            "2025":  [df25[m] for m in common],
            "2026":  [df26[m] for m in common],
        })
        bar_df["Δ YoY (%)"] = (bar_df["2026"] / bar_df["2025"] - 1) * 100

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=bar_df["Month"], y=bar_df["2025"], name="2025",
                                 marker_color="#aec7e8"))
        fig_bar.add_trace(go.Bar(x=bar_df["Month"], y=bar_df["2026"], name="2026",
                                 marker_color=BRAND_ORANGE))
        fig_bar.update_layout(barmode="group", height=520, plot_bgcolor="white",
                               yaxis_title=yoy_label, hovermode="x unified",
                               title=f"{yoy_label} — 2025 vs 2026")
        st.plotly_chart(fig_bar, use_container_width=True)

        fig_delta = go.Figure(go.Bar(
            x=bar_df["Month"], y=bar_df["Δ YoY (%)"],
            marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in bar_df["Δ YoY (%)"]],
            text=[f"{v:+.1f}%" for v in bar_df["Δ YoY (%)"]],
            textposition="outside",
        ))
        fig_delta.add_hline(y=0, line_dash="dash", line_color="grey")
        fig_delta.update_layout(
            title=f"YoY % Change — {yoy_label}",
            yaxis_title="% Δ", plot_bgcolor="white", height=420
        )
        st.plotly_chart(fig_delta, use_container_width=True)
    else:
        st.info("Not enough common data between 2025 and 2026.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUSINESS PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    if merged_df is None:
        st.info(
            "👆 Upload a CSV file in the sidebar to view business metrics.\n\n"
            "**Expected format:** `Dimension 1 | Date | Measure Names | Measure Values`\n\n"
            "ℹ️ Only rows with `Dimension 1 = seo` are used."
        )
    else:
        METRICS_ABS   = ["Purchases", "AOV", "Gross Revenue", "GBV", "CVR", "Sessions"]
        METRICS_DELTA = ["% Δ Purchases", "% Δ AOV", "% Δ Gross Revenue",
                         "% Δ GBV vs LP", "% Δ CVR", "% Δ Sessions"]

        available_abs   = [m for m in METRICS_ABS   if m in merged_df.columns]
        available_delta = [m for m in METRICS_DELTA if m in merged_df.columns]

        last = merged_df.dropna(subset=available_abs[:1]).iloc[-1] if available_abs else None
        if last is not None:
            st.markdown("#### KPIs — Latest Available Month")
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

        st.markdown("#### SEO Clicks (Non-Brand + Brand) vs Business Metrics")
        merged_display = merged_df.copy()
        if "CVR" in merged_display.columns:
            merged_display["CVR"] = merged_display["CVR"] * 100

        for metric in available_abs:
            fig2 = make_subplots(specs=[[{"secondary_y": True}]])
            fig2.add_trace(go.Bar(
                x=merged_display["date_key"], y=merged_display["nb_clicks"],
                name="Non-Brand", marker_color=BRAND_ORANGE, opacity=0.7
            ), secondary_y=False)
            fig2.add_trace(go.Bar(
                x=merged_display["date_key"], y=merged_display["b_clicks"],
                name="Brand", marker_color="#aec7e8", opacity=0.7
            ), secondary_y=False)
            fig2.add_trace(go.Scatter(
                x=merged_display["date_key"], y=merged_display[metric],
                name=metric, mode="lines+markers",
                line=dict(color=BRAND_BLUE, width=2.5), marker=dict(size=7)
            ), secondary_y=True)
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
                title=f"SEO Clicks & {metric}", barmode="stack",
                plot_bgcolor="white", height=500,
                legend=dict(orientation="h", y=-0.2)
            )
            fig2.update_yaxes(title_text="SEO Clicks (stacked)", secondary_y=False)
            fig2.update_yaxes(title_text=metric, secondary_y=True)
            st.plotly_chart(fig2, use_container_width=True)

        if available_delta:
            st.markdown("#### % Change Metrics Over Time")
            fig_delta = go.Figure()
            for m in available_delta:
                fig_delta.add_trace(go.Scatter(
                    x=merged_df["date_key"], y=merged_df[m],
                    name=m, mode="lines+markers"
                ))
            fig_delta.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_delta.update_layout(plot_bgcolor="white", height=460, yaxis_title="%")
            st.plotly_chart(fig_delta, use_container_width=True)

        with st.expander("📋 Full Merged Data"):
            st.dataframe(merged_df.rename(columns={
                "seo_clicks": "Total SEO", "nb_clicks": "Non-Brand", "b_clicks": "Brand"
            }), use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CORRELATIONS
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    if merged_df is None:
        st.info("👆 Upload a CSV file in the sidebar to view correlations.")
    else:
        available_abs = [m for m in ["Purchases","AOV","Gross Revenue","GBV","CVR","Sessions"]
                         if m in merged_df.columns]

        corr_type = st.radio(
            "Correlate with", ["Total SEO", "Non-Brand", "Brand"], horizontal=True
        )
        corr_col_map = {
            "Total SEO": "seo_clicks", "Non-Brand": "nb_clicks", "Brand": "b_clicks"
        }
        corr_col = corr_col_map[corr_type]

        corr_data = []
        for m in available_abs:
            sub = merged_df[[corr_col, m]].dropna()
            if len(sub) < 3:
                continue
            r = np.corrcoef(sub[corr_col], sub[m])[0, 1]
            corr_data.append({"Metric": m, "r": r, "R²": r**2, "N": len(sub),
                               "Interpretation": (
                                   "Strong +" if r > 0.7 else
                                   "Moderate +" if r > 0.4 else
                                   "Strong −" if r < -0.7 else
                                   "Moderate −" if r < -0.4 else "Weak")})

        if corr_data:
            corr_df = pd.DataFrame(corr_data)
            st.markdown(f"#### Correlation Summary — {corr_type}")
            st.dataframe(corr_df.style.format({"r":"{:.3f}","R²":"{:.3f}"}),
                         use_container_width=True)

            fig_r = px.bar(corr_df, x="Metric", y="r",
                           color="r", color_continuous_scale=["red","white","green"],
                           range_color=[-1, 1],
                           title=f"Correlation Coefficients (r) — {corr_type}")
            fig_r.add_hline(y=0, line_dash="dash", line_color="grey")
            fig_r.update_layout(plot_bgcolor="white", height=440)
            st.plotly_chart(fig_r, use_container_width=True)

            # ── GBV IMPACT FOCUS ─────────────────────────────────────────────
            if "GBV" in merged_df.columns:
                st.markdown("---")
                st.markdown("#### 🎯 GBV Impact — Non-Brand vs Brand Clicks")

                sub_gbv = merged_df[["date_key", "nb_clicks", "b_clicks", "GBV"]].dropna().reset_index(drop=True)
                if not sub_gbv.empty:
                    sub_gbv["δ_nb"]  = sub_gbv["nb_clicks"].pct_change() * 100
                    sub_gbv["δ_b"]   = sub_gbv["b_clicks"].pct_change() * 100
                    sub_gbv["δ_gbv"] = sub_gbv["GBV"].pct_change() * 100

                    fig_gbv_time = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_gbv_time.add_trace(go.Bar(
                        x=sub_gbv["date_key"], y=sub_gbv["nb_clicks"],
                        name="Non-Brand", marker_color=BRAND_ORANGE, opacity=0.7
                    ), secondary_y=False)
                    fig_gbv_time.add_trace(go.Bar(
                        x=sub_gbv["date_key"], y=sub_gbv["b_clicks"],
                        name="Brand", marker_color=COLOR_B, opacity=0.7
                    ), secondary_y=False)
                    fig_gbv_time.add_trace(go.Scatter(
                        x=sub_gbv["date_key"], y=sub_gbv["GBV"],
                        name="GBV", mode="lines+markers",
                        line=dict(color=BRAND_BLUE, width=3),
                        marker=dict(size=8, symbol="diamond"),
                    ), secondary_y=True)

                    for _, row in sub_gbv.iterrows():
                        if pd.isna(row["δ_nb"]):
                            continue
                        fig_gbv_time.add_annotation(
                            x=row["date_key"],
                            y=row["nb_clicks"] + row["b_clicks"],
                            text=f"NB {row['δ_nb']:+.1f}%",
                            showarrow=False, yref="y",
                            font=dict(size=8, color="darkorange"),
                            yshift=18,
                        )
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
                        title="GBV vs Non-Brand & Brand Clicks — MoM % Changes",
                        margin=dict(t=60),
                    )
                    fig_gbv_time.update_yaxes(title_text="SEO Clicks (stacked)", secondary_y=False)
                    fig_gbv_time.update_yaxes(title_text="GBV (€)", secondary_y=True)
                    st.plotly_chart(fig_gbv_time, use_container_width=True)

                # ── Dec / Jan / Feb — YoY comparison ─────────────────────────
                compare_pairs = [
                    ("December", "Dec-24", "Dec-25"),
                    ("January",  "Jan-25", "Jan-26"),
                    ("February", "Feb-25", "Feb-26"),
                ]
                rows_yoy = []
                for month_label, key_n1, key_n in compare_pairs:
                    for year_key, year_label in [(key_n1, "N-1"), (key_n, "N")]:
                        row = merged_df[merged_df["date_key"] == year_key]
                        if row.empty:
                            continue
                        r = row.iloc[0]
                        rows_yoy.append({
                            "Month":     month_label,
                            "Year":      year_label,
                            "Key":       year_key,
                            "Non-Brand": r.get("nb_clicks", np.nan),
                            "Brand":     r.get("b_clicks",  np.nan),
                            "GBV":       r.get("GBV",        np.nan),
                        })

                if rows_yoy:
                    yoy_df = pd.DataFrame(rows_yoy)
                    yoy_summary = []
                    for month in ["December", "January", "February"]:
                        sub_m = yoy_df[yoy_df["Month"] == month].set_index("Year")
                        if "N-1" not in sub_m.index or "N" not in sub_m.index:
                            continue
                        for col in ["Non-Brand", "Brand", "GBV"]:
                            v_n1 = sub_m.loc["N-1", col]
                            v_n  = sub_m.loc["N",   col]
                            delta = (v_n / v_n1 - 1) * 100 if v_n1 else np.nan
                            yoy_summary.append({
                                "Month": month, "Metric": col,
                                "N-1": v_n1, "N": v_n, "Δ% YoY": delta
                            })

                    st.markdown("#### 📅 Dec / Jan / Feb — YoY Comparison")

                    months_order = ["December", "January", "February"]
                    yoy_df["Total Clicks"] = yoy_df["Non-Brand"].fillna(0) + yoy_df["Brand"].fillna(0)

                    n1_rows = yoy_df[yoy_df["Year"] == "N-1"].set_index("Month")
                    n_rows  = yoy_df[yoy_df["Year"] == "N"].set_index("Month")
                    month_labels = [m for m in months_order if m in n1_rows.index and m in n_rows.index]

                    fig_jf = go.Figure()

                    nb_n1_vals = [n1_rows.loc[m, "Non-Brand"] for m in month_labels]
                    b_n1_vals  = [n1_rows.loc[m, "Brand"]     for m in month_labels]
                    nb_n_vals  = [n_rows.loc[m, "Non-Brand"]  for m in month_labels]
                    b_n_vals   = [n_rows.loc[m, "Brand"]      for m in month_labels]

                    def fmt_k(v):
                        return f"{v/1000:.0f}k" if not pd.isna(v) else ""

                    fig_jf.add_trace(go.Bar(
                        name="N-1 Non-Brand",
                        x=month_labels, y=nb_n1_vals,
                        offsetgroup="n1",
                        marker_color="#FFB37A",
                        text=[fmt_k(v) for v in nb_n1_vals],
                        textposition="inside",
                        textfont=dict(size=11, color="#7a3800"),
                        hovertemplate="<b>%{x} N-1 Non-Brand</b><br>%{y:,.0f}<extra></extra>",
                    ))
                    fig_jf.add_trace(go.Bar(
                        name="N-1 Brand",
                        x=month_labels, y=b_n1_vals,
                        offsetgroup="n1",
                        marker_color="#98D8A0",
                        text=[fmt_k(v) for v in b_n1_vals],
                        textposition="inside",
                        textfont=dict(size=11, color="#1a5c2a"),
                        hovertemplate="<b>%{x} N-1 Brand</b><br>%{y:,.0f}<extra></extra>",
                    ))
                    fig_jf.add_trace(go.Bar(
                        name="N Non-Brand",
                        x=month_labels, y=nb_n_vals,
                        offsetgroup="n",
                        marker_color=COLOR_NB,
                        text=[fmt_k(v) for v in nb_n_vals],
                        textposition="inside",
                        textfont=dict(size=11, color="white"),
                        hovertemplate="<b>%{x} N Non-Brand</b><br>%{y:,.0f}<extra></extra>",
                    ))
                    fig_jf.add_trace(go.Bar(
                        name="N Brand",
                        x=month_labels, y=b_n_vals,
                        offsetgroup="n",
                        marker_color=COLOR_B,
                        text=[fmt_k(v) for v in b_n_vals],
                        textposition="inside",
                        textfont=dict(size=11, color="white"),
                        hovertemplate="<b>%{x} N Brand</b><br>%{y:,.0f}<extra></extra>",
                    ))

                    for m in month_labels:
                        v_n1 = n1_rows.loc[m, "Total Clicks"]
                        v_n  = n_rows.loc[m, "Total Clicks"]
                        delta = (v_n / v_n1 - 1) * 100 if v_n1 else np.nan
                        if pd.isna(delta):
                            continue
                        color_d = "green" if delta >= 0 else "red"
                        fig_jf.add_annotation(
                            x=m, y=v_n,
                            text=f"<b>{delta:+.1f}%</b>",
                            showarrow=False,
                            font=dict(size=13, color=color_d),
                            yshift=16,
                        )

                    for m in month_labels:
                        gbv_n1 = n1_rows.loc[m, "GBV"] if "GBV" in n1_rows.columns else np.nan
                        gbv_n  = n_rows.loc[m, "GBV"]  if "GBV" in n_rows.columns  else np.nan
                        if pd.isna(gbv_n1) or pd.isna(gbv_n):
                            continue
                        delta_gbv = (gbv_n / gbv_n1 - 1) * 100 if gbv_n1 else np.nan
                        color_g = "green" if (not pd.isna(delta_gbv) and delta_gbv >= 0) else "red"
                        delta_txt = f" ({delta_gbv:+.1f}%)" if not pd.isna(delta_gbv) else ""
                        fig_jf.add_annotation(
                            x=m, y=0,
                            text=f"GBV: {gbv_n1:,.0f} → {gbv_n:,.0f}{delta_txt}".replace(",", "\u202f"),
                            showarrow=False,
                            font=dict(size=10, color=color_g),
                            yshift=-36,
                            yref="y",
                        )

                    fig_jf.update_layout(
                        barmode="stack", plot_bgcolor="white", height=520,
                        margin=dict(b=80),
                        yaxis_title="SEO Clicks (Non-Brand + Brand)",
                        legend=dict(orientation="h", y=-0.12),
                        title="Dec / Jan / Feb — Non-Brand (orange) vs Brand (green) · N-1 vs N",
                        hovermode="x unified",
                    )
                    st.plotly_chart(fig_jf, use_container_width=True)

                # Scatter: GBV vs Non-Brand | GBV vs Brand
                col_left, col_right = st.columns(2)
                for col_ui, click_col, label, color in [
                    (col_left,  "nb_clicks", "Non-Brand", BRAND_ORANGE),
                    (col_right, "b_clicks",  "Brand",     COLOR_B),
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
                        marker=dict(color=color, size=10), name="Data"
                    ))
                    fig_sc.add_trace(go.Scatter(
                        x=x_line, y=p_fn(x_line), mode="lines",
                        line=dict(color=BRAND_BLUE, dash="dash", width=2),
                        name="Trend"
                    ))
                    fig_sc.update_layout(
                        title=f"GBV vs {label}<br>r={r:.3f} | R²={r**2:.3f}",
                        xaxis_title=f"{label} Clicks", yaxis_title="GBV (€)",
                        plot_bgcolor="white", height=500, showlegend=False
                    )
                    with col_ui:
                        st.plotly_chart(fig_sc, use_container_width=True)

                # ── Excel Export ──────────────────────────────────────────────
                if not sub_gbv.empty:
                    export_df = sub_gbv.rename(columns={
                        "date_key":  "Month",
                        "nb_clicks": "Non-Brand Clicks",
                        "b_clicks":  "Brand Clicks",
                        "GBV":       "GBV (€)",
                        "δ_nb":      "Δ% Non-Brand MoM",
                        "δ_b":       "Δ% Brand MoM",
                        "δ_gbv":     "Δ% GBV MoM",
                    })

                    corr_rows = []
                    for lbl, col_k in [("Non-Brand", "Non-Brand Clicks"),
                                        ("Brand",     "Brand Clicks")]:
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
                        export_df.to_excel(writer, sheet_name="GBV Data", index=False)
                        corr_export.to_excel(writer, sheet_name="Correlations", index=False)
                    buf.seek(0)

                    st.download_button(
                        label="📥 Export to Excel — GBV Click Impact",
                        data=buf,
                        file_name="weekendesk_gbv_clicks.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                st.markdown("---")

            st.markdown(f"#### Scatter Plots — {corr_type} vs Metrics")
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
                    marker=dict(color=BRAND_ORANGE, size=9), name="Data"
                ))
                fig_s.add_trace(go.Scatter(
                    x=x_line, y=p(x_line), mode="lines",
                    line=dict(color=BRAND_BLUE, dash="dash"), name="Trend"
                ))
                fig_s.update_layout(
                    title=f"{m} — r={r:.3f} | R²={r**2:.3f}",
                    xaxis_title=corr_type, yaxis_title=m,
                    plot_bgcolor="white", height=500, showlegend=False
                )
                with cols_scatter[i % 2]:
                    st.plotly_chart(fig_s, use_container_width=True)

            st.markdown("#### Correlation Matrix")
            all_num_cols = ["seo_clicks", "nb_clicks", "b_clicks"] + available_abs
            present_cols = [c for c in all_num_cols if c in merged_df.columns]
            corr_matrix = merged_df[present_cols].rename(columns={
                "seo_clicks": "Total SEO", "nb_clicks": "Non-Brand", "b_clicks": "Brand"
            }).corr()
            fig_mat = px.imshow(
                corr_matrix, text_auto=".2f",
                color_continuous_scale="RdBu", zmin=-1, zmax=1,
                title="Full Correlation Matrix"
            )
            fig_mat.update_layout(height=460)
            st.plotly_chart(fig_mat, use_container_width=True)
        else:
            st.warning("Not enough data to compute correlations.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB TOP PAGES — 2025 ANNUAL RANKING
# ═══════════════════════════════════════════════════════════════════════════════
with tab_top:
    st.markdown("#### 🏆 Top SEO Pages Annual Ranking – 2025 (12 months)")

    df_top = pd.DataFrame(TOP_PAGES_2025)
    total_top = df_top["clics"].sum()
    df_top["% of total"] = (df_top["clics"] / total_top * 100).round(1)
    df_top["rank"] = range(1, len(df_top) + 1)

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
            for c, p in zip(df_top["clics"], df_top["% of total"])
        ],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Clicks: %{x:,.0f}<extra></extra>",
    ))
    fig_top.update_layout(
        xaxis_title="SEO Clicks (annual 2025)",
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="white",
        height=500,
        margin=dict(l=120, r=200),
    )
    st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("#### Details")
    df_display = df_top[["rank", "page", "clics", "% of total"]].copy()
    df_display["clicks_fmt"] = df_display["clics"].apply(fmt_num)
    df_display["% of total"] = df_display["% of total"].apply(lambda x: f"{x:.1f}%")
    st.dataframe(
        df_display[["rank", "page", "clicks_fmt", "% of total"]].rename(columns={
            "rank": "Rank", "page": "Page",
            "clicks_fmt": "SEO Clicks 2025", "% of total": "Share of Total",
        }),
        use_container_width=True, hide_index=True,
    )

    total_seo_2025 = seo_df[seo_df["year"] == 2025]["seo_clicks"].sum()
    st.caption(
        f"Top 6 pages total: {fmt_num(total_top)} clicks  |  "
        f"Overall SEO total 2025: {fmt_num(total_seo_2025)} clicks"
    )
