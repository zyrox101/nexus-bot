import time
from watcher import Bot

bot = Bot(test_mode=False)

def run_worker():
    print("🚀 Worker started - trading bot is live")

    while True:
        try:
            if bot.is_running:
                bot.get_balance()

                for market in bot.STABLE_MARKETS:
                    bot.process_market(market)

            time.sleep(10)

        except Exception as e:
            print("❌ Worker error:", e)
            time.sleep(5)


if __name__ == "__main__":
    run_worker()

