"""
Financial Data Retrieval using yfinance
----------------------------------------
Install dependency:  pip install yfinance pandas
Usage:
    from financial_data import retrieve_data
    data = retrieve_data("AAPL")
"""

import yfinance as yf
import math


def retrieve_data(ticker: str) -> dict:
    """
    Retrieve technical and fundamental financial data for a given ticker.

    Parameters
    ----------
    ticker : str
        A valid stock ticker symbol, e.g. "AAPL", "MSFT", "TSLA".

    Returns
    -------
    dict with two top-level keys:
        "technical"   — current price, OHLCV, moving averages, volume, etc.
        "fundamental" — share structure, valuation, income statement,
                        balance sheet, cash flow (annual + quarterly)
    """
    t    = yf.Ticker(ticker)
    info = t.info

    # ── Helper ────────────────────────────────────────────────────────────────
    def df_to_dict(df):
        """Convert a financials DataFrame to {row: {date_str: value}} dict."""
        if df is None or df.empty:
            return {}
        df.columns = [str(c.date()) for c in df.columns]
        return df.to_dict("index")
        #return df.where(df.notna(), other=None).to_dict()

    # ── Technical Data ────────────────────────────────────────────────────────
    history = t.history(period="10d")
    ohlcv = [
        {
            "date":   str(idx.date()),
            "open":   row["Open"],
            "high":   row["High"],
            "low":    row["Low"],
            "close":  row["Close"],
            "volume": int(row["Volume"]),
        }
        for idx, row in history.iterrows()
    ]

    technical = {
        "current_price":       info.get("currentPrice"),
        "open":                info.get("open"),
        "previous_close":      info.get("previousClose"),
        "day_low":             info.get("dayLow"),
        "day_high":            info.get("dayHigh"),
        "fifty_two_week_low":  info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "volume":              info.get("volume"),
        "avg_volume_10d":      info.get("averageVolume10days"),
        "avg_volume_3m":       info.get("averageVolume"),
        "beta":                info.get("beta"),
        "fifty_day_ma":        info.get("fiftyDayAverage"),
        "two_hundred_day_ma":  info.get("twoHundredDayAverage"),
        "ohlcv_history":       ohlcv,           # last 10 trading days
    }

    # ── Fundamental Data ──────────────────────────────────────────────────────
    fundamental = {

        "share_structure": {
            "shares_outstanding":    info.get("sharesOutstanding"),
            "float_shares":          info.get("floatShares"),
            "shares_short":          info.get("sharesShort"),
            "short_ratio":           info.get("shortRatio"),
            "short_pct_of_float":    info.get("shortPercentOfFloat"),
            "held_pct_insiders":     info.get("heldPercentInsiders"),
            "held_pct_institutions": info.get("heldPercentInstitutions"),
        },

        "valuation": {
            "market_cap":            info.get("marketCap"),
            "enterprise_value":      info.get("enterpriseValue"),
            "pe_ratio_ttm":          info.get("trailingPE"),
            "forward_pe":            info.get("forwardPE"),
            "price_to_book":         info.get("priceToBook"),
            "price_to_sales_ttm":    info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda":          info.get("enterpriseToEbitda"),
            "ev_to_revenue":         info.get("enterpriseToRevenue"),
            "eps_ttm":               info.get("trailingEps"),
            "forward_eps":           info.get("forwardEps"),
            "dividend_yield":        info.get("dividendYield"),
            "payout_ratio":          info.get("payoutRatio"),
            "profit_margin":         info.get("profitMargins"),
            "operating_margin":      info.get("operatingMargins"),
            "return_on_equity":      info.get("returnOnEquity"),
            "return_on_assets":      info.get("returnOnAssets"),
            "revenue_growth_yoy":    info.get("revenueGrowth"),
            "earnings_growth_yoy":   info.get("earningsGrowth"),
        },

        # Financial statements — {line_item: {fiscal_year_date: value}}
        "income_statement": {
            "annual":    df_to_dict(t.financials),
            "quarterly": df_to_dict(t.quarterly_financials),
        },

        "balance_sheet": {
            "annual":    df_to_dict(t.balance_sheet),
            "quarterly": df_to_dict(t.quarterly_balance_sheet),
        },

        "cash_flow": {
            "annual":    df_to_dict(t.cashflow),
            "quarterly": df_to_dict(t.quarterly_cashflow),
        },
    }

    return {
        "ticker":      ticker.upper(),
        "technical":   technical,
        "fundamental": fundamental,
    }

