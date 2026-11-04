"""Plain-English explanations for every metric the lenses show.

Each entry answers four questions: what is it, how is it calculated, how do I
read it, and what's the trap. Keys match the `term` field on lens metrics.
"""

GLOSSARY: dict[str, dict] = {
    # ------------------------------------------------------------ basics
    "candlestick": {
        "title": "Candlestick",
        "lens": "both",
        "what": "One bar per day showing where the price opened, closed, and the high and low in between.",
        "how": "The thick body spans open to close; thin wicks reach the high and low. Green (or hollow) means it closed above the open, red means below.",
        "read": "Long bodies mean one side was in control all day. Long wicks mean price went somewhere and got pushed back.",
        "trap": "A single candle says little. Patterns matter more when they show up at a key level on heavy volume.",
    },
    "volume": {
        "title": "Volume",
        "lens": "trader",
        "what": "How many shares changed hands in a day.",
        "how": "Counted by the exchanges and shown as bars under the price.",
        "read": "Volume is conviction. A breakout on heavy volume is more believable than one on light volume.",
        "trap": "Volume spikes around index rebalancing, options expiry and holidays without meaning much.",
    },
    "market_cap": {
        "title": "Market capitalization",
        "lens": "investor",
        "what": "What the market says the whole company is worth.",
        "how": "Share price × number of shares outstanding.",
        "read": "Mega-cap (over $200B) companies tend to be steadier; small-caps (under $2B) swing harder and can grow faster.",
        "trap": "A low share price doesn't mean a stock is cheap. A $5 stock can be more expensive than a $500 one; compare valuation ratios instead.",
    },
    "adjusted_close": {
        "title": "Adjusted close",
        "lens": "both",
        "what": "Closing prices rewritten as if every dividend had been reinvested.",
        "how": "Past prices are scaled down by each dividend paid, so returns include income.",
        "read": "Tape measures every return and risk number on adjusted prices; charts show the actual traded prices.",
        "trap": "Mixing adjusted and unadjusted prices makes dividend payers look worse than they were.",
    },
    "benchmark": {
        "title": "Benchmark (S&P 500)",
        "lens": "both",
        "what": "The yardstick: 500 large US companies, tracked here by the SPY ETF.",
        "how": "Every return and risk figure is shown next to SPY's over the same period.",
        "read": "If a stock didn't beat a cheap index fund over years, owning it added risk without reward.",
        "trap": "Beating the market in one period proves little; check several periods and how much risk it took.",
    },
    "etf": {
        "title": "ETF (exchange-traded fund)",
        "lens": "investor",
        "what": "A basket of stocks (or bonds) that trades like a single stock.",
        "how": "The fund owns the holdings; each share is a slice of the whole basket. The category says what kind of basket it is.",
        "read": "Analyze an ETF by what it owns, what it costs, and how it has behaved, not by company profits.",
        "trap": "Two ETFs with different names can own nearly the same stocks. Check the top holdings before 'diversifying'.",
    },

    # ------------------------------------------------------------ growth
    "revenue_growth": {
        "title": "Revenue growth (year over year)",
        "lens": "investor",
        "what": "How much sales grew compared with the same quarter a year earlier.",
        "how": "(This quarter's revenue ÷ same quarter last year) − 1. Comparing like quarters removes seasonality.",
        "read": "Above ~8% beats inflation comfortably; above 25% is fast. Shrinking revenue needs an explanation.",
        "trap": "One quarter can be lumpy. Check the multi-year average too, and whether growth is speeding up or slowing down.",
    },
    "revenue_cagr": {
        "title": "Revenue growth, multi-year average (CAGR)",
        "lens": "investor",
        "what": "The steady yearly growth rate that would take sales from where they were to where they are.",
        "how": "(Latest annual revenue ÷ earliest) ^ (1 ÷ years) − 1, from the annual reports.",
        "read": "Smooths out lumpy quarters. 10%+ a year sustained is strong for an established company.",
        "trap": "The start year matters: measuring from a bad year flatters the result.",
    },
    "earnings_growth": {
        "title": "Earnings growth (year over year)",
        "lens": "investor",
        "what": "How much profit grew versus the same quarter last year.",
        "how": "(This quarter's earnings ÷ same quarter last year) − 1.",
        "read": "Profits growing faster than sales means margins are widening, which markets reward.",
        "trap": "Earnings swing with one-off charges and tax items, so a single quarter can mislead. Coming off a weak quarter, growth looks huge.",
    },

    # ------------------------------------------------------------ profitability
    "gross_margin": {
        "title": "Gross margin",
        "lens": "investor",
        "what": "The share of each sales dollar left after the direct cost of making the product.",
        "how": "(Revenue − cost of goods sold) ÷ revenue.",
        "read": "High (60%+) suggests pricing power, as with software or strong brands. Low is normal for retail and manufacturing.",
        "trap": "Compare within an industry. A 25% gross margin is great for a grocer and poor for a software firm.",
    },
    "operating_margin": {
        "title": "Operating margin",
        "lens": "investor",
        "what": "The share of each sales dollar left after all the costs of running the business.",
        "how": "Operating income ÷ revenue. It counts salaries, R&D and marketing, but not interest or taxes.",
        "read": "Shows how efficient the core business is. 15%+ is healthy for most industries.",
        "trap": "Fast-growing companies often run thin margins on purpose to reinvest. Check whether the margin is trending up.",
    },
    "profit_margin": {
        "title": "Net profit margin",
        "lens": "investor",
        "what": "The share of each sales dollar that ends up as profit after everything: interest, taxes, one-offs.",
        "how": "Net income ÷ revenue.",
        "read": "The bottom line. Compare it with operating margin: a big gap means debt or taxes are eating profits.",
        "trap": "One-time gains (selling a division, tax credits) can inflate it for a year.",
    },
    "roe": {
        "title": "Return on equity (ROE)",
        "lens": "investor",
        "what": "How much profit the company earns on the money shareholders have in it.",
        "how": "Net income ÷ shareholders' equity (assets minus debts).",
        "read": "15%+ sustained is strong. It's one of the better single measures of a quality business.",
        "trap": "Debt and share buybacks shrink equity, which inflates ROE. Very high ROE needs a debt check.",
    },

    # ------------------------------------------------------------ cash and debt
    "free_cash_flow": {
        "title": "Free cash flow (FCF)",
        "lens": "investor",
        "what": "Cash the business generates after paying its bills and investing in equipment and buildings.",
        "how": "Operating cash flow − capital expenditures, summed over the last four quarters.",
        "read": "This is the money that can pay dividends, buy back stock, pay down debt or fund growth. Positive and growing is the goal.",
        "trap": "Profits can be shaped by accounting choices, but cash is harder to fake. Watch for profits rising while cash flow falls.",
    },
    "fcf_margin": {
        "title": "Free cash flow margin",
        "lens": "investor",
        "what": "The share of each sales dollar that turns into free cash.",
        "how": "Free cash flow ÷ revenue.",
        "read": "20%+ is excellent. Comparing it with net margin shows how much of the reported profit is real cash.",
        "trap": "Heavy investment years (new factories, data centers) depress it temporarily.",
    },
    "debt_to_equity": {
        "title": "Debt to equity",
        "lens": "investor",
        "what": "How much the company has borrowed relative to what shareholders own.",
        "how": "Total debt ÷ shareholders' equity.",
        "read": "Under 0.5 is light; over 1.5 is heavy. Debt magnifies both good years and bad.",
        "trap": "Banks, insurers, utilities and real estate run high debt by design, so compare within the sector. Negative equity makes the ratio meaningless.",
    },
    "net_cash": {
        "title": "Net cash (or net debt)",
        "lens": "investor",
        "what": "Cash on hand minus total debt.",
        "how": "Cash and short-term investments − total debt.",
        "read": "Net cash means the company could pay off every loan today: a cushion in a downturn.",
        "trap": "Some businesses (utilities, telecoms) carry net debt comfortably because their income is steady.",
    },

    # ------------------------------------------------------------ valuation
    "pe_trailing": {
        "title": "P/E ratio (trailing)",
        "lens": "investor",
        "what": "How many dollars you pay for each $1 of the company's yearly profit.",
        "how": "Share price ÷ earnings per share over the last 12 months.",
        "read": "Compare with the S&P 500's P/E and with peers. Higher means the market expects more growth.",
        "trap": "A low P/E can mean a bargain or a business in decline (a 'value trap'). It's undefined when the company lost money.",
    },
    "pe_forward": {
        "title": "P/E ratio (forward)",
        "lens": "investor",
        "what": "P/E using analysts' estimate of next year's earnings instead of last year's.",
        "how": "Share price ÷ expected earnings per share for the next 12 months.",
        "read": "Forward lower than trailing means profits are expected to grow; higher means they're expected to fall.",
        "trap": "It's built on forecasts, which are often wrong, especially at turning points.",
    },
    "price_to_sales": {
        "title": "Price to sales (P/S)",
        "lens": "investor",
        "what": "How many dollars of market value per $1 of yearly sales.",
        "how": "Market cap ÷ last 12 months' revenue.",
        "read": "Useful for unprofitable or fast-growing companies where P/E doesn't work. Under 2 is low; over 10 assumes high margins later.",
        "trap": "Sales aren't profit. A low P/S on a thin-margin business can still be expensive.",
    },
    "ev_ebitda": {
        "title": "EV / EBITDA",
        "lens": "investor",
        "what": "Price of the whole business, debt included, relative to its operating earnings.",
        "how": "Enterprise value (market cap + debt − cash) ÷ earnings before interest, taxes, depreciation and amortization.",
        "read": "Lets you compare companies with different amounts of debt. Under 10 is generally inexpensive.",
        "trap": "EBITDA ignores the cost of replacing equipment, which flatters capital-heavy businesses.",
    },
    "fcf_yield": {
        "title": "Free cash flow yield",
        "lens": "investor",
        "what": "Free cash generated per year as a percentage of what the company costs to buy.",
        "how": "Free cash flow ÷ market cap.",
        "read": "Think of it like an interest rate the business pays its owners. Compare it with what bonds pay.",
        "trap": "A high yield on shrinking cash flow is a warning sign, not a bargain.",
    },
    "peg": {
        "title": "PEG ratio",
        "lens": "investor",
        "what": "P/E adjusted for how fast earnings are expected to grow.",
        "how": "P/E ÷ expected annual earnings growth rate (in %).",
        "read": "Around 1 means the price is in line with growth; below 1 looks cheap for the growth on offer.",
        "trap": "It depends on a multi-year growth forecast, which is the least reliable number in finance.",
    },

    # ------------------------------------------------------------ returns and risk
    "total_return": {
        "title": "Total return",
        "lens": "investor",
        "what": "How much an investment gained or lost including dividends.",
        "how": "Change in adjusted close over the period. Multi-year returns are shown per year (annualized).",
        "read": "Always compare with the S&P 500 over the same window: that's what you'd have got doing nothing clever.",
        "trap": "Past returns depend heavily on the start date and don't predict future ones.",
    },
    "volatility": {
        "title": "Volatility",
        "lens": "investor",
        "what": "How much the price typically swings.",
        "how": "Standard deviation of daily returns over the last year, scaled to a yearly figure.",
        "read": "The S&P 500 usually runs 12–20%. Divide by 3.5 for a rough 'typical month' move.",
        "trap": "Low volatility in the past doesn't rule out a sudden crash.",
    },
    "max_drawdown": {
        "title": "Maximum drawdown",
        "lens": "investor",
        "what": "The worst peak-to-bottom fall over the period.",
        "how": "The biggest percentage drop from any high to the lowest point that followed.",
        "read": "This is the gut check: would you have held, or sold at the bottom? A 50% drop needs a 100% gain to recover.",
        "trap": "The worst drawdown so far is not the worst possible.",
    },
    "beta": {
        "title": "Beta",
        "lens": "investor",
        "what": "How much a stock tends to move when the market moves.",
        "how": "Covariance of daily returns with the S&P 500 ÷ the S&P 500's variance, over the last year.",
        "read": ("1 means it moves with the market; 2 means roughly twice as much, both up and down; "
                 "between 0 and 1 is calmer than the market. Below 0 means it has tended to move "
                 "against the market."),
        "trap": ("Beta only describes a stock that actually follows the market. One driven by oil prices "
                 "or its own news can show a low or negative beta and still swing hard, so read it next "
                 "to volatility. It also measures typical days, not crashes, and changes over time."),
    },
    "correlation": {
        "title": "Correlation",
        "lens": "investor",
        "what": "How closely two investments move together, from −1 to +1.",
        "how": "Correlation of daily returns with the S&P 500 over the last year.",
        "read": "Near 1 means they move as one, so holding both adds little diversification. Near 0 means independent.",
        "trap": "In market panics correlations jump toward 1; diversification helps least when you need it most.",
    },
    "dividend_yield": {
        "title": "Dividend yield",
        "lens": "investor",
        "what": "The cash a company (or fund) paid out over the past year, as a percentage of today's price.",
        "how": "Dividends per share over the last 12 months ÷ current price.",
        "read": "Income on top of price changes. 1–4% is typical for dividend payers.",
        "trap": "An unusually high yield often means the price fell because the market expects the dividend to be cut.",
    },

    # ------------------------------------------------------------ funds
    "expense_ratio": {
        "title": "Expense ratio",
        "lens": "investor",
        "what": "The yearly fee a fund takes, as a percentage of what you have invested.",
        "how": "Taken out of the fund's assets automatically; you never see a bill.",
        "read": "Broad index ETFs cost 0.03–0.20%. Over 0.5% needs a good reason. Fees compound against you every year.",
        "trap": "A cheap fee doesn't make a fund good, but a high fee is a guaranteed drag.",
    },
    "aum": {
        "title": "Assets under management (fund size)",
        "lens": "investor",
        "what": "How much money is invested in the fund.",
        "how": "Total market value of everything the fund holds.",
        "read": "Bigger funds trade more, so the gap between buy and sell prices is tighter. Under $100M carries closure risk.",
        "trap": "Size is popularity, not quality.",
    },
    "concentration": {
        "title": "Top-holdings concentration",
        "lens": "investor",
        "what": "How much of the fund sits in its largest positions.",
        "how": "Sum of the weights of the top 10 holdings.",
        "read": "Over 50% means a handful of companies drive results; under 25% is broadly spread.",
        "trap": "Many 'diversified' tech or growth ETFs are dominated by the same five mega-caps.",
    },
    "top_holdings": {
        "title": "Top holdings",
        "lens": "investor",
        "what": "The fund's biggest positions and their weights.",
        "how": "Reported by the fund, usually monthly or quarterly.",
        "read": "Owning this ETF is, in large part, owning these companies. Analyze the big ones on their own.",
        "trap": "Holdings data lags a little; weights drift as prices move.",
    },

    # ------------------------------------------------------------ trend
    "trend_state": {
        "title": "Trend",
        "lens": "trader",
        "what": "Whether price is above or below its short, medium and long-term averages.",
        "how": "Compares the last close with the 20-day EMA, 50-day SMA and 200-day SMA.",
        "read": "Above all three is an uptrend on every timeframe; below all three is a downtrend. Mixed often means a pause or a turn.",
        "trap": "Trends are obvious in hindsight. Price crosses an average and back again often, which traders call whipsaw.",
    },
    "sma": {
        "title": "Simple moving average (SMA)",
        "lens": "trader",
        "what": "The average closing price over the last N days, redrawn each day as a smooth line.",
        "how": "Sum of the last N closes ÷ N. The 50-day and 200-day are the most-watched.",
        "read": "Price above a rising average means an uptrend. The 200-day is the line many funds use to separate bull from bear.",
        "trap": "Averages lag: by the time price crosses one, much of the move has happened.",
    },
    "ema": {
        "title": "Exponential moving average (EMA)",
        "lens": "trader",
        "what": "A moving average that weights recent days more heavily, so it reacts faster.",
        "how": "Each day: EMA = previous EMA + (2 ÷ (N+1)) × (close − previous EMA).",
        "read": "The 20-day EMA tracks the short-term trend. In strong trends, pullbacks often stop near it.",
        "trap": "Faster means more false signals in choppy markets.",
    },
    "golden_cross": {
        "title": "Golden cross / death cross",
        "lens": "trader",
        "what": "When the 50-day average crosses above (golden) or below (death) the 200-day average.",
        "how": "Watch the two lines; the cross date is when they swap order.",
        "read": "Marks a shift in the medium-term trend relative to the long-term one. Widely watched, so it can move prices briefly.",
        "trap": "It lags badly: crosses often arrive after the move is mostly done, and they whipsaw in sideways markets.",
    },

    # ------------------------------------------------------------ momentum
    "rsi": {
        "title": "RSI (Relative Strength Index)",
        "lens": "trader",
        "what": "A 0–100 gauge of how strongly price has been moving up versus down recently.",
        "how": "Compares average gains to average losses over 14 days (Wilder's smoothing). 100 − 100 ÷ (1 + avg gain ÷ avg loss).",
        "read": "Above 70 is 'overbought', below 30 'oversold', 50 the midpoint. Price making a new high while RSI doesn't (divergence) hints at fading momentum.",
        "trap": "Overbought isn't a sell signal. Strong stocks stay above 70 for weeks, and falling ones stay under 30.",
    },
    "macd": {
        "title": "MACD",
        "lens": "trader",
        "what": "A momentum indicator built from two moving averages.",
        "how": "MACD line = 12-day EMA − 26-day EMA. Signal line = 9-day EMA of the MACD line. Histogram = the gap between them.",
        "read": "MACD crossing above its signal suggests momentum turning up; a growing histogram means momentum is building.",
        "trap": "It's built from averages, so it lags, and it chops around in sideways markets.",
    },
    "relative_strength": {
        "title": "Relative strength (vs the market)",
        "lens": "trader",
        "what": "Whether a stock has done better or worse than the S&P 500 recently.",
        "how": "The stock's return over 1 and 3 months next to SPY's over the same days.",
        "read": "Stocks that hold up when the market falls are showing strength. Leaders tend to keep leading for a while (momentum).",
        "trap": "Momentum can reverse sharply, especially after a crowded run.",
    },

    # ------------------------------------------------------------ volatility
    "atr": {
        "title": "ATR (Average True Range)",
        "lens": "trader",
        "what": "The typical size of a day's move in dollars, including overnight gaps.",
        "how": "True range = the largest of (high − low), |high − yesterday's close|, |low − yesterday's close|, averaged over 14 days.",
        "read": "Used to size positions and place stops: a stop inside one ATR is likely to be hit by normal noise.",
        "trap": "ATR says how far, not which way.",
    },
    "bollinger": {
        "title": "Bollinger Bands",
        "lens": "trader",
        "what": "A band around the 20-day average that widens when price is volatile and narrows when it's quiet.",
        "how": "Middle = 20-day SMA. Upper and lower = middle ± 2 standard deviations of the last 20 closes.",
        "read": "Closes outside the bands are unusual moves. A 'squeeze' (unusually narrow bands) often precedes a bigger move.",
        "trap": "Riding the upper band is normal in strong uptrends, so touching it is not a sell signal. A squeeze doesn't say which direction.",
    },

    # ------------------------------------------------------------ volume
    "relative_volume": {
        "title": "Relative volume",
        "lens": "trader",
        "what": "Today's volume compared with normal.",
        "how": "Today's volume ÷ average volume of the previous 20 days.",
        "read": "2× or more means something is happening (news, earnings, a big fund moving). Moves on heavy volume are more meaningful.",
        "trap": "During the trading day, today's bar is incomplete, so it reads low until the close.",
    },
    "up_down_volume": {
        "title": "Up/down volume ratio",
        "lens": "trader",
        "what": "Whether more shares trade on up days or down days.",
        "how": "Total volume on up days ÷ total volume on down days, last 20 sessions.",
        "read": "Above 1.3 suggests buying pressure (accumulation); below 0.77 suggests selling pressure (distribution).",
        "trap": "A single huge-volume day (earnings) can dominate the ratio.",
    },

    # ------------------------------------------------------------ levels and events
    "week52": {
        "title": "52-week high and low",
        "lens": "trader",
        "what": "The highest and lowest prices over the past year.",
        "how": "Max of daily highs and min of daily lows over the last 252 trading days.",
        "read": "Many traders watch these levels. New highs often attract buyers (breakouts); new lows can trigger more selling.",
        "trap": "'Near the low' is not the same as 'cheap'. The low can keep getting lower.",
    },
    "support_resistance": {
        "title": "Support and resistance",
        "lens": "trader",
        "what": "Price zones where buying (support) or selling (resistance) has repeatedly stepped in.",
        "how": "Tape finds swing highs and lows from the last 6 months and merges ones within 1.5% of each other. More touches = stronger level.",
        "read": "Levels mark where the odds shift. Once broken, old resistance often becomes new support and vice versa.",
        "trap": "Levels are zones, not exact prices, and they break all the time, especially on news.",
    },
    "earnings_date": {
        "title": "Earnings date",
        "lens": "trader",
        "what": "When the company next reports quarterly results.",
        "how": "Published by the company, usually 2–4 weeks ahead.",
        "read": "Stocks often gap 5–10% or more overnight on earnings, past any stop-loss. Short-term positions held through it are partly a coin flip.",
        "trap": "Good results can still send a stock down if they weren't as good as expected.",
    },

    # ------------------------------------------------------------ the two lenses
    "investor_vs_trader": {
        "title": "Investor view vs trader view",
        "lens": "both",
        "what": "Two separate ways of judging the same stock, over different time horizons.",
        "how": "The investor view looks at the business and its price over months to years. The trader view looks at price behaviour over days to weeks.",
        "read": "They often disagree: a great business can be in a short-term downtrend, and a weak one can be rallying. Both readings can be true at once.",
        "trap": "Mixing them up: buying on a short-term signal and then holding through a bad business 'for the long term'.",
    },
}

