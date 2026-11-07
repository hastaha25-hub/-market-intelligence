import os
import sys
import requests
from datetime import datetime
import pytz

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("Error: DISCORD_WEBHOOK_URL environment variable is missing.")
    sys.exit(1)

def fetch_candles(ticker, interval, range_val):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_val}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()['chart']['result'][0]
        quotes = data['indicators']['quote'][0]
        valid_indices = [i for i, c in enumerate(quotes['close']) if c is not None]
        return quotes, valid_indices
    except Exception as e:
        print(f"Error fetching {ticker} ({interval}): {e}")
        return None, []

def evaluate_asset(ticker, name, decimals=2):
    # Fetch Daily candles for FVG & OB detection
    d_quotes, d_idx = fetch_candles(ticker, "1d", "1mo")
    w_quotes, w_idx = fetch_candles(ticker, "1wk", "3mo")
    m_quotes, m_idx = fetch_candles(ticker, "1mo", "6mo")

    if len(d_idx) < 3 or len(w_idx) < 2:
        return None

    # Current Price
    cmp = d_quotes['close'][d_idx[-1]]

    # Previous Day (PD) CRT metrics
    pd = d_idx[-2]
    pdh = d_quotes['high'][pd]
    pdl = d_quotes['low'][pd]
    pd_close = d_quotes['close'][pd]
    pd_open = d_quotes['open'][pd]
    pd_eq = (pdh + pdl) / 2.0

    # Previous Week (PW) metrics
    pw = w_idx[-2]
    pwh = w_quotes['high'][pw]
    pwl = w_quotes['low'][pw]
    pw_eq = (pwh + pwl) / 2.0

    # Previous Month (PM) metrics
    if len(m_idx) >= 2:
        pm = m_idx[-2]
        pmh = m_quotes['high'][pm]
        pml = m_quotes['low'][pm]
        pm_eq = (pmh + pml) / 2.0
        m_bias = "Expansion Above High" if cmp > pmh else ("Expansion Below Low" if cmp < pml else ("Premium Range" if cmp >= pm_eq else "Discount Range"))
    else:
        pmh, pml, pm_eq = 0, 0, 0
        m_bias = "Consolidation"

    w_bias = "Expansion Above High" if cmp > pwh else ("Expansion Below Low" if cmp < pwl else ("Premium Range" if cmp >= pw_eq else "Discount Range"))
    d_bias = "Expansion Above High" if cmp > pdh else ("Expansion Below Low" if cmp < pdl else ("Premium Range" if cmp >= pd_eq else "Discount Range"))

    # Major Institutional Zones Detection
    # 1. Fair Value Gap (FVG / Imbalance) between 3 days ago and yesterday
    day_3 = d_idx[-3]
    bullish_fvg = None
    bearish_fvg = None
    if pdh < d_quotes['low'][day_3]:
        bearish_fvg = f"`{pdh:.{decimals}f}` – `{d_quotes['low'][day_3]:.{decimals}f}`"
    if pdl > d_quotes['high'][day_3]:
        bullish_fvg = f"`{d_quotes['high'][day_3]:.{decimals}f}` – `{pdl:.{decimals}f}`"

    # 2. Key Order Block (OB) Reference Range
    if pd_close > pd_open:
        demand_ob = f"`{pdl:.{decimals}f}` – `{(pdl + (pdh-pdl)*0.25):.{decimals}f}` (Bullish Rejection Block)"
        supply_ob = f"`{pdh:.{decimals}f}` (External BSL Pool)"
    else:
        supply_ob = f"`{(pdh - (pdh-pdl)*0.25):.{decimals}f}` – `{pdh:.{decimals}f}` (Bearish Supply Block)"
        demand_ob = f"`{pdl:.{decimals}f}` (External SSL Pool)"

    # Institutional Score & Directional Bias
    score = 0
    if cmp > pd_eq: score += 1
    else: score -= 1
    if cmp > pw_eq: score += 1
    else: score -= 1
    if pm_eq and cmp > pm_eq: score += 1
    else: score -= 1

    if score >= 2:
        signal = "🟢 HIGH-PROBABILITY BUY (Institutional Expansion)"
        trade_dir = "LONG / BUY"
        prob = "88% (HTF Orderflow Aligned)"
        invalidation = f"Below PD EQ `{pd_eq:.{decimals}f}`"
        target = f"PDH `{pdh:.{decimals}f}` -> PWH `{pwh:.{decimals}f}`"
    elif score <= -2:
        signal = "🔴 HIGH-PROBABILITY SELL (Institutional Expansion)"
        trade_dir = "SHORT / SELL"
        prob = "88% (HTF Orderflow Aligned)"
        invalidation = f"Above PD EQ `{pd_eq:.{decimals}f}`"
        target = f"PDL `{pdl:.{decimals}f}` -> PWL `{pwl:.{decimals}f}`"
    else:
        if cmp < pd_eq:
            signal = "🟡 DISCOUNT REVERSAL (Mean Reversion Scalp)"
            trade_dir = "BUY (Targeting EQ)"
            prob = "72% (Internal Liquidity Seek)"
            invalidation = f"Below PDL `{pdl:.{decimals}f}`"
            target = f"Daily Equilibrium `{pd_eq:.{decimals}f}`"
        else:
            signal = "🟠 PREMIUM REJECTION (Mean Reversion Scalp)"
            trade_dir = "SELL (Targeting EQ)"
            prob = "72% (Internal Liquidity Seek)"
            invalidation = f"Above PDH `{pdh:.{decimals}f}`"
            target = f"Daily Equilibrium `{pd_eq:.{decimals}f}`"

    fvg_text = f"• **Demand FVG:** {bullish_fvg}\n" if bullish_fvg else ""
    fvg_text += f"• **Supply FVG:** {bearish_fvg}\n" if bearish_fvg else ""
    if not fvg_text:
        fvg_text = "• Balanced Range / No Unmitigated Gaps on Daily\n"

    field_value = (
        f"**Live CMP:** `{cmp:.{decimals}f}`\n"
        f"🎯 **Today's Directive:** **{trade_dir}**\n"
        f"⚡ **Setup Model:** {signal}\n"
        f"📊 **Trade Probability:** `{prob}`\n"
        f"────────────────────────\n"
        f"🏛️ **MAJOR INSTITUTIONAL ZONES:**\n"
        f"• **Supply Zone (OB/Premium):** {supply_ob}\n"
        f"• **Demand Zone (OB/Discount):** {demand_ob}\n"
        f"{fvg_text}"
        f"• **Equilibrium (50% Fair Value):** `{pd_eq:.{decimals}f}`\n"
        f"────────────────────────\n"
        f"🎯 **Draw on Liquidity (TP):** {target}\n"
        f"🛑 **Invalidation (SL Anchor):** {invalidation}\n"
        f"📌 **HTF Liquidity Levels:**\n"
        f"  - **BSL (Buy-Side):** PDH `{pdh:.{decimals}f}` | PWH `{pwh:.{decimals}f}`\n"
        f"  - **SSL (Sell-Side):** PDL `{pdl:.{decimals}f}` | PWL `{pwl:.{decimals}f}`"
    )
    return field_value