def dcf_valuation(
    data: dict,
    discount_rate: float = 0.10,    # WACC assumption, e.g. 0.10 = 10%
    projection_years: int = 5,      # number of years to project FCF
) -> dict:
    """
    Run a DCF valuation from a retrieve_data() output dict.

    Parameters
    ----------
    data            : dict returned by retrieve_data()
    discount_rate   : float, assumed WACC (default 10%)
    projection_years: int, forecast horizon (default 5 years)

    Returns
    -------
    dict with inputs, projections, and valuation output
    """

    # ── 1. Pull raw data ──────────────────────────────────────────────────────
    annual = data["fundamental"]

    def get_sorted(statement: str, line_item: str) -> list:
        """Return values sorted chronologically (oldest → newest)."""
        items = annual[statement]["annual"].get(line_item, {})
        return [v for _, v in sorted(items.items()) if v is not None and not math.isnan(v)]

    revenue_history      = get_sorted("income_statement", "Total Revenue")
    operating_cf_history = get_sorted("cash_flow", "Operating Cash Flow")
    capex_history        = get_sorted("cash_flow", "Capital Expenditure")
    total_debt_history   = get_sorted("balance_sheet", "Total Debt")
    cash_history         = get_sorted("balance_sheet", "Cash And Cash Equivalents")
    shares_outstanding   = data["fundamental"]["share_structure"]["shares_outstanding"]

    # ── 2. Compute historical FCF ─────────────────────────────────────────────
    # CapEx is negative in yfinance, so FCF = OpCF + CapEx
    fcf_history = [
        ocf + capex
        for ocf, capex in zip(operating_cf_history, capex_history)
    ]

    # ── 3. Derive growth rates ────────────────────────────────────────────────
    def cagr(values: list) -> float:
        """Compute CAGR from a list of chronological annual values."""
        if len(values) < 2 or values[0] is None or values[0] == 0:
            return 0.0
        n = len(values) - 1
        return (values[-1] / values[0]) ** (1 / n) - 1

    revenue_cagr = cagr(revenue_history)

    # FCF growth rate: use FCF CAGR if FCFs are consistently positive,
    # otherwise fall back to revenue CAGR as a proxy
    fcf_positive = all(f > 0 for f in fcf_history)
    fcf_growth_rate = cagr(fcf_history) if fcf_positive else revenue_cagr

    # Terminal growth rate = revenue CAGR, capped between 1% and 4%
    terminal_growth_rate = max(0.01, min(0.04, revenue_cagr))

    # ── 4. Project FCFs ───────────────────────────────────────────────────────
    base_fcf = fcf_history[-1]      # most recent FCF as starting point

    projected_fcfs = []
    for year in range(1, projection_years + 1):
        projected_fcfs.append(base_fcf * (1 + fcf_growth_rate) ** year)

    # ── 5. Discount projected FCFs ────────────────────────────────────────────
    pv_fcfs = [
        fcf / (1 + discount_rate) ** year
        for year, fcf in enumerate(projected_fcfs, start=1)
    ]
    total_pv_fcfs = sum(pv_fcfs)

    # ── 6. Terminal value (Gordon Growth Model) ───────────────────────────────
    terminal_fcf      = projected_fcfs[-1] * (1 + terminal_growth_rate)
    terminal_value    = terminal_fcf / (discount_rate - terminal_growth_rate)
    pv_terminal_value = terminal_value / (1 + discount_rate) ** projection_years

    # ── 7. Intrinsic value per share ──────────────────────────────────────────
    # Enterprise Value = PV of FCFs + PV of Terminal Value
    # Equity Value     = Enterprise Value - Net Debt
    # Net Debt         = Total Debt - Cash
    net_debt          = (total_debt_history[-1] or 0) - (cash_history[-1] or 0)
    enterprise_value  = total_pv_fcfs + pv_terminal_value
    equity_value      = enterprise_value - net_debt
    intrinsic_value   = equity_value / shares_outstanding if shares_outstanding else None

    # Current price for margin of safety calc
    current_price     = data["technical"]["current_price"]
    margin_of_safety  = (
        (intrinsic_value - current_price) / intrinsic_value
        if intrinsic_value and current_price
        else None
    )

    # ── 8. Package results ────────────────────────────────────────────────────
    return {
        "ticker": data["ticker"],

        "assumptions": {
            "discount_rate":       discount_rate,
            "projection_years":    projection_years,
            "fcf_growth_rate":     round(fcf_growth_rate, 4),
            "terminal_growth_rate": round(terminal_growth_rate, 4),
            "fcf_growth_source":   "fcf_cagr" if fcf_positive else "revenue_cagr_proxy",
        },

        "historical": {
            "revenue":          dict(zip(sorted(annual["income_statement"]["annual"].get("Total Revenue", {}).keys()), revenue_history)),
            "operating_cf":     dict(zip(sorted(annual["cash_flow"]["annual"].get("Operating Cash Flow", {}).keys()), operating_cf_history)),
            "capex":            dict(zip(sorted(annual["cash_flow"]["annual"].get("Capital Expenditure", {}).keys()), capex_history)),
            "fcf":              dict(zip(sorted(annual["cash_flow"]["annual"].get("Operating Cash Flow", {}).keys()), fcf_history)),
        },

        "projections": {
            f"year_{i}": {"fcf": round(fcf), "pv": round(pv)}
            for i, (fcf, pv) in enumerate(zip(projected_fcfs, pv_fcfs), start=1)
        },

        "valuation": {
            "total_pv_fcfs":       round(total_pv_fcfs),
            "terminal_value":      round(terminal_value),
            "pv_terminal_value":   round(pv_terminal_value),
            "enterprise_value":    round(enterprise_value),
            "net_debt":            round(net_debt),
            "equity_value":        round(equity_value),
            "shares_outstanding":  shares_outstanding,
            "intrinsic_value":     round(intrinsic_value, 2) if intrinsic_value else None,
            "current_price":       current_price,
            "margin_of_safety":    round(margin_of_safety, 4) if margin_of_safety else None,
        },
    }


