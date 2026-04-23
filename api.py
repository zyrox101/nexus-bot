from flask import Flask, jsonify
import threading

from watcher import Bot
from trade_logger import read_trades

from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= BOT INSTANCE =================
bot = Bot(test_mode=True)

# ================= START BOT THREAD =================
def start_bot():
    print("🚀 Starting bot thread...")

    # FIX: ensure correct method is used
    if hasattr(bot, "start"):
        bot.start()
    else:
        bot.run()

threading.Thread(target=start_bot, daemon=True).start()


# ================= ROUTES =================

@app.route("/")
def home():
    return "Nexus Bot is running 🚀"


@app.route("/status")
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal,
        "balance": bot.balance,
        "last_heartbeat": bot.last_heartbeat
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "alive",
        "bot_running": bot.is_running
    })


@app.route("/balance")
def balance():
    return jsonify({
        "balance": bot.balance,
        "test_mode": bot.test_mode
    })


# ================= FIXED TRADES ENDPOINT =================
@app.route("/trades")
def trades():
    return jsonify(read_trades())


# ================= RUN LOCAL =================
if __name__ == "__main__":
    app.run(debug=True)
