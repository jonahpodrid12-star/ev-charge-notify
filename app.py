from flask import Flask
import requests
from datetime import datetime

app = Flask(__name__)

NTFY_TOPIC = "podrid-ev-charger"


def check_and_notify():
    url_current = "https://hourlypricing.comed.com/api?type=currenthouraverage"
    current_data = requests.get(url_current).json()
    current_price = float(current_data[0]["price"])

    url_recent = "https://hourlypricing.comed.com/api?type=5minutefeed"
    recent_data = requests.get(url_recent).json()

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
        else:
            advice = "GREAT time to plug in! Price is low."
    elif current_price < 6:
        if trend == "FALLING":
            advice = "Price is OK and dropping -- could wait a bit for even cheaper."
        else:
            advice = "Price is OK. Fine to charge."
    elif current_price < 10:
        if trend == "FALLING":
            advice = "Price is high but coming down -- wait a little longer."
        else:
            advice = "Price is HIGH. Wait for it to drop."
    else:
        advice = "Price is VERY HIGH. Definitely wait!"

    now = datetime.now().strftime("%I:%M %p")
    message = f"ComEd {now}: {current_price:.1f}c/kWh {arrow}{trend}\n{advice}"
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message)
    return message


@app.route("/check-price")
def check_price():
    message = check_and_notify()
    return f"OK - sent: {message}"


@app.route("/")
def home():
    return "EV Charge Notify is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
