"""The two lenses, plus the overview, comparison and chart payloads built on them.

Each lens turns raw numbers into labeled metrics with a plain-English reading.
They are built separately on purpose: the investor lens never looks at
short-term signals and the trader lens never looks at valuation, so each one
reaches its own conclusion and the two can disagree.

Readings explain what a number means. They don't recommend buying or selling.
"""

import math
from datetime import date

import numpy as np
import pandas as pd

from . import data, indicators as ind, risk
from .config import BENCHMARK

# ---------------------------------------------------------------- formatting

def pct(x, digits=1, signed=False):
    if x is None:
        return "—"
    return f"{x * 100:+.{digits}f}%" if signed else f"{x * 100:.{digits}f}%"


def pts(x):
    return f"{abs(x) * 100:.0f} pts"


def money(x):
    if x is None:
        return "—"
    sign, a = ("-" if x < 0 else ""), abs(x)
    for div, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            v = a / div
            return f"{sign}${v:.2f}{suffix}" if v < 10 else f"{sign}${v:.1f}{suffix}"
    return f"{sign}${a:,.0f}"


def usd(x):
    return "—" if x is None else f"${x:,.2f}"


def times(x):
    return "—" if x is None else f"{x:.1f}×"


def day(ts) -> str:
    ts = pd.Timestamp(ts)
    return f"{ts:%b} {ts.day}, {ts.year}"


def metric(key, label, value, display, reading, tone="neutral", term=None):
    """tone is for colour only: positive | negative | caution | neutral."""
    if isinstance(value, np.generic):
        value = value.item()  # numpy scalars don't serialize to JSON
    if isinstance(value, float) and not math.isfinite(value):
        value = None
    return {"key": key, "label": label, "value": value, "display": display,
            "reading": reading, "tone": tone, "term": term or key}


def missing(key, label, term=None, why="Not available from the data source for this ticker."):
    return metric(key, label, None, "—", why, "neutral", term)


def section(key, title, metrics):
    return {"key": key, "title": title, "metrics": metrics}


def _f(v):
    """Float or None from a Yahoo field."""
    return None if v is None else float(v)


# ---------------------------------------------------------------- shared context

class Ctx:
    def __init__(self, symbol: str):
        self.symbol = data.normalize(symbol)
        self.df = data.get_prices(self.symbol)
        self.profile = data.get_profile(self.symbol)
        self.info = self.profile.get("info", {})
        self.is_etf = self.info.get("quoteType") == "ETF"
        self.last = float(self.df["close"].iloc[-1])
        self.as_of = self.df.index[-1]
        self._bench = None

    @property
    def bench(self) -> pd.DataFrame:
        if self._bench is None:
            self._bench = self.df if self.symbol == BENCHMARK else data.get_prices(BENCHMARK)
        return self._bench

    def header(self, lens: str, title: str, horizon: str, question: str) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.info.get("longName") or self.info.get("shortName") or self.symbol,
            "kind": "ETF" if self.is_etf else "Stock",
            "lens": lens,
            "title": title,
            "horizon": horizon,
            "question": question,
            "as_of": self.as_of.strftime("%Y-%m-%d"),
            "prices_fetched_at": data.fetched_at(self.symbol, "prices"),
            "profile_fetched_at": data.fetched_at(self.symbol, "profile"),
        }


# ---------------------------------------------------------------- overview

def overview(symbol: str) -> dict:
    c = Ctx(symbol)
    df, info = c.df, c.info
    prev = float(df["close"].iloc[-2]) if len(df) > 1 else c.last
    year = df.tail(252)
    out = {
        "symbol": c.symbol,
        "name": info.get("longName") or info.get("shortName") or c.symbol,
        "kind": "ETF" if c.is_etf else "Stock",
        "price": round(c.last, 2),
        "change_1d": c.last / prev - 1,
        "as_of": c.as_of.strftime("%Y-%m-%d"),
        "high_52w": round(float(year["high"].max()), 2),
        "low_52w": round(float(year["low"].min()), 2),
        "exchange": info.get("exchange"),
        "summary": info.get("longBusinessSummary"),
        "prices_fetched_at": data.fetched_at(c.symbol, "prices"),
        "history_start": df.index[0].strftime("%Y-%m-%d"),
    }
    if c.is_etf:
        out.update(category=info.get("category"), fund_family=info.get("fundFamily"),
                   total_assets=info.get("totalAssets"))
    else:
        out.update(sector=info.get("sector"), industry=info.get("industry"),
                   market_cap=info.get("marketCap"), website=info.get("website"))
    return out


# ---------------------------------------------------------------- investor lens

def _track_record(c: Ctx) -> list[dict]:
    adj, badj = c.df["adj_close"], c.bench["adj_close"]
    rows = []
    for label, days, years in (("1Y", 252, 1), ("3Y", 756, 3), ("5Y", 1260, 5)):
        key = f"return_{label.lower()}"
        title = f"{label} return" + ("" if years == 1 else " (per year)")
        r, b = risk.period_return(adj, days), risk.period_return(badj, days)
        if r is None:
            rows.append(missing(key, title, "total_return",
                                f"Not enough history: prices start {day(c.df.index[0])}."))
            continue
        if years > 1:
            r, b = risk.annualize(r, years), risk.annualize(b, years)
        shown = pct(r, 1, signed=True) + ("" if years == 1 else "/yr")
        if c.symbol == BENCHMARK or b is None:
            rows.append(metric(key, title, r, shown, "This is the benchmark (the S&P 500).",
                               "neutral", "total_return"))
            continue
        diff = r - b
        bench = pct(b, 1, signed=True)
        if diff >= 0.02:
            reading, tone = f"Beat the S&P 500 ({bench}) by {pts(diff)}.", "positive"
        elif diff <= -0.02:
            reading, tone = f"Lagged the S&P 500 ({bench}) by {pts(diff)}.", "negative"
        else:
            reading, tone = f"Roughly matched the S&P 500 ({bench}).", "neutral"
        rows.append(metric(key, title, r, shown, reading, tone, "total_return"))
    return rows


