from flask import Flask, jsonify, render_template
import threading
import os
import time

from watcher import Bot

app = Flask(__name__)

# ---------------- BOT INSTANCE ----------------
bot = Bot(test_mode=False)

bot_thread = None
bot_lock = threading.Lock()

# ---------------- LIVE LOG STORE ----------------
live_logs = []


def log_event(event):
    """Store live bot events for UI"""
    global live_logs

    live_logs.append({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event
    })

    # keep only last 100 logs
    if len(live_logs) > 100:
        live_logs = live_logs[-100:]


# ---------------- WRAPPED BOT LOOP ----------------
def run_bot():
    log_event("BOT_THREAD_STARTED")

    while bot.is_running:
        try:
            bot.get_balance()
            log_event(f"BALANCE_UPDATE: {bot.balance}")

            for market in bot.STABLE_MARKETS:
                bot.process_market(market)

            log_event(f"SIGNAL: {bot.current_signal}")

            time.sleep(10)

        except Exception as e:
            log_event(f"ERROR: {str(e)}")


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- STATUS ----------------
@app.route('/status')
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal
    })


# ---------------- BALANCE ----------------
@app.route('/balance')
def balance():
    return jsonify({
        "balance": round(bot.balance, 2)
    })


# ---------------- TRADES ----------------
@app.route('/trades')
def trades():
    return jsonify(bot.trade_history[-10:][::-1])


# ---------------- LIVE LOGS (NEW FIX) ----------------
@app.route('/logs')
def logs():
    return jsonify(live_logs[-50:][::-1])


# ---------------- START BOT (SAFE FIX) ----------------
@app.route("/start", methods=["POST"])
def start_bot():
    global bot_thread

    with bot_lock:
        if bot.is_running:
            return jsonify({"status": "already running"})

        bot.is_running = True

        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()

        log_event("BOT_STARTED")

    return jsonify({"status": "bot started"})


# ---------------- STOP BOT ----------------
@app.route("/stop", methods=["POST"])
def stop_bot():
    with bot_lock:
        bot.stop()
        log_event("BOT_STOPPED")

    return jsonify({"status": "bot stopped"})


# ---------------- AUTO START (SAFE FIX) ----------------
def auto_start():
    global bot_thread

    with bot_lock:
        if not bot.is_running:
            bot.is_running = True

            bot_thread = threading.Thread(target=run_bot)
            bot_thread.daemon = True
            bot_thread.start()

            log_event("AUTO_START_TRIGGERED")
            print("🚀 Bot auto-started")


auto_start()


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