# ── Quick smoke-test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    import json

    data = retrieve_data("AAPL")
    annual = data["fundamental"]

    """
    for line_item, values in data["fundamental"]["balance_sheet"]["annual"].items():
    	print(line_item)
    	for date, value in values.items():
        	print(f"  {date}: {value}")
    	print()

    for line_item, values in data["fundamental"]["balance_sheet"]["annual"].items():
    	if "cash" in line_item.lower():
        	print(line_item)
    """

    # Helper: extract a line item across the last N years
    def get_item(statement: str, line_item: str, years: int = 5) -> dict:
        items = data["fundamental"][statement]["annual"].get(line_item, {})
        return dict(list(items.items())[:years])

    summary = {
        "ticker":    data["ticker"],
        "technical": {k: v for k, v in data["technical"].items() if k != "ohlcv_history"},
        "ohlcv_history (last 3 days)": data["technical"]["ohlcv_history"][-3:],
        "fundamental": {
            "share_structure": data["fundamental"]["share_structure"],
            "valuation":       data["fundamental"]["valuation"],
            "key_metrics (last 5 years)": {
                "revenue":                  get_item("income_statement", "Total Revenue"),
                "operating_cash_flow":      get_item("cash_flow", "Operating Cash Flow"),
                "capex":                    get_item("cash_flow", "Capital Expenditure"),
                "total_debt":               get_item("balance_sheet", "Total Debt"),
                "cash_and_equivalents":     get_item("balance_sheet", "Cash And Cash Equivalents"),
            },
        },
    }

    result = dcf_valuation(data, discount_rate=0.10)
    print(json.dumps(result, indent=2, default=str))