def _risk_metrics(c: Ctx) -> list[dict]:
    adj, badj = c.df["adj_close"], c.bench["adj_close"]
    out = []

    v, bv = risk.volatility(adj), risk.volatility(badj)
    if v is None:
        out.append(missing("volatility", "Volatility (1Y)"))
    else:
        monthly = pct(v / math.sqrt(12), 0)
        if c.symbol == BENCHMARK or not bv:
            reading = f"A typical month moves about ±{monthly}."
            tone = "neutral"
        else:
            ratio = v / bv
            reading = (f"Swings about {ratio:.1f}× as much as the S&P 500 ({pct(bv, 0)}). "
                       f"A typical month moves about ±{monthly}.")
            tone = "caution" if ratio > 1.5 else "neutral"
        out.append(metric("volatility", "Volatility (1Y)", v, pct(v, 0), reading, tone))

    md = risk.max_drawdown(adj, 1260)
    if md is None:
        out.append(missing("max_drawdown", "Worst drop (5Y)"))
    else:
        back = f"recovered by {day(md['recovered'])}" if md["recovered"] else "not yet recovered"
        reading = (f"Fell {pct(-md['drawdown'], 0)} from {day(md['peak'])} to {day(md['trough'])}, "
                   f"{back}. Ask yourself whether you'd have held through that.")
        dd = md["drawdown"]
        tone = "neutral" if dd > -0.25 else ("caution" if dd > -0.5 else "negative")
        out.append(metric("max_drawdown", "Worst drop (5Y)", dd, pct(dd, 0), reading, tone))

    beta, corr = (None, None) if c.symbol == BENCHMARK else risk.beta_and_correlation(adj, badj)
    if c.symbol == BENCHMARK:
        out.append(metric("beta", "Beta (1Y)", 1.0, "1.00", "The benchmark itself: beta is 1 by definition."))
    elif beta is None:
        out.append(missing("beta", "Beta (1Y)"))
    else:
        reading, tone = _beta_reading(beta, corr)
        out.append(metric("beta", "Beta (1Y)", beta, f"{beta:.2f}", reading, tone))

    if c.is_etf and corr is not None:
        if corr >= 0.9:
            reading = ("Moves almost in lockstep with the S&P 500, so it adds little "
                       "diversification next to an S&P 500 fund.")
        elif corr >= 0.6:
            reading = "Partly follows the S&P 500."
        else:
            reading = "Moves fairly independently of the S&P 500: real diversification."
        out.append(metric("correlation", "Correlation to S&P 500", corr, f"{corr:.2f}", reading))
    return out


def _dividend_metric(c: Ctx, label="Dividend yield") -> dict:
    ttm = c.profile.get("dividends_ttm")
    if ttm is None:
        return missing("dividend_yield", label)
    if ttm == 0:
        return metric("dividend_yield", label, 0.0, "0%", "Pays no dividend; all returns come from the price.")
    y = ttm / c.last
    reading = f"{usd(ttm)} per share over the last 12 months: {pct(y, 2)} a year at today's price."
    tone = "neutral"
    if y > 0.06 and not c.is_etf:
        reading += " An unusually high yield can mean the market expects a cut."
        tone = "caution"
    return metric("dividend_yield", label, y, pct(y, 2), reading, tone)


def _beta_reading(beta: float, corr: float) -> tuple[str, str]:
    # Beta = correlation × (its volatility ÷ the market's), so a low beta only means
    # "calm" when the stock actually tracks the market. Check direction and fit first.
    if beta < -0.2:
        return (f"Moved against the market this year: a 1% S&P 500 rise came with about a "
                f"{-beta:.1f}% fall here on average, and the reverse. That usually means a different "
                "driver (oil, interest rates, its own news), not a hedge you can count on."), "neutral"
    if corr < 0.3:
        return ("Mostly independent of the market: its swings this year had little to do with "
                "the S&P 500's, so beta says little about how bumpy it is. Check volatility."), "neutral"
    if beta < 0.8:
        return "Defensive: has tended to move less than the market.", "neutral"
    if beta <= 1.2:
        return "Moves roughly in step with the market.", "neutral"
    return (f"Amplified: a 1% market move has come with about a {beta:.1f}% move here, "
            "in both directions."), "caution"


def _pe_reading(pe: float, market_pe: float | None) -> tuple[str, str]:
    if market_pe:
        rel = pe / market_pe
        mkt = f"{market_pe:.0f}×"
        if pe < 12:
            return (f"Low next to the S&P 500's {mkt}. Cheap stocks are sometimes bargains "
                    "and sometimes cheap for a reason."), "neutral"
        if rel <= 1.2:
            return f"In line with the S&P 500 ({mkt}).", "neutral"
        if rel <= 2:
            return f"Above the S&P 500's {mkt}: investors are paying up for expected growth.", "caution"
        return (f"{rel:.1f}× the S&P 500's multiple ({mkt}). The price assumes strong growth "
                "for years; that growth has to show up."), "caution"
    if pe < 15:
        return "Low by historical standards (the market has usually traded around 15–25×).", "neutral"
    if pe <= 25:
        return "Within the market's usual 15–25× range.", "neutral"
    return "Above the market's usual 15–25× range: priced for growth.", "caution"