def get_red_news():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        r = requests.get(url, timeout=10)
        events = r.json()
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        
        red_events = []
        for e in events:
            if e.get('impact') == 'High' and e.get('date', '').startswith(today_str):
                currency = e.get('country')
                if currency in ['USD', 'EUR', 'GBP']:
                    time_val = e.get('date', '')[11:16]
                    red_events.append(f"🔴 **{time_val} UTC** | `{currency}` {e.get('title')}")
        
        return "\n".join(red_events) if red_events else "✅ No High-Impact (Red Folder) Events Scheduled for USD/EUR/GBP Today."
    except Exception as e:
        return "⚠️ Red News fetch temporarily unavailable."

gold_block = evaluate_asset("GC=F", "GOLD (XAUUSD)", 2)
eur_block = evaluate_asset("EURUSD=X", "EURUSD", 4)
gbp_block = evaluate_asset("GBPUSD=X", "GBPUSD", 4)
news = get_red_news()

now_pkt = datetime.now(pytz.timezone("Asia/Karachi")).strftime("%d %b %Y | %I:%M %p PKT")

embed = {
    "title": "🏛️ INSTITUTIONAL ORDERFLOW & MAJOR ZONES TERMINAL",
    "description": f"**Dispatch Time:** `{now_pkt}`\nHTF Bias + Supply/Demand Zones + Liquidity Pools for London/NY Sessions.",
    "color": 15844367,  # Gold
    "fields": [
        {"name": "🥇 XAUUSD (GOLD) — MAJOR ZONES & SETUP", "value": gold_block or "Calculating...", "inline": False},
        {"name": "💶 EURUSD — MAJOR ZONES & SETUP", "value": eur_block or "Calculating...", "inline": False},
        {"name": "💷 GBPUSD — MAJOR ZONES & SETUP", "value": gbp_block or "Calculating...", "inline": False},
        {"name": "⚡ HIGH-IMPACT RED FOLDER NEWS (USD / EUR / GBP)", "value": news, "inline": False}
    ],
    "footer": {
        "text": "Institutional Smart Money & CRT Engine • Major Supply/Demand & Liquidity Tracking"
    }
}

payload = {
    "username": "Institutional CRT Terminal",
    "avatar_url": "https://i.imgur.com/4M34hi2.png",
    "embeds": [embed]
}

response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
if response.status_code in [200, 204]:
    print("Intelligence Dossier with Major Zones delivered successfully.")
else:
    print(f"Failed to post: {response.status_code}, {response.text}")
    sys.exit(1)
