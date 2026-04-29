from flask import Flask, jsonify
import threading

from watcher import Bot
from trade_logger import read_trades

from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ================= BOT INSTANCE =================
bot = Bot(test_mode=False)
bot_thread = None


# ================= START BOT THREAD =================
def start_bot():
    global bot_thread

    if bot.is_running:
        return "Bot already running"

    print("🚀 Starting bot thread...")
    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()


# ================= STOP BOT =================
def stop_bot():
    if bot.is_running:
        bot.stop()
        return "Bot stopped"
    return "Bot already stopped"


# ================= ROUTES =================

@app.route("/")
def home():
    return "Nexus Bot is running 🚀"


# ================= STATUS =================
@app.route("/status")
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal,
        "balance": round(bot.balance, 2),
        "last_heartbeat": bot.last_heartbeat
    })


# ================= BALANCE =================
@app.route("/balance")
def balance():
    return jsonify({
        "balance": round(bot.balance, 2),
        "test_mode": bot.test_mode
    })


# ================= TRADES =================
@app.route("/trades")
def trades():
    try:
        data = read_trades()
        return jsonify(data if data else [])
    except:
        return jsonify([])


# ================= PERFORMANCE =================
@app.route("/performance")
def performance():
    return jsonify(bot.tracker.summary())


# ================= ANALYTICS =================
@app.route("/analytics")
def analytics():
    return jsonify(bot.tracker.analytics())


# ================= BOT CONTROL =================
@app.route("/start", methods=["POST"])
def start():
    start_bot()
    return jsonify({"status": "started"})


@app.route("/stop", methods=["POST"])
def stop():
    msg = stop_bot()
    return jsonify({"status": msg})


@app.route("/restart", methods=["POST"])
def restart():
    stop_bot()
    start_bot()
    return jsonify({"status": "restarted"})


# ================= HEALTH =================
@app.route("/health")
def health():
    return jsonify({
        "status": "alive",
        "bot_running": bot.is_running
    })


# ================= AUTO START =================
start_bot()


# ================= RUN LOCAL =================
if __name__ == "__main__":
    app.run(debug=True)