def _investor_equity(c: Ctx) -> list[dict]:
    info, fin = c.info, c.profile.get("financials", {})
    sector = info.get("sector") or ""
    market_pe = _f(data.get_profile(BENCHMARK).get("info", {}).get("trailingPE"))

    # Growth
    growth = []
    g = _f(info.get("revenueGrowth"))
    if g is None:
        growth.append(missing("revenue_growth", "Revenue growth (YoY)"))
    else:
        if g >= 0.25:
            r, t = f"Growing fast: sales up {pct(g, 0)} on the same quarter last year.", "positive"
        elif g >= 0.08:
            r, t = "Solid growth, comfortably ahead of inflation.", "positive"
        elif g >= 0:
            r, t = "Slow growth: the business is roughly treading water.", "neutral"
        else:
            r, t = "Sales are shrinking versus a year ago. Worth finding out why.", "negative"
        growth.append(metric("revenue_growth", "Revenue growth (YoY)", g, pct(g, 1, True), r, t))

    rev = fin.get("revenue") or {}
    if len(rev) >= 2:
        (d0, first), (d1, last) = list(rev.items())[0], list(rev.items())[-1]
        years = (pd.Timestamp(d1) - pd.Timestamp(d0)).days / 365.25
        if first > 0 and last > 0 and years >= 1:
            cagr = (last / first) ** (1 / years) - 1
            label = f"Revenue growth ({round(years)}-yr avg)"
            r = f"Sales went from {money(first)} to {money(last)}: about {pct(cagr, 0)} a year."
            t = "positive" if cagr >= 0.1 else ("neutral" if cagr >= 0 else "negative")
            growth.append(metric("revenue_cagr", label, cagr, pct(cagr, 1, True) + "/yr", r, t))

    eg = _f(info.get("earningsGrowth"))
    if eg is not None:
        if eg >= 0.25:
            r, t = f"Profits up {pct(eg, 0)} on the same quarter last year.", "positive"
        elif eg >= 0:
            r, t = "Profits growing modestly.", "neutral"
        else:
            r, t = "Profits are down versus a year ago.", "negative"
        growth.append(metric("earnings_growth", "Earnings growth (YoY)", eg, pct(eg, 1, True), r, t))

    # Profitability
    prof = []
    gm = _f(info.get("grossMargins"))
    if gm is not None:
        if gm >= 0.6:
            r, t = (f"High: keeps {pct(gm, 0)} of each sales dollar after the direct cost of the product. "
                    "Typical of software and strong brands."), "positive"
        elif gm >= 0.35:
            r, t = "Moderate.", "neutral"
        elif gm >= 0:
            r, t = "Low, as is normal for retailers, manufacturers and distributors.", "neutral"
        else:
            r, t = "Selling below cost.", "negative"
        prof.append(metric("gross_margin", "Gross margin", gm, pct(gm), r, t))
    om = _f(info.get("operatingMargins"))
    if om is not None:
        if om >= 0.25:
            r, t = f"Very profitable operations: {pct(om, 0)} of each sales dollar is left after running the business.", "positive"
        elif om >= 0.15:
            r, t = "Healthy operating profit.", "positive"
        elif om >= 0.05:
            r, t = "Modest operating profit.", "neutral"
        elif om >= 0:
            r, t = "Thin: a small rise in costs could erase operating profit.", "caution"
        else:
            r, t = "Losing money on operations.", "negative"
        prof.append(metric("operating_margin", "Operating margin", om, pct(om), r, t))
    nm = _f(info.get("profitMargins"))
    if nm is not None:
        if nm >= 0.2:
            r, t = f"{pct(nm, 0)} of every sales dollar ends up as profit.", "positive"
        elif nm >= 0.08:
            r, t = "Solid bottom-line profit.", "neutral"
        elif nm >= 0:
            r, t = "Thin bottom-line profit.", "caution"
        else:
            r, t = "Net loss over the last year.", "negative"
        prof.append(metric("profit_margin", "Net profit margin", nm, pct(nm), r, t))
    roe = _f(info.get("returnOnEquity"))
    if roe is not None:
        if roe >= 0.4:
            r, t = ("Exceptionally high. Can mean a great business, or a small equity base from "
                    "buybacks or debt; check debt-to-equity."), "neutral"
        elif roe >= 0.15:
            r, t = f"Strong: earns about {pct(roe, 0)} a year on shareholders' money.", "positive"
        elif roe >= 0.08:
            r, t = "Average return on shareholders' money.", "neutral"
        elif roe >= 0:
            r, t = "Low return on shareholders' money.", "caution"
        else:
            r, t = "Negative: the company lost money.", "negative"
        prof.append(metric("roe", "Return on equity", roe, pct(roe, 0), r, t))

    # Cash and balance sheet
    cash = []
    fcf = _f(fin.get("fcf_ttm"))
    if fcf is None:
        fcf = _f(info.get("freeCashflow"))
    revenue = _f(info.get("totalRevenue"))
    if fcf is None:
        cash.append(missing("free_cash_flow", "Free cash flow (TTM)"))
    else:
        if fcf > 0:
            r, t = f"Generates {money(fcf)} a year in cash after paying to run and invest in the business.", "positive"
        else:
            r, t = f"Burning cash: spent {money(-fcf)} more than it brought in.", "negative"
        cash.append(metric("free_cash_flow", "Free cash flow (TTM)", fcf, money(fcf), r, t))
        if revenue:
            fm = fcf / revenue
            if fm >= 0.2:
                r, t = f"Turns {pct(fm, 0)} of sales into free cash. Excellent.", "positive"
            elif fm >= 0.05:
                r, t = "Converts a reasonable share of sales into cash.", "neutral"
            elif fm >= 0:
                r, t = "Little cash left over from each sales dollar.", "caution"
            else:
                r, t = "Spends more cash than its sales bring in.", "negative"
            cash.append(metric("fcf_margin", "Free cash flow margin", fm, pct(fm), r, t))
    de = _f(info.get("debtToEquity"))
    if de is not None:
        de = de / 100  # Yahoo reports this as a percentage
        if de < 0.5:
            r, t = f"Light debt: {usd(de)} of debt per $1 of shareholder equity.", "positive"
        elif de < 1.5:
            r, t = "Moderate debt, normal for many industries.", "neutral"
        else:
            r, t = "Heavy debt. Common for utilities and real estate; riskier for cyclical businesses.", "caution"
        if sector in ("Financial Services", "Real Estate", "Utilities"):
            r += " Debt ratios work differently in this sector, so compare within it."
        cash.append(metric("debt_to_equity", "Debt to equity", de, f"{de:.2f}", r, t))
    tc, td = _f(info.get("totalCash")), _f(info.get("totalDebt"))
    if tc is not None and td is not None:
        net = tc - td
        if net >= 0:
            r, t = f"More cash than debt: {money(net)} net cash.", "positive"
        else:
            r, t = f"More debt than cash: {money(-net)} net debt.", "neutral"
        cash.append(metric("net_cash", "Net cash", net, money(net), r, t))

    # Valuation
    val = []
    pe = _f(info.get("trailingPE"))
    if pe is None or pe <= 0:
        val.append(missing("pe_trailing", "P/E (trailing)", why=(
            "No meaningful P/E: no profit over the last year, or not reported. "
            "Price-to-sales is the usual fallback.")))
    else:
        r, t = _pe_reading(pe, market_pe)
        val.append(metric("pe_trailing", "P/E (trailing)", pe, times(pe), r, t))
    fpe = _f(info.get("forwardPE"))
    if fpe is not None and fpe > 0:
        if pe and pe > 0 and fpe < pe * 0.85:
            r = f"Below the trailing {times(pe)}: analysts expect profits to grow. Estimates can be wrong."
        elif pe and pe > 0 and fpe > pe * 1.15:
            r = f"Above the trailing {times(pe)}: analysts expect profits to fall."
        else:
            r = "Analysts expect roughly flat profits."
        val.append(metric("pe_forward", "P/E (forward)", fpe, times(fpe), r))
    ps = _f(info.get("priceToSalesTrailing12Months"))
    if ps is not None:
        if ps <= 2:
            r, t = "Low: under $2 of market value per $1 of yearly sales.", "neutral"
        elif ps <= 8:
            r, t = "Moderate.", "neutral"
        elif ps <= 20:
            r, t = "High. Usual for fast-growing, high-margin businesses; steep for anything else.", "caution"
        else:
            r, t = "Very high: the price leans heavily on future growth.", "caution"
        val.append(metric("price_to_sales", "Price to sales", ps, times(ps), r, t))
    ev = _f(info.get("enterpriseToEbitda"))
    if ev is not None and ev > 0:
        if ev <= 10:
            r, t = "Below 10×: generally considered inexpensive.", "neutral"
        elif ev <= 20:
            r, t = "Moderate.", "neutral"
        else:
            r, t = "Above 20×: expensive on current operating earnings.", "caution"
        val.append(metric("ev_ebitda", "EV / EBITDA", ev, times(ev), r, t))
    mcap = _f(info.get("marketCap"))
    if fcf is not None and mcap:
        fy = fcf / mcap
        if fy >= 0.05:
            r, t = f"High: free cash equal to {pct(fy, 1)} of the company's value each year.", "positive"
        elif fy >= 0.02:
            r, t = "Moderate cash yield.", "neutral"
        elif fy > 0:
            r, t = "Low: you're paying mostly for future growth.", "caution"
        else:
            r, t = "Negative: the business isn't producing free cash yet.", "negative"
        val.append(metric("fcf_yield", "Free cash flow yield", fy, pct(fy), r, t))
    peg = _f(info.get("trailingPegRatio"))
    if peg is not None and peg > 0:
        if peg < 1:
            r = "Below 1: cheap relative to expected growth, if that growth estimate holds."
        elif peg <= 2:
            r = "Fair relative to expected growth."
        else:
            r = "Pricey relative to expected growth."
        val.append(metric("peg", "PEG ratio", peg, f"{peg:.2f}", r, "caution" if peg > 2 else "neutral"))

    sections = [
        section("growth", "Growth", growth),
        section("profitability", "Profitability", prof),
        section("cash", "Cash and debt", cash),
        section("valuation", "Valuation", val),
        section("record", "Track record vs S&P 500", _track_record(c)),
        section("risk", "Risk", _risk_metrics(c)),
        section("income", "Income", [_dividend_metric(c)]),
    ]
    return [s for s in sections if s["metrics"]]


