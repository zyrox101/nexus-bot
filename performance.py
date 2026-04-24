class PerformanceTracker:
    def __init__(self):
        self.initial_balance = 1000.0
        self.current_balance = 1000.0

        self.total_trades = 0
        self.wins = 0
        self.losses = 0

        self.total_profit = 0.0

        # Track account growth over time (for analytics later)
        self.equity_curve = []

    # ================= INITIAL =================
    def get_initial_balance(self):
        return self.initial_balance

    # ================= RECORD TRADE =================
    def record_trade(self, profit):
        self.total_trades += 1
        self.total_profit += profit

        # Update balance
        self.current_balance += profit

        # Win/Loss tracking
        if profit > 0:
            self.wins += 1
        elif profit < 0:
            self.losses += 1

        # Save equity snapshot
        self.equity_curve.append({
            "balance": round(self.current_balance, 2),
            "profit": round(profit, 4),
            "trade_number": self.total_trades
        })

    # ================= WIN RATE =================
    def win_rate(self):
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100

    # ================= PERFORMANCE SUMMARY =================
    def summary(self):
        return {
            "initial_balance": round(self.initial_balance, 2),
            "current_balance": round(self.current_balance, 2),
            "total_profit": round(self.total_profit, 2),

            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate(), 2)
        }

    # ================= ANALYTICS =================
    def analytics(self):
        return {
            "equity_curve": self.equity_curve,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate(), 2)
        }

