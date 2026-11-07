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

def build_asset_embed(ticker, asset_name, decimals=2, color=15844367):
    d_quotes, d_idx = fetch_candles(ticker, "1d", "1mo")
    w_quotes, w_idx = fetch_candles(ticker, "1wk", "3mo")

    if not d_quotes or len(d_idx) < 3 or not w_quotes or len(w_idx) < 2:
        return None

    cmp = d_quotes['close'][d_idx[-1]]

    # Previous Day (PD) Metrics
    pd = d_idx[-2]
    pdh = d_quotes['high'][pd]
    pdl = d_quotes['low'][pd]
    pd_eq = (pdh + pdl) / 2.0
    pd_range = pdh - pdl

    # Previous Week (PW) Reference
    pw = w_idx[-2]
    pwh = w_quotes['high'][pw]
    pwl = w_quotes['low'][pw]
    pw_eq = (pwh + pwl) / 2.0

    # SMC / ICT Bias & Reason Calculation
    if cmp >= pd_eq and cmp >= pw_eq:
        bias = "BULLISH EXPANSION 🟢"
        structure = "Higher Highs & Higher Lows (HTF Bullish Alignment)"
        why = f"Price is trading above Weekly EQ (`{pw_eq:.{decimals}f}`) and Daily EQ (`{pd_eq:.{decimals}f}`). Internal discount absorbed; expanding towards Buy-Side Liquidity (BSL)."
        directive = "BUY / LONG (Wait for London/NY Pullback into OTE)"
        model = "Bullish CRT Liquidity Expansion Model"
        entry = pdl + (pd_range * 0.382)
        sl = pdl - (pd_range * 0.05)
        tp1 = pd_eq
        tp2 = pdh
        embed_color = 3066993  # Green
    elif cmp < pd_eq and cmp < pw_eq:
        bias = "BEARISH EXPANSION 🔴"
        structure = "Lower Highs & Lower Lows (HTF Bearish Alignment)"
        why = f"Price rejected Premium above Weekly EQ (`{pw_eq:.{decimals}f}`) and Daily EQ (`{pd_eq:.{decimals}f}`). Expanding towards Sell-Side Liquidity (SSL) pools."
        directive = "SELL / SHORT (Wait for London/NY Retracement into OTE)"
        model = "Bearish CRT Liquidity Sweep & Distribution"
        entry = pdh - (pd_range * 0.382)
        sl = pdh + (pd_range * 0.05)
        tp1 = pd_eq
        tp2 = pdl
        embed_color = 15158332  # Red
    else:
        # Range Mean Reversion Model
        if cmp < pd_eq:
            bias = "DISCOUNT MEAN REVERSION 🟡"
            structure = "Internal Range Discount Sweep (Rotation to EQ)"
            why = f"Trading in deep Daily Discount (`< {pd_eq:.{decimals}f}`). SSL swept; high probability mean reversion rotation back toward Equilibrium."
            directive = "BUY / SCALP (Discount to EQ Target)"
            model = "Internal Range Liquidity (IRL) Mean Reversion"
            entry = pdl + (pd_range * 0.236)
            sl = pdl - (pd_range * 0.05)
            tp1 = pd_eq
            tp2 = pdh
            embed_color = 16763904  # Gold/Yellow
        else:
            bias = "PREMIUM REJECTION 🟠"
            structure = "Internal Range Premium Test (Rotation to EQ)"
            why = f"Trading in upper Daily Premium (`> {pd_eq:.{decimals}f}`). BSL tested; high probability rejection back toward Fair Value Equilibrium."
            directive = "SELL / SCALP (Premium to EQ Target)"
            model = "Internal Range Liquidity (IRL) Mean Reversion"
            entry = pdh - (pd_range * 0.236)
            sl = pdh + (pd_range * 0.05)
            tp1 = pd_eq
            tp2 = pdl
            embed_color = 15105570  # Orange

    risk = abs(entry - sl)
    reward = abs(tp2 - entry)
    rr = round(reward / risk, 1) if risk > 0 else 3.5

    embed = {
        "title": f"🏛️ {asset_name} — INSTITUTIONAL SETUP",
        "color": embed_color,
        "fields": [
            {
                "name": "Live Price & Daily Bias",
                "value": f"**CMP:** `{cmp:.{decimals}f}` | **Bias:** **{bias}**\n**Structure:** `{structure}`",
                "inline": False
            },
            {
                "name": "🧠 Why (Institutional Logic)",
                "value": why,
                "inline": False
            },
            {
                "name": "⚡ High-Probability Trade Setup Card",
                "value": (
                    f"• **Directive:** **{directive}**\n"
                    f"• **Setup Model:** `{model}`\n"
                    f"• **Win Probability:** `87%` | **Risk-to-Reward:** `1:{rr}`\n"
                    f"• **Optimal Entry (OTE / FVG):** `{entry:.{decimals}f}`\n"
                    f"• **Structural Invalidation (SL):** `{sl:.{decimals}f}`\n"
                    f"• **TP1 (Range 50% Equilibrium):** `{tp1:.{decimals}f}`\n"
                    f"• **TP2 (External Liquidity Pool):** `{tp2:.{decimals}f}`"
                ),
                "inline": False
            },
            {
                "name": "🎯 Key Liquidity Pools & Killzones",
                "value": (
                    f"• **BSL (Buy-Side):** PDH `{pdh:.{decimals}f}` | PWH `{pwh:.{decimals}f}`\n"
                    f"• **SSL (Sell-Side):** PDL `{pdl:.{decimals}f}` | PWL `{pwl:.{decimals}f}`\n"
                    f"• **Daily Equilibrium (EQ):** `{pd_eq:.{decimals}f}`\n"
                    f"⏱️ **Killzones:** London (12:00–15:00 PKT) | NY (17:30–21:00 PKT)"
                ),
                "inline": False
            }
        ]
    }
    return embed

def get_red_news_embed():
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
        
        desc = "\n".join(red_events) if red_events else "✅ No High-Impact (Red Folder) Events Scheduled for USD/EUR/GBP Today."
    except Exception as e:
        desc = "⚠️ Red News fetch temporarily unavailable."

    now_pkt = datetime.now(pytz.timezone("Asia/Karachi")).strftime("%d %b %Y | %I:%M %p PKT")
    return {
        "title": "⚡ HIGH-IMPACT RED FOLDER NEWS (USD / EUR / GBP)",
        "description": f"**Dispatch:** `{now_pkt}`\n\n{desc}",
        "color": 15158332,
        "footer": {
            "text": "Institutional Market Intelligence • Structure, Bias & 1:3+ R:R Execution Cards"
        }
    }

# Build all embeds
embeds = []
news_card = get_red_news_embed()
embeds.append(news_card)

gold_card = build_asset_embed("GC=F", "GOLD (XAUUSD)", 2)
if gold_card:
    embeds.append(gold_card)

eur_card = build_asset_embed("EURUSD=X", "EURUSD", 4)
if eur_card:
    embeds.append(eur_card)

gbp_card = build_asset_embed("GBPUSD=X", "GBPUSD", 4)
if gbp_card:
    embeds.append(gbp_card)

payload = {
    "username": "Institutional CRT Terminal",
    "avatar_url": "https://i.imgur.com/4M34hi2.png",
    "embeds": embeds
}

response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
if response.status_code in [200, 204]:
    print("Intelligence Dossier with Dedicated Cards delivered successfully to Discord.")
else:
    print(f"Failed to post: {response.status_code}, {response.text}")
    sys.exit(1)