def _investor_etf(c: Ctx) -> list[dict]:
    info, fund = c.info, c.profile.get("fund", {})
    market_pe = _f(data.get_profile(BENCHMARK).get("info", {}).get("trailingPE"))
    f = []
    cat = info.get("category") or (fund.get("overview") or {}).get("categoryName")
    if cat:
        f.append(metric("category", "Category", cat, cat,
                        f"What the fund holds, in the standard fund-category scheme. Family: {info.get('fundFamily') or '—'}.",
                        term="etf"))
    er = _f(info.get("netExpenseRatio"))
    if er is None:
        f.append(missing("expense_ratio", "Expense ratio"))
    else:
        er = er / 100  # Yahoo reports this as a percentage
        cost = f"Costs about ${er * 10000:,.0f} a year per $10,000 invested."
        if er <= 0.002:
            r, t = cost + " Very cheap.", "positive"
        elif er <= 0.006:
            r, t = cost + " Reasonable.", "neutral"
        else:
            r, t = cost + " Expensive for an ETF; the strategy has to earn that back.", "caution"
        f.append(metric("expense_ratio", "Expense ratio", er, pct(er, 2), r, t))
    aum = _f(info.get("totalAssets"))
    if aum is not None:
        if aum >= 1e10:
            r, t = "Large and heavily traded, so buying and selling costs are minimal.", "positive"
        elif aum >= 1e9:
            r, t = "Established fund.", "neutral"
        elif aum >= 1e8:
            r, t = "Mid-sized fund.", "neutral"
        else:
            r, t = "Small fund: wider trading spreads and a higher chance it closes.", "caution"
        f.append(metric("aum", "Fund size (AUM)", aum, money(aum), r, t))
    holdings = fund.get("top_holdings") or []
    if holdings:
        w = sum(h["weight"] for h in holdings)
        n = len(holdings)
        if w >= 0.5:
            r, t = f"Concentrated: the top {n} holdings are {pct(w, 0)} of the fund, so a few companies drive results.", "caution"
        elif w >= 0.25:
            r, t = f"The top {n} holdings are {pct(w, 0)} of the fund: moderately concentrated.", "neutral"
        else:
            r, t = f"The top {n} holdings are only {pct(w, 0)} of the fund: well diversified.", "positive"
        f.append(metric("concentration", f"Top {n} weight", w, pct(w, 0), r, t))
        top = " · ".join(f"{h['symbol']} {pct(h['weight'], 1)}" for h in holdings[:5])
        f.append(metric("top_holdings", "Largest holdings", [h["symbol"] for h in holdings], top,
                        "The biggest positions. Each can be analyzed on its own."))

    val = []
    pe = _f(info.get("trailingPE"))
    if pe and pe > 0 and c.symbol != BENCHMARK:
        r, t = _pe_reading(pe, market_pe)
        val.append(metric("pe_trailing", "P/E of holdings", pe, times(pe), r, t))
    elif pe and pe > 0:
        val.append(metric("pe_trailing", "P/E of holdings", pe, times(pe),
                          "The S&P 500's own multiple: the yardstick other P/Es are compared with."))

    sections = [
        section("fund", "The fund", f),
        section("valuation", "Valuation", val),
        section("record", "Track record vs S&P 500", _track_record(c)),
        section("risk", "Risk", _risk_metrics(c)),
        section("income", "Income", [_dividend_metric(c, "Distribution yield")]),
    ]
    return [s for s in sections if s["metrics"]]


