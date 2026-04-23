"""
Stock Valuation Dashboard — Streamlit App
------------------------------------------
Install dependencies:
    pip install streamlit yfinance pandas plotly

Run:
    streamlit run app.py
"""

import math
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Valuation",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .stApp { background-color: #0f1117; }

    /* Ticker header */
    .ticker-header {
        font-family: 'DM Mono', monospace;
        font-size: 2rem;
        font-weight: 500;
        color: #e8f4f8;
        letter-spacing: 0.05em;
    }
    .ticker-price {
        font-family: 'DM Mono', monospace;
        font-size: 1.5rem;
        color: #4ade80;
    }

    /* Metric cards */
    .metric-card {
        background: #1a1d27;
        border: 1px solid #2a2d3a;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
    }
    .metric-label {
        font-size: 0.7rem;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-family: 'DM Mono', monospace;
    }
    .metric-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e8f4f8;
        font-family: 'DM Mono', monospace;
        margin-top: 0.2rem;
    }
    .metric-value.positive { color: #4ade80; }
    .metric-value.negative { color: #f87171; }

    /* Section headers */
    .section-header {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #6b7280;
        font-family: 'DM Mono', monospace;
        border-bottom: 1px solid #2a2d3a;
        padding-bottom: 0.4rem;
        margin: 1.5rem 0 1rem 0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #13151f;
        border-right: 1px solid #2a2d3a;
    }
    [data-testid="stSidebar"] .stTextInput input {
        font-family: 'DM Mono', monospace;
        background: #1a1d27;
        border: 1px solid #2a2d3a;
        color: #e8f4f8;
        text-transform: uppercase;
    }

    /* Divider */
    hr { border-color: #2a2d3a; }

    /* Dataframe */
    [data-testid="stDataFrame"] { border: 1px solid #2a2d3a; border-radius: 8px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background: #1a1d27; border-radius: 8px; gap: 2px; }
    .stTabs [data-baseweb="tab"] { color: #6b7280; font-family: 'DM Mono', monospace; font-size: 0.8rem; }
    .stTabs [aria-selected="true"] { color: #e8f4f8; background: #2a2d3a; border-radius: 6px; }

    /* Valuation verdict */
    .verdict-undervalued {
        background: linear-gradient(135deg, #052e16, #14532d);
        border: 1px solid #16a34a;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        text-align: center;
    }
    .verdict-overvalued {
        background: linear-gradient(135deg, #2d0a0a, #450a0a);
        border: 1px solid #dc2626;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        text-align: center;
    }
    .verdict-label {
        font-family: 'DM Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #9ca3af;
    }
    .verdict-value {
        font-family: 'DM Mono', monospace;
        font-size: 1.8rem;
        font-weight: 500;
        margin-top: 0.2rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Imports from your modules ─────────────────────────────────────────────────
from financial_data import retrieve_data
from dcf import dcf_valuation


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_large(val):
    """Format large numbers as $XB / $XM."""
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"${val/1e12:.2f}T"
    if abs(val) >= 1e9:
        return f"${val/1e9:.2f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:.2f}M"
    return f"${val:,.0f}"

def fmt_pct(val):
    return f"{val*100:.2f}%" if val is not None else "N/A"

def fmt_price(val):
    return f"${val:,.2f}" if val is not None else "N/A"

def metric_card(label, value, color_class=""):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """, unsafe_allow_html=True)

PLOTLY_THEME = dict(
    paper_bgcolor="#0f1117",
    plot_bgcolor="#0f1117",
    font=dict(family="DM Mono, monospace", color="#9ca3af", size=11),
    xaxis=dict(gridcolor="#2a2d3a", linecolor="#2a2d3a", tickcolor="#2a2d3a"),
    yaxis=dict(gridcolor="#2a2d3a", linecolor="#2a2d3a", tickcolor="#2a2d3a"),
)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📈 Stock Valuation")
    st.markdown('<div class="section-header">Tickers</div>', unsafe_allow_html=True)

    ticker_input = st.text_input(
        "Enter tickers (comma-separated)",
        value="AAPL, MSFT",
        help="e.g. AAPL, MSFT, TSLA"
    )
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    st.markdown('<div class="section-header">DCF Assumptions</div>', unsafe_allow_html=True)

    discount_rate = st.slider(
        "Discount Rate (WACC)",
        min_value=0.05, max_value=0.20, value=0.10, step=0.005,
        format="%.1f%%",
        help="Weighted average cost of capital"
    )
    projection_years = st.slider(
        "Projection Years",
        min_value=3, max_value=10, value=5, step=1,
    )
    terminal_growth_rate = st.slider(
        "Terminal Growth Rate",
        min_value=0.01, max_value=0.05, value=0.03, step=0.005,
        format="%.1f%%",
        help="Long-run perpetual growth rate (~GDP growth)"
    )
    override_fcf_growth = st.checkbox("Override FCF Growth Rate", value=False)
    fcf_growth_override = None
    if override_fcf_growth:
        fcf_growth_override = st.slider(
            "FCF Growth Rate (Override)",
            min_value=-0.10, max_value=0.30, value=0.08, step=0.005,
            format="%.1f%%",
        )

    run = st.button("Run Analysis", type="primary", use_container_width=True)


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("## Stock Valuation Dashboard")
st.markdown("---")

if not run:
    st.markdown("""
    <div style="text-align:center; padding: 4rem; color: #4b5563;">
        <div style="font-family: DM Mono, monospace; font-size: 3rem; margin-bottom: 1rem;">📊</div>
        <div style="font-family: DM Mono, monospace; font-size: 0.9rem; letter-spacing: 0.1em;">
            Enter tickers and configure DCF assumptions in the sidebar, then click Run Analysis.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── Load data for each ticker ─────────────────────────────────────────────────
@st.cache_data(ttl=900)   # cache for 15 minutes
def load(ticker, dr, py, tgr, fgr_override):
    data   = retrieve_data(ticker)
    result = dcf_valuation(
        data,
        discount_rate=dr,
        projection_years=py,
        terminal_growth_rate=tgr,
        fcf_growth_rate_override=fgr_override,
    )
    return data, result

cols = st.columns(len(tickers))

for col, ticker in zip(cols, tickers):
    with col:
        with st.spinner(f"Loading {ticker}..."):
            try:
                data, dcf = load(ticker, discount_rate, projection_years, terminal_growth_rate, fcf_growth_override)
            except Exception as e:
                st.error(f"**{ticker}**: {e}")
                continue

        tech  = data["technical"]
        fund  = data["fundamental"]
        val   = fund["valuation"]
        ss    = fund["share_structure"]
        dcf_v = dcf["valuation"]
        dcf_a = dcf["assumptions"]

        # ── Header ────────────────────────────────────────────────────────────
        price_change = (
            (tech["current_price"] - tech["previous_close"]) / tech["previous_close"]
            if tech.get("current_price") and tech.get("previous_close") else None
        )
        change_color = "positive" if price_change and price_change >= 0 else "negative"
        change_str   = f"({'▲' if price_change and price_change >= 0 else '▼'} {fmt_pct(abs(price_change) if price_change else None)})"

        st.markdown(f'<div class="ticker-header">{ticker}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="ticker-price">{fmt_price(tech.get("current_price"))} '
            f'<span style="font-size:0.9rem; color: {"#4ade80" if change_color == "positive" else "#f87171"}">'
            f'{change_str}</span></div>',
            unsafe_allow_html=True
        )
        st.markdown("---")

        tabs = st.tabs(["Overview", "Financials", "DCF"])

        # ── Tab 1: Overview ───────────────────────────────────────────────────
        with tabs[0]:
            st.markdown('<div class="section-header">Price & Technicals</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                metric_card("Day Low / High",  f"{fmt_price(tech.get('day_low'))} — {fmt_price(tech.get('day_high'))}")
                metric_card("52W Low / High",  f"{fmt_price(tech.get('fifty_two_week_low'))} — {fmt_price(tech.get('fifty_two_week_high'))}")
                metric_card("50-Day MA",       fmt_price(tech.get("fifty_day_ma")))
                metric_card("200-Day MA",      fmt_price(tech.get("two_hundred_day_ma")))
            with c2:
                metric_card("Volume",          f"{tech.get('volume', 0):,.0f}" if tech.get('volume') else "N/A")
                metric_card("Avg Vol (10D)",   f"{tech.get('avg_volume_10d', 0):,.0f}" if tech.get('avg_volume_10d') else "N/A")
                metric_card("Beta",            f"{tech.get('beta'):.2f}" if tech.get('beta') else "N/A")
                metric_card("Prev Close",      fmt_price(tech.get("previous_close")))

            st.markdown('<div class="section-header">Valuation Multiples</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                metric_card("Market Cap",      fmt_large(val.get("market_cap")))
                metric_card("Enterprise Value",fmt_large(val.get("enterprise_value")))
                metric_card("P/E (TTM)",       f"{val.get('pe_ratio_ttm'):.1f}x" if val.get('pe_ratio_ttm') else "N/A")
                metric_card("Forward P/E",     f"{val.get('forward_pe'):.1f}x" if val.get('forward_pe') else "N/A")
            with c2:
                metric_card("EV/EBITDA",       f"{val.get('ev_to_ebitda'):.1f}x" if val.get('ev_to_ebitda') else "N/A")
                metric_card("Price/Book",      f"{val.get('price_to_book'):.2f}x" if val.get('price_to_book') else "N/A")
                metric_card("EPS (TTM)",       fmt_price(val.get("eps_ttm")))
                metric_card("Dividend Yield",  fmt_pct(val.get("dividend_yield")))

            st.markdown('<div class="section-header">OHLCV — Last 10 Days</div>', unsafe_allow_html=True)
            ohlcv = tech.get("ohlcv_history", [])
            if ohlcv:
                df_ohlcv = pd.DataFrame(ohlcv).set_index("date")
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                fig.add_trace(go.Candlestick(
                    x=df_ohlcv.index, open=df_ohlcv["open"], high=df_ohlcv["high"],
                    low=df_ohlcv["low"], close=df_ohlcv["close"],
                    increasing_line_color="#4ade80", decreasing_line_color="#f87171",
                    name="Price"
                ), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=df_ohlcv.index, y=df_ohlcv["volume"],
                    marker_color="#3b82f6", opacity=0.6, name="Volume"
                ), row=2, col=1)
                fig.update_layout(**PLOTLY_THEME, height=320, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
                fig.update_xaxes(rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 2: Financials ─────────────────────────────────────────────────
        with tabs[1]:
            def get_statement_df(statement, line_items):
                """Build a clean DataFrame for a financial statement."""
                rows = {}
                for item in line_items:
                    values = fund[statement]["annual"].get(item, {})
                    if values:
                        rows[item] = {d: v for d, v in sorted(values.items()) if v and not (isinstance(v, float) and math.isnan(v))}
                if not rows:
                    return pd.DataFrame()
                df = pd.DataFrame(rows).T
                df.columns = [c[:7] for c in df.columns]   # trim to YYYY-MM
                return df

            income_items = ["Total Revenue", "Gross Profit", "Operating Income", "EBITDA", "Net Income", "Basic EPS", "Diluted EPS"]
            balance_items = ["Total Assets", "Total Liabilities Net Minority Interest", "Stockholders Equity", "Cash And Cash Equivalents", "Total Debt", "Net Debt"]
            cf_items = ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow", "Investing Cash Flow", "Financing Cash Flow"]

            st.markdown('<div class="section-header">Income Statement</div>', unsafe_allow_html=True)
            df_inc = get_statement_df("income_statement", income_items)
            if not df_inc.empty:
                st.dataframe(df_inc.map(lambda x: fmt_large(x) if isinstance(x, float) else x), use_container_width=True)

                # Revenue & Net Income chart
                rev_data  = fund["income_statement"]["annual"].get("Total Revenue", {})
                ni_data   = fund["income_statement"]["annual"].get("Net Income", {})
                dates     = sorted(set(rev_data) & set(ni_data))
                fig = go.Figure()
                fig.add_trace(go.Bar(x=dates, y=[rev_data[d] for d in dates], name="Revenue", marker_color="#3b82f6", opacity=0.8))
                fig.add_trace(go.Bar(x=dates, y=[ni_data[d] for d in dates],  name="Net Income", marker_color="#4ade80", opacity=0.8))
                fig.update_layout(**PLOTLY_THEME, height=260, barmode="group",
                                  margin=dict(l=0, r=0, t=10, b=0),
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

            st.markdown('<div class="section-header">Balance Sheet</div>', unsafe_allow_html=True)
            df_bal = get_statement_df("balance_sheet", balance_items)
            if not df_bal.empty:
                st.dataframe(df_bal.map(lambda x: fmt_large(x) if isinstance(x, float) else x), use_container_width=True)

            st.markdown('<div class="section-header">Cash Flow Statement</div>', unsafe_allow_html=True)
            df_cf = get_statement_df("cash_flow", cf_items)
            if not df_cf.empty:
                st.dataframe(df_cf.map(lambda x: fmt_large(x) if isinstance(x, float) else x), use_container_width=True)

                # FCF chart
                fcf_data = fund["cash_flow"]["annual"].get("Free Cash Flow", {})
                ocf_data = fund["cash_flow"]["annual"].get("Operating Cash Flow", {})
                dates    = sorted(set(fcf_data) & set(ocf_data))
                fig = go.Figure()
                fig.add_trace(go.Bar(x=dates, y=[ocf_data[d] for d in dates], name="Operating CF", marker_color="#3b82f6", opacity=0.8))
                fig.add_trace(go.Bar(x=dates, y=[fcf_data[d] for d in dates], name="Free Cash Flow", marker_color="#a78bfa", opacity=0.8))
                fig.update_layout(**PLOTLY_THEME, height=260, barmode="group",
                                  margin=dict(l=0, r=0, t=10, b=0),
                                  legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 3: DCF ────────────────────────────────────────────────────────
        with tabs[2]:
            intrinsic = dcf_v.get("intrinsic_value")
            current   = dcf_v.get("current_price")
            mos       = dcf_v.get("margin_of_safety")

            # Verdict
            if intrinsic and current:
                is_under = intrinsic > current
                verdict_class = "verdict-undervalued" if is_under else "verdict-overvalued"
                verdict_text  = "UNDERVALUED" if is_under else "OVERVALUED"
                verdict_color = "#4ade80" if is_under else "#f87171"
                st.markdown(f"""
                <div class="{verdict_class}">
                    <div class="verdict-label">DCF Verdict</div>
                    <div class="verdict-value" style="color:{verdict_color}">{verdict_text}</div>
                    <div style="font-family: DM Mono, monospace; font-size: 0.85rem; color: #9ca3af; margin-top: 0.3rem;">
                        Intrinsic: {fmt_price(intrinsic)} &nbsp;|&nbsp; Market: {fmt_price(current)}<br>
                        Margin of Safety: {fmt_pct(mos)}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div class="section-header">Assumptions</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                metric_card("Discount Rate (WACC)",   fmt_pct(dcf_a.get("discount_rate")))
                metric_card("Projection Years",        str(dcf_a.get("projection_years")))
            with c2:
                metric_card("FCF Growth Rate",         fmt_pct(dcf_a.get("fcf_growth_rate")))
                metric_card("Terminal Growth Rate",    fmt_pct(dcf_a.get("terminal_growth_rate")))
            st.caption(f"FCF growth source: `{dcf_a.get('fcf_growth_source', 'N/A')}`")

            st.markdown('<div class="section-header">Valuation Bridge</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                metric_card("PV of FCFs",          fmt_large(dcf_v.get("total_pv_fcfs")))
                metric_card("PV Terminal Value",   fmt_large(dcf_v.get("pv_terminal_value")))
                metric_card("Enterprise Value",    fmt_large(dcf_v.get("enterprise_value")))
            with c2:
                metric_card("Net Debt",            fmt_large(dcf_v.get("net_debt")))
                metric_card("Equity Value",        fmt_large(dcf_v.get("equity_value")))
                metric_card("Shares Outstanding",  f"{dcf_v.get('shares_outstanding', 0)/1e9:.2f}B" if dcf_v.get('shares_outstanding') else "N/A")

            # Waterfall chart
            pv_fcfs = dcf_v.get("total_pv_fcfs", 0)
            pv_tv   = dcf_v.get("pv_terminal_value", 0)
            net_d   = dcf_v.get("net_debt", 0)
            eq_val  = dcf_v.get("equity_value", 0)
            fig = go.Figure(go.Waterfall(
                orientation="v",
                measure=["relative", "relative", "relative", "total"],
                x=["PV of FCFs", "PV Terminal Value", "Less: Net Debt", "Equity Value"],
                y=[pv_fcfs, pv_tv, -net_d, eq_val],
                connector=dict(line=dict(color="#2a2d3a")),
                increasing=dict(marker_color="#4ade80"),
                decreasing=dict(marker_color="#f87171"),
                totals=dict(marker_color="#3b82f6"),
                text=[fmt_large(pv_fcfs), fmt_large(pv_tv), fmt_large(-net_d), fmt_large(eq_val)],
                textposition="outside",
            ))
            fig.update_layout(**PLOTLY_THEME, height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown('<div class="section-header">Projected FCFs</div>', unsafe_allow_html=True)
            proj = dcf["projections"]
            hist_fcf = dcf["historical"]["fcf"]

            years_hist = list(hist_fcf.keys())
            vals_hist  = list(hist_fcf.values())
            years_proj = [f"Proj Y{i}" for i in range(1, len(proj)+1)]
            vals_proj  = [v["fcf"] for v in proj.values()]
            vals_pv    = [v["pv"] for v in proj.values()]

            fig = go.Figure()
            fig.add_trace(go.Bar(x=years_hist, y=vals_hist, name="Historical FCF", marker_color="#3b82f6", opacity=0.8))
            fig.add_trace(go.Bar(x=years_proj, y=vals_proj, name="Projected FCF",  marker_color="#a78bfa", opacity=0.8))
            fig.add_trace(go.Bar(x=years_proj, y=vals_pv,   name="PV of FCF",      marker_color="#4ade80", opacity=0.6))
            fig.update_layout(**PLOTLY_THEME, height=300, barmode="group",
                              margin=dict(l=0, r=0, t=10, b=0),
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)

            # Projections table
            proj_df = pd.DataFrame([
                {"Year": f"Year {i}", "Projected FCF": fmt_large(v["fcf"]), "PV of FCF": fmt_large(v["pv"])}
                for i, v in enumerate(proj.values(), start=1)
            ]).set_index("Year")
            st.dataframe(proj_df, use_container_width=True)