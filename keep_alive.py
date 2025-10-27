# -------------------------------
# PowerPointBreak Bot Keep Alive System (for Replit 24/7)
# -------------------------------

from flask import Flask
from threading import Thread
import logging

# Flask app তৈরি
app = Flask('PowerPointBreak')

# Flask log কমানোর জন্য
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return (
        "<center>"
        "<h2>✅ PowerPointBreak Bot 24/7 Active!</h2>"
        "<p>Flask keep_alive system running successfully 🚀</p>"
        "<hr>"
        "<p>🔹 Bot Owner: <b>@MinexxProo</b></p>"
        "<p>🔹 Channel: <b>@PowerPointBreak</b></p>"
        "<p>🔹 Group: <b>@PowerPointBreakConversion</b></p>"
        "<p>🔹 Hosted on Replit 🌐</p>"
        "</center>"
    )

def run():
    # 0.0.0.0 → public access (Replit এর জন্য দরকার)
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """এটা call করলে Flask সার্ভার ব্যাকগ্রাউন্ডে চালু থাকবে"""
    t = Thread(target=run)
    t.start()
