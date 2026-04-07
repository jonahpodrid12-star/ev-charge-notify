from flask import Flask, jsonify, request
import requests
from datetime import datetime
import json
import os

app = Flask(__name__)

NTFY_TOPIC = "podrid-ev-charger"

# ============================================================
# VISITOR COUNTER
# ============================================================
# We store the count in a simple JSON file on disk.
# Every time someone visits the homepage, we add 1.
# On Render's free tier, this file resets when the server
# restarts -- but it's a great starting point!

COUNTER_FILE = "/tmp/visitor_count.json"

def get_visitor_count():
    """Read the current visitor count from the file."""
    try:
        with open(COUNTER_FILE, "r") as f:
            data = json.load(f)
            return data.get("count", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

def increment_visitor_count():
    """Add 1 to the visitor count and save it."""
    count = get_visitor_count() + 1
    with open(COUNTER_FILE, "w") as f:
        json.dump({"count": count}, f)
    return count


# ============================================================
# PRICE DATA FUNCTION
# ============================================================
# This function does THREE things:
#   1. Fetches the current hour's average price from ComEd
#   2. Fetches the last 12 five-minute price readings
#   3. Calculates the trend (rising/falling/steady)
#   4. Picks the right advice message based on price + trend

def get_price_data():
    try:
        # STEP 1: Get the current hour's average price
        # ComEd's API returns JSON like: [{"millisUTC": "...", "price": "3.5"}]
        url_current = "https://hourlypricing.comed.com/api?type=currenthouraverage"
        current_data = requests.get(url_current, timeout=10).json()
        current_price = float(current_data[0]["price"])

        # STEP 2: Get the 5-minute price feed (most recent readings)
        url_recent = "https://hourlypricing.comed.com/api?type=5minutefeed"
        recent_data = requests.get(url_recent, timeout=10).json()

        # STEP 3: Calculate the trend
        # We compare the average of the 3 newest readings vs 3 older ones
        last_6 = recent_data[:6]
        prices = [float(r["price"]) for r in last_6]
        older_avg = sum(prices[3:]) / 3   # older 3 readings
        newer_avg = sum(prices[:3]) / 3    # newer 3 readings

        difference = newer_avg - older_avg
        if difference > 0.5:
            trend, arrow = "RISING", "^"
        elif difference < -0.5:
            trend, arrow = "FALLING", "v"
        else:
            trend, arrow = "STEADY", "="

        # STEP 4: Pick advice based on price level + trend
        if current_price < 3:
            if trend == "RISING":
                advice = "Price is LOW but rising -- plug in NOW before it goes up!"
                color = "#f59e0b"
                emoji = "&#9889;"
            else:
                advice = "GREAT time to plug in! Price is low."
                color = "#22c55e"
                emoji = "&#9989;"
        elif current_price < 6:
            if trend == "FALLING":
                advice = "Price is OK and dropping -- could wait a bit for even cheaper."
                color = "#3b82f6"
                emoji = "&#128201;"
            else:
                advice = "Price is OK. Fine to charge."
                color = "#3b82f6"
                emoji = "&#128077;"
        elif current_price < 10:
            if trend == "FALLING":
                advice = "Price is high but coming down -- wait a little longer."
                color = "#f59e0b"
                emoji = "&#9203;"
            else:
                advice = "Price is HIGH. Wait for it to drop."
                color = "#ef4444"
                emoji = "&#10060;"
        else:
            advice = "Price is VERY HIGH. Definitely wait!"
            color = "#ef4444"
            emoji = "&#128680;"

        # Build the list of recent prices for the chart
        recent_prices = [{"price": float(r["price"]), "time": r["millisUTC"]} for r in recent_data[:12]]

        return {
            "price": round(current_price, 2),
            "trend": trend,
            "arrow": arrow,
            "advice": advice,
            "color": color,
            "emoji": emoji,
            "recent": recent_prices,
            "time": datetime.now().strftime("%I:%M %p")
        }
    except Exception as e:
        return {"error": str(e)[:100]}


# ============================================================
# NOTIFICATION FUNCTION
# ============================================================
# Gets the price data, builds a message, and sends it to ntfy

def check_and_notify():
    data = get_price_data()
    if "error" in data:
        return f"ERR: {data['error']}"
    try:
        message = f"ComEd {data['time']}: {data['price']:.1f}c/kWh {data['arrow']}{data['trend']}\n{data['advice']}"
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message, timeout=10)
        return "OK"
    except Exception as e:
        return f"ERR: {str(e)[:50]}"


# ============================================================
# API ROUTES
# ============================================================
# These are the URLs that the server responds to.
# Each @app.route() decorator maps a URL to a Python function.