def investor_view(symbol: str) -> dict:
    """Long-term lens: is this a good business (or fund) at a sensible price,
    and could you live with how bumpy it has been?"""
    c = Ctx(symbol)
    out = c.header("investor", "Investor view", "Months to years",
                   "Is this a good business at a sensible price, and could I live with the ride?"
                   if not c.is_etf else
                   "What does this fund own, what does it cost, and how has it held up?")
    out["sections"] = _investor_etf(c) if c.is_etf else _investor_equity(c)
    out["notes"] = [
        "Fundamentals come from Yahoo Finance (via yfinance): unofficial, and can lag company filings.",
        "Returns include dividends. Comparisons use SPY as the S&P 500.",
    ]
    return out


# ---------------------------------------------------------------- trader lens

def _vs_average(key, label, last, avg, horizon, term):
    if avg is None or pd.isna(avg):
        return missing(key, label, term, "Not enough history yet.")
    d = last / avg - 1
    side = "above" if d >= 0 else "below"
    r = f"{pct(abs(d))} {side} it: the {horizon} trend is {'up' if d >= 0 else 'down'}."
    t = "positive" if d >= 0 else "negative"
    if abs(d) > 0.1 and horizon != "long-term":
        r += " Stretched this far, pullbacks toward the average are common."
        t = "caution"
    return metric(key, label, d, pct(d, 1, True), r, t, term)