ALIASES = {
    "pe": "pe_trailing", "p/e": "pe_trailing", "price to earnings": "pe_trailing",
    "forward pe": "pe_forward", "forward p/e": "pe_forward",
    "ps": "price_to_sales", "p/s": "price_to_sales",
    "ev/ebitda": "ev_ebitda", "ebitda": "ev_ebitda", "enterprise value": "ev_ebitda",
    "fcf": "free_cash_flow", "cash flow": "free_cash_flow",
    "moving average": "sma", "200-day": "sma", "50-day": "sma", "200 day": "sma", "50 day": "sma",
    "death cross": "golden_cross", "overbought": "rsi", "oversold": "rsi",
    "bollinger bands": "bollinger", "squeeze": "bollinger", "band width": "bollinger",
    "average true range": "atr", "stop loss": "atr", "stop": "atr",
    "support": "support_resistance", "resistance": "support_resistance",
    "52 week": "week52", "52-week": "week52", "52-week high": "week52",
    "drawdown": "max_drawdown", "dividend": "dividend_yield", "yield": "dividend_yield",
    "fees": "expense_ratio", "expense": "expense_ratio", "fund size": "aum",
    "s&p 500": "benchmark", "spy": "benchmark", "index": "benchmark",
    "trend": "trend_state", "momentum": "relative_strength", "candle": "candlestick",
    "candles": "candlestick", "margin": "operating_margin", "debt": "debt_to_equity",
    "growth": "revenue_growth", "cagr": "revenue_cagr", "return": "total_return",
    "returns": "total_return", "lenses": "investor_vs_trader", "investor": "investor_vs_trader",
    "trader": "investor_vs_trader",
}


def lookup(term: str) -> dict | None:
    """Find an entry by key, alias or title, case-insensitively."""
    t = (term or "").strip().lower()
    key = t.replace(" ", "_")
    if key in GLOSSARY:
        return {"key": key, **GLOSSARY[key]}
    if t in ALIASES:
        k = ALIASES[t]
        return {"key": k, **GLOSSARY[k]}
    for k, entry in GLOSSARY.items():
        if t and (t in entry["title"].lower() or entry["title"].lower().startswith(t)):
            return {"key": k, **entry}
    return None
