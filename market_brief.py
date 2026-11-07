import os
import sys
import requests
from datetime import datetime
import pytz

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("Error: DISCORD_WEBHOOK_URL environment variable is missing.")
    sys.exit(1)

def get_market_data(ticker):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()['chart']['result'][0]
        quotes = data['indicators']['quote'][0]
        valid_indices = [i for i, c in enumerate(quotes['close']) if c is not None]
        
        if len(valid_indices) < 2:
            return None
            
        prev_idx = valid_indices[-2]
        curr_idx = valid_indices[-1]
        
        pd_high = quotes['high'][prev_idx]
        pd_low = quotes['low'][prev_idx]
        pd_close = quotes['close'][prev_idx]
        current_price = quotes['close'][curr_idx]
        
        # Candle Range Theory (CRT) & Equilibrium Calculation
        pd_eq = (pd_high + pd_low) / 2
        
        if current_price > pd_high:
            bias = "Bullish Expansion (Above PDH)"
        elif current_price < pd_low:
            bias = "Bearish Expansion (Below PDL)"
        elif current_price > pd_eq:
            bias = "Premium Range (Bullish Internal Flow)"
        else:
            bias = "Discount Range (Bearish Internal Flow)"
            
        return {
            "current": current_price,
            "pdh": pd_high,
            "pdl": pd_low,
            "eq": pd_eq,
            "bias": bias
        }
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

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

# Market Data Collection
xau = get_market_data("GC=F")       # Gold
eur = get_market_data("EURUSD=X")   # EURUSD
gbp = get_market_data("GBPUSD=X")   # GBPUSD
news = get_red_news()

now_pkt = datetime.now(pytz.timezone("Asia/Karachi")).strftime("%d %b %Y | %I:%M %p PKT")

def format_asset(name, data, decimals=2):
    if not data:
        return f"**{name}**: Data temporarily unavailable"
    return (
        f"**Live CMP:** `{data['current']:.{decimals}f}`\n"
        f"• **PDH:** `{data['pdh']:.{decimals}f}` | **PDL:** `{data['pdl']:.{decimals}f}`\n"
        f"• **Range 50% (EQ):** `{data['eq']:.{decimals}f}`\n"
        f"• **CRT Structure:** `{data['bias']}`"
    )

gold_block = format_asset("GOLD (XAUUSD)", xau, 2)
eur_block = format_asset("EURUSD", eur, 4)
gbp_block = format_asset("GBPUSD", gbp, 4)

embed = {
    "title": "🏛️ INSTITUTIONAL CRT PRE-MARKET INTELLIGENCE",
    "description": f"**Timestamp:** `{now_pkt}`\nConfidential Market Briefing for London & NY Open Prep.",
    "color": 15844367,  # Gold Theme
    "fields": [
        {"name": "🥇 XAUUSD (GOLD)", "value": gold_block, "inline": False},
        {"name": "💶 EURUSD", "value": eur_block, "inline": True},
        {"name": "💷 GBPUSD", "value": gbp_block, "inline": True},
        {"name": "⚡ HIGH-IMPACT RED FOLDER NEWS (USD / EUR / GBP)", "value": news, "inline": False}
    ],
    "footer": {
        "text": "Automated Market Intelligence • Candle Range Theory Execution"
    }
}

payload = {
    "username": "Institutional CRT Terminal",
    "avatar_url": "https://i.imgur.com/4M34hi2.png",
    "embeds": [embed]
}

response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
if response.status_code in [200, 204]:
    print("Intelligence Dossier delivered successfully to Discord.")
else:
    print(f"Failed to post to Discord: {response.status_code}, {response.text}")
    sys.exit(1)