def trader_view(symbol: str) -> dict:
    """Short-term lens (days to weeks): trend, momentum, volatility, volume,
    key price levels and upcoming event risk."""
    c = Ctx(symbol)
    df = c.df
    close, last = df["close"], c.last
    e20, s50, s200 = ind.ema(close, 20), ind.sma(close, 50), ind.sma(close, 200)
    v20, v50, v200 = e20.iloc[-1], s50.iloc[-1], s200.iloc[-1]

    # Trend
    trend = []
    checks = [(n, last > v) for n, v in (("20-day", v20), ("50-day", v50), ("200-day", v200)) if pd.notna(v)]
    above = [n for n, ok in checks if ok]
    below = [n for n, ok in checks if not ok]
    if checks:
        if not below:
            r, t, shown = "Uptrend: price is above its 20-, 50- and 200-day averages.", "positive", "Uptrend"
        elif not above:
            r, t, shown = "Downtrend: price is below its 20-, 50- and 200-day averages.", "negative", "Downtrend"
        else:
            r, t, shown = (f"Mixed: above the {', '.join(above)} and below the {', '.join(below)} average. "
                           "Often a pause or a turning point."), "neutral", "Mixed"
        trend.append(metric("trend_state", "Trend", shown, shown, r, t))
    trend.append(_vs_average("vs_ema20", "vs 20-day EMA", last, v20, "short-term", "ema"))
    trend.append(_vs_average("vs_sma50", "vs 50-day SMA", last, v50, "medium-term", "sma"))
    trend.append(_vs_average("vs_sma200", "vs 200-day SMA", last, v200, "long-term", "sma"))
    if pd.notna(v50) and pd.notna(v200):
        cross = ind.last_cross(s50, s200)
        golden = v50 > v200
        since = f" since {day(cross['date'])}" if cross else " for all the history loaded"
        if golden:
            r, t, shown = f"Golden cross: the 50-day average has been above the 200-day{since}.", "positive", "50 > 200"
        else:
            r, t, shown = f"Death cross: the 50-day average has been below the 200-day{since}.", "negative", "50 < 200"
        trend.append(metric("ma_cross", "50 / 200-day", golden, shown, r, t, "golden_cross"))

    # Momentum
    mom = []
    rv = ind.rsi(close).iloc[-1]
    if pd.notna(rv):
        if rv >= 70:
            r, t = ("Overbought zone: price has risen fast. In strong uptrends RSI can stay above 70 "
                    "for weeks, so this means 'strong' as often as 'due to drop'."), "caution"
        elif rv >= 50:
            r, t = "Bullish range: buyers have had the upper hand recently.", "positive"
        elif rv > 30:
            r, t = "Bearish range: sellers have had the upper hand recently.", "negative"
        else:
            r, t = ("Oversold zone: price has fallen fast. Bounces are common, but falling stocks "
                    "can stay oversold."), "caution"
        mom.append(metric("rsi", "RSI (14)", float(rv), f"{rv:.0f}", r, t))
    m = ind.macd(close)
    if pd.notna(m["signal"].iloc[-1]):
        line, sig = m["macd"].iloc[-1], m["signal"].iloc[-1]
        h = m["hist"].dropna().tail(5)
        rising = h.iloc[-1] > h.iloc[0]
        cross = ind.last_cross(m["macd"], m["signal"])
        since = f" since {day(cross['date'])}" if cross else ""
        if line > sig:
            r = f"MACD above its signal line{since}: upward momentum, " + ("building." if rising else "but fading.")
            t, shown = ("positive" if rising else "neutral"), "Above signal"
        else:
            r = f"MACD below its signal line{since}: downward momentum, " + ("easing." if rising else "building.")
            t, shown = ("neutral" if rising else "negative"), "Below signal"
        mom.append(metric("macd", "MACD (12, 26, 9)", float(line - sig), shown, r, t))
    badj = c.bench["adj_close"]
    for label, days in (("1M", 21), ("3M", 63)):
        r1 = risk.period_return(df["adj_close"], days)
        if r1 is None:
            continue
        b1 = risk.period_return(badj, days)
        if c.symbol == BENCHMARK or b1 is None:
            reading = "The benchmark's own move."
        elif abs(r1 - b1) < 0.005:
            reading = f"In line with the S&P 500 ({pct(b1, 1, True)}) over the period."
        else:
            reading = (f"{'Outperforming' if r1 > b1 else 'Underperforming'} the S&P 500 "
                       f"({pct(b1, 1, True)}) over the period.")
        mom.append(metric(f"return_{label.lower()}", f"{label} return", r1, pct(r1, 1, True), reading,
                          "neutral" if abs(r1) < 0.005 else ("positive" if r1 > 0 else "negative"),
                          "relative_strength"))

    # Volatility
    vol = []
    a = ind.atr(df["high"], df["low"], close).iloc[-1]
    if pd.notna(a):
        ap = a / last
        r = (f"A typical day moves about {usd(a)} ({pct(ap)}). Stops placed closer than about "
             "one ATR tend to get hit by normal noise.")
        vol.append(metric("atr", "ATR (14)", float(a), f"{usd(a)} · {pct(ap)}", r,
                          "caution" if ap > 0.04 else "neutral"))
    bb = ind.bollinger(close)
    up, lo, mid = bb["upper"].iloc[-1], bb["lower"].iloc[-1], bb["mid"].iloc[-1]
    if pd.notna(up) and up > lo:
        pb = (last - lo) / (up - lo)
        if pb > 1:
            r, t, shown = ("Closed above the upper band: an unusually strong move. Can mark breakout "
                           "strength or a stretched short-term top."), "caution", "Above upper"
        elif pb >= 0.8:
            r, t, shown = "Near the upper band: recent closes have been strong.", "neutral", "Upper zone"
        elif pb < 0:
            r, t, shown = "Closed below the lower band: an unusually weak move.", "caution", "Below lower"
        elif pb <= 0.2:
            r, t, shown = "Near the lower band: recent closes have been weak.", "neutral", "Lower zone"
        else:
            r, t, shown = "Inside the bands, mid-range.", "neutral", "Mid-range"
        vol.append(metric("bollinger", "Bollinger position", float(pb), shown, r, t))
        width = (bb["upper"] - bb["lower"]) / bb["mid"]
        med = width.tail(126).median()
        ratio = width.iloc[-1] / med if med else None
        if ratio is not None:
            if ratio < 0.75:
                r, t, shown = (f"Squeeze: the bands are {pct(1 - ratio, 0)} tighter than their 6-month norm. "
                               "Quiet stretches often come before a bigger move; the squeeze doesn't "
                               "say which direction."), "caution", "Squeeze"
            elif ratio > 1.5:
                r, t, shown = "Wide: volatility is running well above its 6-month norm.", "caution", "Wide"
            else:
                r, t, shown = "Normal width for the last 6 months.", "neutral", "Normal"
            vol.append(metric("band_width", "Band width", float(ratio), shown, r, t, "bollinger"))

    # Volume
    volm = []
    v = df["volume"].astype(float)
    if len(v) > 21 and v.tail(21).sum() > 0:
        avg_prev = v.iloc[-21:-1].mean()
        if avg_prev:
            rel = v.iloc[-1] / avg_prev
            if rel >= 2:
                r, t = f"Very heavy: {rel:.1f}× the 20-day average. Something happened; check the news.", "caution"
            elif rel >= 1.3:
                r, t = "Above-average volume.", "neutral"
            elif rel <= 0.6:
                r, t = ("Light volume. Moves on light volume are less convincing. "
                        "(If today's session is still open, the bar is incomplete.)"), "neutral"
            else:
                r, t = "Normal volume.", "neutral"
            volm.append(metric("relative_volume", "Relative volume", float(rel), f"{rel:.2f}×", r, t))
        chg = close.diff().tail(20)
        vv = v.tail(20)
        up_v, down_v = vv[chg > 0].sum(), vv[chg < 0].sum()
        if down_v > 0:
            ud = up_v / down_v
            if ud >= 1.3:
                r, t = "More volume on up days than down days over 20 sessions: buyers more active (accumulation).", "positive"
            elif ud <= 0.77:
                r, t = "More volume on down days than up days over 20 sessions: sellers more active (distribution).", "negative"
            else:
                r, t = "Up-day and down-day volume roughly balanced.", "neutral"
            volm.append(metric("up_down_volume", "Up/down volume (20d)", float(ud), f"{ud:.2f}", r, t))

    # Levels
    lv = []
    year = df.tail(252)
    hi, low = float(year["high"].max()), float(year["low"].min())
    from_hi, from_low = last / hi - 1, last / low - 1
    if from_hi >= -0.03:
        r = "At or near the 52-week high, a level breakout traders watch closely."
    elif (last - low) / (hi - low) <= 0.1:
        r = f"Near the 52-week low ({pct(from_low)} above it)."
    else:
        r = f"{pct(-from_hi)} below the high and {pct(from_low)} above the low."
    lv.append(metric("range_52w", "52-week range", [low, hi], f"{usd(low)} – {usd(hi)}", r, term="week52"))
    levels = ind.key_levels(df)
    sup = next((x for x in levels if x["side"] == "support"), None)
    res = next((x for x in levels if x["side"] == "resistance"), None)
    if sup and 1 - sup["price"] / last < 0.005:
        r = (f"Right at the current price: price is testing it now. It turned here {sup['touches']}× "
             f"in the last 6 months, most recently {day(sup['last_touch'])}.")
        lv.append(metric("support", "Nearest support", sup["price"], usd(sup["price"]), r, term="support_resistance"))
    elif sup:
        r = (f"{pct(1 - sup['price'] / last)} below. Price turned here {sup['touches']}× in the last "
             f"6 months, most recently {day(sup['last_touch'])}.")
        lv.append(metric("support", "Nearest support", sup["price"], usd(sup["price"]), r, term="support_resistance"))
    else:
        lv.append(missing("support", "Nearest support", "support_resistance",
                          "No swing low below the current price in the last 6 months."))
    if res and res["price"] / last - 1 < 0.005:
        r = (f"Right at the current price: price is testing it now. It turned here {res['touches']}× "
             f"in the last 6 months, most recently {day(res['last_touch'])}.")
        lv.append(metric("resistance", "Nearest resistance", res["price"], usd(res["price"]), r, term="support_resistance"))
    elif res:
        r = (f"{pct(res['price'] / last - 1)} above. Price turned here {res['touches']}× in the last "
             f"6 months, most recently {day(res['last_touch'])}.")
        lv.append(metric("resistance", "Nearest resistance", res["price"], usd(res["price"]), r, term="support_resistance"))
    else:
        lv.append(metric("resistance", "Nearest resistance", None, "None nearby",
                         "No swing high above the current price in 6 months: price is above its recent highs.",
                         "positive", "support_resistance"))

    sections = [
        section("trend", "Trend", trend),
        section("momentum", "Momentum", mom),
        section("volatility", "Volatility", vol),
        section("volume", "Volume", volm),
        section("levels", "Key levels", lv),
    ]

    # Event risk
    if not c.is_etf:
        today = date.today()
        upcoming = sorted(d for d in c.profile.get("earnings_dates", []) if d >= today.isoformat())
        if upcoming:
            nxt = upcoming[0]
            days_out = (date.fromisoformat(nxt) - today).days
            if days_out <= 14:
                r, t = (f"In {days_out} days. Stocks often gap several percent on earnings, so short-term "
                        "positions carry extra risk across that date."), "caution"
            else:
                r, t = f"In {days_out} days.", "neutral"
            ev = metric("earnings_date", "Next earnings", nxt, day(nxt), r, t)
        else:
            ev = missing("earnings_date", "Next earnings", why="No upcoming date published yet.")
        sections.append(section("events", "Event risk", [ev]))

    out = c.header("trader", "Trader view", "Days to weeks",
                   "What is the price doing right now, and where is the risk?")
    out["sections"] = [s for s in sections if s["metrics"]]
    out["levels"] = levels
    out["notes"] = [
        "Indicators use daily bars; the latest bar may be intraday and incomplete.",
        "Technical signals describe price behaviour. Their power to predict is mixed and none is reliable alone.",
    ]
    return out


