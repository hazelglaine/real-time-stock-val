"""
Financial Data Retrieval using yfinance
----------------------------------------
Install dependency:  pip install yfinance pandas
Usage:
    from financial_data import retrieve_data
    data = retrieve_data("AAPL")
"""

import yfinance as yf


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


# ── Quick smoke-test when run directly ────────────────────────────────────────
if __name__ == "__main__":
    import json

    data = retrieve_data("AAPL")

    """
    for line_item, values in data["fundamental"]["balance_sheet"]["annual"].items():
    	print(line_item)
    	for date, value in values.items():
        	print(f"  {date}: {value}")
    	print()
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

    print(json.dumps(summary, indent=2, default=str))
