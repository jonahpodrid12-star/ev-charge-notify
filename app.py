from flask import Flask, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

NTFY_TOPIC = "podrid-ev-charger"

def get_price_data():
    try:
        url_current = "https://hourlypricing.comed.com/api?type=currenthouraverage"
        current_data = requests.get(url_current, timeout=10).json()
        current_price = float(current_data[0]["price"])

        url_recent = "https://hourlypricing.comed.com/api?type=5minutefeed"
        recent_data = requests.get(url_recent, timeout=10).json()

        last_6 = recent_data[:6]
        prices = [float(r["price"]) for r in last_6]
        older_avg = sum(prices[3:]) / 3
        newer_avg = sum(prices[:3]) / 3

        difference = newer_avg - older_avg
        if difference > 0.5:
            trend, arrow = "RISING", "^"
        elif difference < -0.5:
            trend, arrow = "FALLING", "v"
        else:
            trend, arrow = "STEADY", "="

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

@app.route("/api/price")
def api_price():
    data = get_price_data()
    return jsonify(data)

@app.route("/check-price")
def check_price():
    result = check_and_notify()
    return result

@app.route("/ping")
def ping():
    return "OK"

@app.route("/")
def home():
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
.notify-card{background:linear-gradient(135deg,#1e3a5f,#1e293b);border-radius:16px;padding:25px;text-align:center;margin-bottom:20px;border:1px solid #334155}
.notify-card h2{font-size:1.3em;margin-bottom:8px}
.notify-card p{color:#94a3b8;margin-bottom:16px;font-size:0.95em}
.steps{text-align:left;max-width:350px;margin:0 auto 16px}
.steps div{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:0.95em}
.step-num{background:#22c55e;color:#0f172a;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8em;flex-shrink:0}
.btn{display:inline-block;background:#22c55e;color:#0f172a;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:1em;transition:transform 0.1s}
.btn:hover{transform:scale(1.05)}
.check-btn{background:#3b82f6;color:white;border:none;padding:10px 20px;border-radius:8px;font-size:0.95em;font-weight:600;cursor:pointer;margin-top:12px;transition:transform 0.1s}
.check-btn:hover{transform:scale(1.05)}
.footer{text-align:center;padding:20px;color:#475569;font-size:0.85em}
.loading{color:#94a3b8;padding:40px;text-align:center}
.updated{color:#64748b;font-size:0.8em;margin-top:8px}
@media(max-width:480px){.hero h1{font-size:1.6em}.price-big{font-size:3em}}
</style>
</head>
<body>
<div class="hero">
<h1>&#9889; <span>EV Charge</span> Notify</h1>
<p>Real-time ComEd pricing for EV owners</p>
</div>
<div class="dashboard">
<div class="price-card" id="priceCard">
<div class="loading">Loading live price...</div>
</div>
<div class="chart-card" id="chartCard">
<h3>Last 60 Minutes</h3>
<div class="loading">Loading chart...</div>
</div>
<div class="notify-card">
<h2>&#128276; Get Free Alerts</h2>
<p>Get push notifications when it's a good time to charge</p>
<div class="steps">
<div><span class="step-num">1</span> Install the <b>ntfy</b> app (free)</div>
<div><span class="step-num">2</span> Subscribe to topic: <b>podrid-ev-charger</b></div>
<div><span class="step-num">3</span> Get smart alerts every afternoon!</div>
</div>
<a class="btn" href="https://ntfy.sh/podrid-ev-charger" target="_blank">Open in ntfy</a>
<br>
<button class="check-btn" onclick="sendCheck()">&#128225; Send Price Check Now</button>
<div id="checkResult" style="margin-top:8px;font-size:0.85em;color:#94a3b8"></div>
</div>
<div class="footer">
Built by the Podrid family &#9889; Powered by ComEd Hourly Pricing
</div>
</div>
<script>
async function loadPrice(){
try{
const r=await fetch('/api/price');
const d=await r.json();
if(d.error){document.getElementById('priceCard').innerHTML='<div class="loading">Could not load price</div>';return}
document.getElementById('priceCard').innerHTML=
'<div class="price-big" style="color:'+d.color+'">'+d.price.toFixed(1)+'<span class="price-unit"> c/kWh</span></div>'+
'<div class="trend-badge" style="background:'+d.color+'22;color:'+d.color+'">'+d.arrow+' '+d.trend+'</div>'+
'<div class="advice-text">'+d.emoji+' '+d.advice+'</div>'+
'<div class="updated">Updated '+d.time+'</div>';
if(d.recent&&d.recent.length){
const prices=d.recent.map(r=>r.price).reverse();
const max=Math.max(...prices,1);
let bars='';let labels='';
for(let i=0;i<prices.length;i++){
const h=Math.max((prices[i]/max)*100,4);
const c=prices[i]<3?'#22c55e':prices[i]<6?'#3b82f6':prices[i]<10?'#f59e0b':'#ef4444';
bars+='<div class="bar" style="height:'+h+'%;background:'+c+'" data-label="'+prices[i].toFixed(1)+'c"></div>';
labels+='<span>'+(i%3===0?(prices.length-i)*5+'m':'')+'</span>';
}
document.getElementById('chartCard').innerHTML='<h3>Last 60 Minutes</h3><div class="bar-chart">'+bars+'</div><div class="time-labels">'+labels+'</div>';
}
}catch(e){document.getElementById('priceCard').innerHTML='<div class="loading">Could not load price</div>'}}
async function sendCheck(){
const el=document.getElementById('checkResult');
el.textContent='Sending...';
try{const r=await fetch('/check-price');const t=await r.text();el.textContent=t==='OK'?'Notification sent!':'Error: '+t}
catch(e){el.textContent='Failed to send'}}
loadPrice();
setInterval(loadPrice,300000);
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