# ---------------------------------------------------------------- compare

COMPARE_KEYS = [
    "return_1y", "return_3y", "volatility", "max_drawdown", "beta",
    "revenue_growth", "operating_margin", "pe_trailing", "price_to_sales", "fcf_yield",
    "expense_ratio", "dividend_yield", "trend_state", "rsi", "vs_sma200",
]


def compare(symbols: list[str]) -> dict:
    rows, errors = [], {}
    for s in symbols[:6]:
        try:
            views = (investor_view(s), trader_view(s))
        except data.DataError as e:
            errors[s] = str(e)
            continue
        flat = {m["key"]: m for v in views for sec in v["sections"] for m in sec["metrics"]}
        rows.append({
            "symbol": views[0]["symbol"], "name": views[0]["name"], "kind": views[0]["kind"],
            "metrics": {k: {"label": flat[k]["label"], "display": flat[k]["display"], "value": flat[k]["value"]}
                        for k in COMPARE_KEYS if k in flat},
        })
    return {"rows": rows, "errors": errors}


# ---------------------------------------------------------------- chart and history payloads

RANGES = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260, "10Y": 2520}


def _series(s: pd.Series, index) -> list[dict]:
    s = s.reindex(index)
    return [{"time": t.strftime("%Y-%m-%d"), "value": round(float(v), 4)} for t, v in s.items() if pd.notna(v)]