# /api/price -- Returns price data as JSON (used by the dashboard JavaScript)
@app.route("/api/price")
def api_price():
    data = get_price_data()
    return jsonify(data)

# /api/visitors -- Returns the visitor count as JSON
@app.route("/api/visitors")
def api_visitors():
    count = get_visitor_count()
    return jsonify({"count": count})

# /check-price -- Checks the price AND sends a notification
@app.route("/check-price")
def check_price():
    result = check_and_notify()
    return result

# /ping -- Simple health check for the keep-alive cron job
@app.route("/ping")
def ping():
    return "OK"

# / -- The homepage! This serves the full dashboard HTML
@app.route("/")
def home():
    # Increment the visitor counter every time someone loads the page
    count = increment_visitor_count()

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EV Charge Notify - ComEd Price Tracker</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
.hero{text-align:center;padding:40px 20px 20px}
.hero h1{font-size:2.2em;margin-bottom:8px}
.hero h1 span{color:#22c55e}
.hero p{color:#94a3b8;font-size:1.1em}
.counter{text-align:center;margin:8px 0 0;color:#64748b;font-size:0.85em}
.counter b{color:#22c55e}
.dashboard{max-width:600px;margin:20px auto;padding:0 20px}
.price-card{background:#1e293b;border-radius:16px;padding:30px;text-align:center;margin-bottom:20px;border:1px solid #334155}
.price-big{font-size:4em;font-weight:800;line-height:1}
.price-unit{font-size:0.3em;font-weight:400;color:#94a3b8}
.trend-badge{display:inline-block;padding:6px 16px;border-radius:20px;font-size:0.9em;font-weight:600;margin:12px 0}
.advice-text{font-size:1.15em;margin-top:10px;line-height:1.4}
.chart-card{background:#1e293b;border-radius:16px;padding:20px;margin-bottom:20px;border:1px solid #334155}
.chart-card h3{margin-bottom:12px;color:#94a3b8;font-size:0.85em;text-transform:uppercase;letter-spacing:1px}
.bar-chart{display:flex;align-items:flex-end;gap:4px;height:120px;padding-top:10px}
.bar{flex:1;border-radius:4px 4px 0 0;min-width:0;transition:height 0.3s;position:relative}
.bar:hover::after{content:attr(data-label);position:absolute;top:-22px;left:50%;transform:translateX(-50%);font-size:11px;white-space:nowrap;background:#334155;padding:2px 6px;border-radius:4px}
.time-labels{display:flex;gap:4px;margin-top:4px}
.time-labels span{flex:1;text-align:center;font-size:10px;color:#64748b}
.setup-card{background:linear-gradient(135deg,#1e3a5f,#1e293b);border-radius:16px;padding:25px;margin-bottom:20px;border:1px solid #334155}
.setup-card h2{font-size:1.3em;margin-bottom:6px;text-align:center}
.setup-card .subtitle{color:#94a3b8;text-align:center;margin-bottom:20px;font-size:0.95em}
.step{display:flex;gap:14px;margin:16px 0;align-items:flex-start}
.step-num{background:#22c55e;color:#0f172a;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85em;flex-shrink:0;margin-top:2px}
.step-content{flex:1}
.step-content b{color:#e2e8f0}
.step-content p{color:#94a3b8;font-size:0.9em;margin-top:2px;line-height:1.4}
.store-links{display:flex;gap:10px;margin-top:8px;flex-wrap:wrap}
.store-btn{display:inline-flex;align-items:center;gap:6px;padding:8px 14px;border-radius:8px;text-decoration:none;font-size:0.85em;font-weight:600;transition:transform 0.1s}
.store-btn:hover{transform:scale(1.05)}
.store-btn.apple{background:#000;color:#fff;border:1px solid #333}
.store-btn.google{background:#fff;color:#000;border:1px solid #ddd}
.topic-box{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 14px;margin-top:8px;display:flex;align-items:center;justify-content:space-between}
.topic-name{font-family:monospace;font-size:1em;color:#22c55e;font-weight:700}
.copy-btn{background:#334155;color:#e2e8f0;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:0.8em}
.copy-btn:hover{background:#475569}
.btn{display:inline-block;background:#22c55e;color:#0f172a;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:1em;transition:transform 0.1s}
.btn:hover{transform:scale(1.05)}
.check-btn{background:#3b82f6;color:white;border:none;padding:10px 20px;border-radius:8px;font-size:0.95em;font-weight:600;cursor:pointer;margin-top:12px;transition:transform 0.1s}
.check-btn:hover{transform:scale(1.05)}
.actions{text-align:center;margin-top:20px}
.footer{text-align:center;padding:20px;color:#475569;font-size:0.85em}
.loading{color:#94a3b8;padding:40px;text-align:center}
.updated{color:#64748b;font-size:0.8em;margin-top:8px}
.divider{border:none;border-top:1px solid #334155;margin:20px 0}
@media(max-width:480px){.hero h1{font-size:1.6em}.price-big{font-size:3em}.store-links{flex-direction:column}}
</style>
</head>
<body>
<div class="hero">
<h1>&#9889; <span>EV Charge</span> Notify</h1>
<p>Real-time ComEd pricing for EV owners</p>
<div class="counter" id="visitorCount">&#127775; <b>""" + str(count) + """</b> people have visited</div>
</div>
<div class="dashboard">

<div class="price-card" id="priceCard">
<div class="loading">Loading live price...</div>
</div>

<div class="setup-card">
<h2>&#128241; Get Free Alerts on Your Phone</h2>
<p class="subtitle">Takes 2 minutes -- works on iPhone and Android</p>

<div class="step">
<span class="step-num">1</span>
<div class="step-content">
<b>Download the ntfy app (free)</b>
<p>ntfy is a free push notification app. Download it for your phone:</p>
<div class="store-links">
<a class="store-btn apple" href="https://apps.apple.com/us/app/ntfy/id1625396347" target="_blank">&#63743; App Store (iPhone)</a>
<a class="store-btn google" href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank">&#9654; Play Store (Android)</a>
</div>
</div>
</div>

<div class="step">
<span class="step-num">2</span>
<div class="step-content">
<b>Subscribe to our topic</b>
<p>Open the ntfy app, tap the + button, and type in this exact topic name:</p>
<div class="topic-box">
<span class="topic-name">podrid-ev-charger</span>
<button class="copy-btn" onclick="copyTopic()">Copy</button>
</div>
</div>
</div>

<div class="step">
<span class="step-num">3</span>
<div class="step-content">
<b>That's it -- you'll get alerts!</b>
<p>Every afternoon between 2:30 and 7:30 PM (peak EV charging hours), you'll get a notification telling you whether it's a good time to plug in or if you should wait.</p>
</div>
</div>

<hr class="divider">

<div class="actions">
<a class="btn" href="https://ntfy.sh/podrid-ev-charger" target="_blank">Open Topic in Browser</a>
<br>
<button class="check-btn" onclick="sendCheck()">&#128225; Send Test Notification</button>
<div id="checkResult" style="margin-top:8px;font-size:0.85em;color:#94a3b8"></div>
</div>
</div>

<div class="footer">
Built by the Podrid family &#9889; Powered by ComEd Hourly Pricing
</div>
</div>

<script>
// ============================================================
// JAVASCRIPT - This code runs in the user's browser
// ============================================================

// Load the current price from our API and update the dashboard
async function loadPrice(){
try{
const r=await fetch('/api/price');
const d=await r.json();
if(d.error){document.getElementById('priceCard').innerHTML='<div class="loading">Could not load price</div>';return}

// Update the price card with current data
document.getElementById('priceCard').innerHTML=
'<div class="price-big" style="color:'+d.color+'">'+d.price.toFixed(1)+'<span class="price-unit"> c/kWh</span></div>'+
'<div class="trend-badge" style="background:'+d.color+'22;color:'+d.color+'">'+d.arrow+' '+d.trend+'</div>'+
'<div class="advice-text">'+d.emoji+' '+d.advice+'</div>'+
'<div class="updated">Updated '+d.time+'</div>';
}catch(e){document.getElementById('priceCard').innerHTML='<div class="loading">Could not load price</div>'}}

// Send a test notification to all subscribed phones
async function sendCheck(){
const el=document.getElementById('checkResult');
el.textContent='Sending...';
try{const r=await fetch('/check-price');const t=await r.text();el.textContent=t==='OK'?'Notification sent!':'Error: '+t}
catch(e){el.textContent='Failed to send'}}

// Copy the topic name to clipboard
function copyTopic(){
navigator.clipboard.writeText('podrid-ev-charger').then(function(){
document.querySelector('.copy-btn').textContent='Copied!';
setTimeout(function(){document.querySelector('.copy-btn').textContent='Copy'},2000);
}).catch(function(){
// Fallback if clipboard API fails
document.querySelector('.copy-btn').textContent='Select and copy above';
})}

// Load the price immediately when the page opens
loadPrice();
// Then refresh it every 5 minutes (300000 milliseconds)
setInterval(loadPrice,300000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
