from flask import Flask, jsonify, render_template
import threading
import os
import time

from watcher import Bot

app = Flask(__name__)

# ================= BOT INSTANCE =================
bot = Bot(test_mode=False)

bot_thread = None
bot_lock = threading.Lock()

# ================= LIVE LOG STORE =================
live_logs = []


def log_event(event):
    global live_logs

    live_logs.append({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "event": event
    })

    if len(live_logs) > 100:
        live_logs = live_logs[-100:]


# ================= BOT LOOP =================
def run_bot():
    log_event("BOT_THREAD_STARTED")

    while bot.is_running:
        try:
            bot.get_balance()
            log_event(f"BALANCE_UPDATE: {bot.balance}")

            # FIX: correct method name from watcher.py
            for market in bot.STABLE_MARKETS:
                bot.process(market)

            log_event(f"SIGNAL: {bot.current_signal}")

            time.sleep(10)

        except Exception as e:
            log_event(f"ERROR: {str(e)}")


# ================= HOME =================
@app.route('/')
def home():
    return jsonify({
        "message": "NEXUS BOT RUNNING",
        "status": bot.is_running
    }) 



# ================= STATUS =================
@app.route('/status')
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal
    })


# ================= BALANCE =================
@app.route('/balance')
def balance():
    return jsonify({
        "balance": round(bot.balance, 2)
    })


# ================= TRADES =================
@app.route('/trades')
def trades():
    return jsonify(bot.trade_history[-10:][::-1])


# ================= LOGS =================
@app.route('/logs')
def logs():
    return jsonify(live_logs[-50:][::-1])


# ================= START BOT =================
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


# ================= STOP BOT =================
@app.route("/start", methods=["GET", "POST"])
def stop_bot():
    with bot_lock:
        if not bot.is_running:
            return jsonify({"status": "already stopped"})

        bot.stop()
        log_event("BOT_STOPPED")

    return jsonify({"status": "bot stopped"})


# ================= SAFE START CONTROL =================
def safe_auto_start():
    """
    Only start if explicitly enabled via env variable
    Prevents Render double-instance issues
    """
    if os.environ.get("AUTO_START", "false").lower() != "true":
        print("AUTO START DISABLED")
        return

    global bot_thread

    with bot_lock:
        if not bot.is_running:
            bot.is_running = True

            bot_thread = threading.Thread(target=run_bot)
            bot_thread.daemon = True
            bot_thread.start()

            log_event("AUTO_START_TRIGGERED")
            print("🚀 Bot auto-started")


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