def chart_payload(symbol: str, rng: str = "1Y") -> dict:
    """Candles plus every indicator series, computed on full history then cut
    to the range so long averages exist from the first visible bar."""
    symbol = data.normalize(symbol)
    if rng not in RANGES:
        raise ValueError(f"range must be one of {', '.join(RANGES)}")
    df = data.get_prices(symbol)
    close = df["close"]
    idx = df.index[-RANGES[rng]:]
    view = df.loc[idx]
    bb, m = ind.bollinger(close), ind.macd(close)
    return {
        "symbol": symbol,
        "range": rng,
        "candles": [
            {"time": t.strftime("%Y-%m-%d"), "open": round(r.open, 4), "high": round(r.high, 4),
             "low": round(r.low, 4), "close": round(r.close, 4)}
            for t, r in zip(view.index, view.itertuples())
        ],
        "volume": [
            {"time": t.strftime("%Y-%m-%d"), "value": float(r.volume or 0), "up": bool(r.close >= r.open)}
            for t, r in zip(view.index, view.itertuples())
        ],
        "series": {
            "sma20": _series(ind.sma(close, 20), idx),
            "sma50": _series(ind.sma(close, 50), idx),
            "sma200": _series(ind.sma(close, 200), idx),
            "ema20": _series(ind.ema(close, 20), idx),
            "bb_upper": _series(bb["upper"], idx),
            "bb_mid": _series(bb["mid"], idx),
            "bb_lower": _series(bb["lower"], idx),
            "rsi": _series(ind.rsi(close), idx),
            "macd": _series(m["macd"], idx),
            "macd_signal": _series(m["signal"], idx),
            "macd_hist": _series(m["hist"], idx),
        },
        "levels": ind.key_levels(df),
        "prices_fetched_at": data.fetched_at(symbol, "prices"),
    }


def price_history(symbol: str, rng: str = "1Y") -> dict:
    """Compact price history for reasoning about: weekly (or monthly, past 2Y)
    bars, plus the notable days worth annotating."""
    symbol = data.normalize(symbol)
    if rng not in RANGES:
        raise ValueError(f"timeframe must be one of {', '.join(RANGES)}")
    full = data.get_prices(symbol)
    rel_vol = full["volume"] / full["volume"].rolling(20).mean().shift(1)
    df = full.tail(RANGES[rng])
    rule, label = ("W-FRI", "weekly") if RANGES[rng] <= 504 else ("ME", "monthly")
    bars = df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last",
                                  "volume": "sum"}).dropna()
    ret = df["close"].pct_change()
    gap = df["open"] / df["close"].shift(1) - 1

    def days(values, rank):
        """Top 5 days by `rank`, reporting the signed `values` on those days."""
        picks = rank.dropna().sort_values(ascending=False).head(5).index
        return [{"date": t.strftime("%Y-%m-%d"), "change": round(float(values[t]), 4),
                 "close": round(float(df.at[t, "close"]), 2),
                 "volume_vs_avg": None if pd.isna(rel_vol.get(t)) else round(float(rel_vol[t]), 2)}
                for t in picks]

    return {
        "symbol": symbol,
        "timeframe": rng,
        "start": df.index[0].strftime("%Y-%m-%d"),
        "end": df.index[-1].strftime("%Y-%m-%d"),
        "change": round(float(df["close"].iloc[-1] / df["close"].iloc[0] - 1), 4),
        "high": {"price": round(float(df["high"].max()), 2), "date": df["high"].idxmax().strftime("%Y-%m-%d")},
        "low": {"price": round(float(df["low"].min()), 2), "date": df["low"].idxmin().strftime("%Y-%m-%d")},
        "bars_" + label: [
            {"end": t.strftime("%Y-%m-%d"), "open": round(r.open, 2), "high": round(r.high, 2),
             "low": round(r.low, 2), "close": round(r.close, 2)}
            for t, r in zip(bars.index, bars.itertuples())
        ],
        "biggest_up_days": days(ret, ret),
        "biggest_down_days": days(ret, -ret),
        "largest_gaps": days(gap, gap.abs()),
    }
