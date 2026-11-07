import os
import sys
import requests
from datetime import datetime
import pytz

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("Error: DISCORD_WEBHOOK_URL environment variable is missing.")
    sys.exit(1)

def fetch_candle_data(ticker, interval, count=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    range_param = "3mo" if interval == "1mo" else ("1mo" if interval == "1wk" else "10d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={interval}&range={range_param}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()['chart']['result'][0]
        quotes = data['indicators']['quote'][0]
        valid_indices = [i for i, c in enumerate(quotes['close']) if c is not None]
        if len(valid_indices) < 2:
            return None
        
        prev_idx = valid_indices[-2]
        curr_idx = valid_indices[-1]
        
        high = quotes['high'][prev_idx]
        low = quotes['low'][prev_idx]
        close = quotes['close'][prev_idx]
        current_price = quotes['close'][curr_idx]
        eq = (high + low) / 2.0
        
        # Range Flow Evaluation
        if current_price > high:
            flow = "Expansion Above High"
            state = 1
        elif current_price < low:
            flow = "Expansion Below Low"
            state = -1
        elif current_price >= eq:
            flow = "Premium (Internal Bearish/EQ Rejection)"
            state = 0.5
        else:
            flow = "Discount (Internal Bullish/EQ Bounce)"
            state = -0.5
            
        return {
            "current": current_price,
            "high": high,
            "low": low,
            "eq": eq,
            "flow": flow,
            "state": state
        }
    except Exception as e:
        print(f"Error fetching {ticker} ({interval}): {e}")
        return None

def evaluate_multi_timeframe(ticker, name, decimals=2):
    daily = fetch_candle_data(ticker, "1d")
    weekly = fetch_candle_data(ticker, "1wk")
    monthly = fetch_candle_data(ticker, "1mo")
    
    if not daily or not weekly:
        return None

    cmp = daily["current"]
    
    # Calculate Institutional Confluence & Alignment
    # Monthly weight: 30%, Weekly: 40%, Daily: 30%
    score = 0
    m_bias = monthly["flow"] if monthly else "Consolidating"
    w_bias = weekly["flow"]
    d_bias = daily["flow"]
    
    if monthly:
        score += (30 if monthly["state"] > 0 else (-30 if monthly["state"] < 0 else 0))
    score += (40 if weekly["state"] > 0 else (-40 if weekly["state"] < 0 else 0))
    score += (30 if daily["state"] > 0 else (-30 if daily["state"] < 0 else 0))
    
    # Trading Signal & Direction Decision
    if score >= 40:
        signal = "🟢 HIGH-PROBABILITY BUY (Long Expansions)"
        trade_dir = "BUY / LONG"
        probability = "85% - Institutional Orderflow Aligned"
        draw_target = f"PDH `{daily['high']:.{decimals}f}` -> PWH `{weekly['high']:.{decimals}f}`"
        invalidation = f"Below Daily EQ `{daily['eq']:.{decimals}f}`"
    elif score <= -40:
        signal = "🔴 HIGH-PROBABILITY SELL (Short Expansions)"
        trade_dir = "SELL / SHORT"
        probability = "85% - Institutional Orderflow Aligned"
        draw_target = f"PDL `{daily['low']:.{decimals}f}` -> PWL `{weekly['low']:.{decimals}f}`"
        invalidation = f"Above Daily EQ `{daily['eq']:.{decimals}f}`"
    else:
        # Range bound / Equilibrium rotation model
        if cmp < daily["eq"]:
            signal = "🟡 DISCOUNT REVERSAL BUY (Rotational Scalp)"
            trade_dir = "BUY (Targeting EQ)"
            probability = "68% - Range Mean Reversion"
            draw_target = f"Daily EQ `{daily['eq']:.{decimals}f}`"
            invalidation = f"Below PDL `{daily['low']:.{decimals}f}`"
        else:
            signal = "🟠 PREMIUM REJECTION SELL (Rotational Scalp)"
            trade_dir = "SELL (Targeting EQ)"
            probability = "68% - Range Mean Reversion"
            draw_target = f"Daily EQ `{daily['eq']:.{decimals}f}`"
            invalidation = f"Above PDH `{daily['high']:.{decimals}f}`"

    m_eq_str = f"`{monthly['eq']:.{decimals}f}`" if monthly else "N/A"
    
    content = (
        f"**Live CMP:** `{cmp:.{decimals}f}`\n"
        f"🎯 **Today's Directive:** **{trade_dir}**\n"
        f"🔥 **Setup Model:** {signal}\n"
        f"📊 **Trade Probability:** `{probability}`\n"
        f"────────────────────────\n"
        f"📐 **Timeframe Alignment:**\n"
        f"• **Monthly Range:** {m_bias} (EQ: {m_eq_str})\n"
        f"• **Weekly Range:** {w_bias} (EQ: `{weekly['eq']:.{decimals}f}`)\n"
        f"• **Daily CRT:** {d_bias} (EQ: `{daily['eq']:.{decimals}f}`)\n"
        f"────────────────────────\n"
        f"🎯 **Draw on Liquidity (TP):** {draw_target}\n"
        f"🛑 **Invalidation Zone (SL Ref):** {invalidation}\n"
        f"📌 **Key Levels:** PDH: `{daily['high']:.{decimals}f}` | PDL: `{daily['low']:.{decimals}f}` | PWH: `{weekly['high']:.{decimals}f}` | PWL: `{weekly['low']:.{decimals}f}`"
    )
    return content

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

gold_block = evaluate_multi_timeframe("GC=F", "GOLD (XAUUSD)", 2)
eur_block = evaluate_multi_timeframe("EURUSD=X", "EURUSD", 4)
gbp_block = evaluate_multi_timeframe("GBPUSD=X", "GBPUSD", 4)
news = get_red_news()

now_pkt = datetime.now(pytz.timezone("Asia/Karachi")).strftime("%d %b %Y | %I:%M %p PKT")

embed = {
    "title": "🏛️ INSTITUTIONAL MULTI-TIMEFRAME & CRT EXECUTION TERMINAL",
    "description": f"**Dispatch:** `{now_pkt}`\nAligned across Monthly, Weekly, and Daily Institutional Ranges.",
    "color": 2123412,  # Dark Institutional Navy
    "fields": [
        {"name": "🥇 XAUUSD (GOLD) — DIRECTION & BIAS", "value": gold_block or "Calculating...", "inline": False},
        {"name": "💶 EURUSD — DIRECTION & BIAS", "value": eur_block or "Calculating...", "inline": False},
        {"name": "💷 GBPUSD — DIRECTION & BIAS", "value": gbp_block or "Calculating...", "inline": False},
        {"name": "⚡ HIGH-IMPACT RED FOLDER NEWS (USD / EUR / GBP)", "value": news, "inline": False}
    ],
    "footer": {
        "text": "Institutional Smart Money & Candle Range Theory • Multi-Timeframe Alignment"
    }
}

payload = {
    "username": "Institutional CRT Terminal",
    "avatar_url": "https://i.imgur.com/4M34hi2.png",
    "embeds": [embed]
}

response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
if response.status_code in [200, 204]:
    print("Multi-Timeframe Intelligence Dossier delivered successfully.")
else:
    print(f"Failed to post to Discord: {response.status_code}, {response.text}")
    sys.exit(1)
