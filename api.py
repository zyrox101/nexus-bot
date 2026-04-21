from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from watcher import Bot
import threading
import os

app = Flask(__name__)
CORS(app)

# ---------------- BOT ----------------
bot = Bot(test_mode=False)
bot_thread = None


def run_bot():
    bot.start()


# ---------------- DASHBOARD ----------------
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- API ----------------
@app.route('/status')
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal
    })


@app.route('/balance')
def balance():
    return jsonify({
        "balance": round(bot.balance, 2)
    })


@app.route('/trades')
def trades():
    return jsonify(bot.trade_history[-10:][::-1])


# ---------------- CONTROLS ----------------
@app.route('/start', methods=['POST'])
def start_bot():
    global bot_thread

    if not bot.is_running:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

    return jsonify({"message": "Bot started"})


@app.route('/stop', methods=['POST'])
def stop_bot():
    bot.stop()
    return jsonify({"message": "Bot stopped"})


# ---------------- AUTO START (IMPORTANT) ----------------
def auto_start():
    global bot_thread
    if not bot.is_running:
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        print("🚀 Bot auto-started")


auto_start()


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


