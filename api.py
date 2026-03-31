from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
from watcher import Bot
import threading

app = Flask(__name__)
CORS(app)

# Initialize bot
bot = Bot(test_mode=False)

# Run bot in background thread
def run_bot():
    bot.start()

thread = threading.Thread(target=run_bot, daemon=True)
thread.start()

# ---------------- WEB PAGE ----------------
@app.route('/')
def home():
    return render_template_string(f"""
    <h1>🚀 Nexus Trading Bot</h1>

    <p><b>Status:</b> {"Running" if bot.is_running else "Stopped"}</p>
    <p><b>Balance:</b> ${bot.balance}</p>
    <p><b>Signal:</b> {bot.current_signal}</p>

    <h2>Controls</h2>
    <form action="/start" method="post">
        <button type="submit">Start Bot</button>
    </form>

    <form action="/stop" method="post">
        <button type="submit">Stop Bot</button>
    </form>

    <h2>Trades</h2>
    <pre>{bot.trade_history}</pre>
    """)

# ---------------- API ENDPOINTS ----------------

@app.route('/status')
def status():
    return jsonify({
        "running": bot.is_running,
        "current_signal": bot.current_signal
    })

@app.route('/balance')
def balance():
    return jsonify({
        "balance": bot.balance
    })

@app.route('/trades')
def trades():
    return jsonify(bot.trade_history)

# ---------------- CONTROLS ----------------

@app.route('/start', methods=['POST'])
def start_bot():
    if not bot.is_running:
        threading.Thread(target=bot.start, daemon=True).start()
    return jsonify({"message": "Bot started"})

@app.route('/stop', methods=['POST'])
def stop_bot():
    bot.stop()
    return jsonify({"message": "Bot stopped"})

# ---------------- IMPORTANT ----------------
# DO NOT USE app.run() ON PYTHONANYWHERE

