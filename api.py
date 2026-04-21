from flask import Flask, jsonify, render_template
import threading
import os
from watcher import Bot

app = Flask(__name__)

# ---------------- BOT ----------------
bot = Bot(test_mode=False)
bot_thread = None


def run_bot():
    print("🚀 Bot thread started")
    bot.start()


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


# ---------------- START BOT ----------------
@app.route("/start", methods=["POST"])
def start_bot():
    global bot_thread

    if bot.is_running:
        return jsonify({"status": "already running"})

    bot.is_running = True
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    return jsonify({"status": "bot started"})


# ---------------- STOP BOT ----------------
@app.route("/stop", methods=["POST"])
def stop_bot():
    bot.stop()
    return jsonify({"status": "bot stopped"})


# ---------------- AUTO START (SAFE) ----------------
def auto_start():
    global bot_thread

    if not bot.is_running:
        bot.is_running = True
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        print("🚀 Bot auto-started")


auto_start()


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
