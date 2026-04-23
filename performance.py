class PerformanceTracker:
    def __init__(self):
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.total_profit = 0.0

    # ✅ FIX ADDED (prevents bot crash)
    def get_initial_balance(self):
        return 1000.0

    def record_trade(self, profit):
        self.total_trades += 1
        self.total_profit += profit

        if profit > 0:
            self.wins += 1
        else:
            self.losses += 1

    def win_rate(self):
        if self.total_trades == 0:
            return 0
        return (self.wins / self.total_trades) * 100

    def summary(self):
        return {
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "total_profit": round(self.total_profit, 2),
            "win_rate": round(self.win_rate(), 2)
        }
