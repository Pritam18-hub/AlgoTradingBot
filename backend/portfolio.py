import os
import json
from datetime import datetime
from filelock import FileLock

# Using /tmp or environment variable if running in Vercel/Railway
data_dir = os.environ.get("DATA_DIR", os.path.dirname(__file__))
PORTFOLIO_FILE = os.path.join(data_dir, "portfolio.json")
LOCK_FILE = PORTFOLIO_FILE + ".lock"

class PortfolioManager:
    def __init__(self, initial_balance: float = 500000.0): # Upgraded starting balance to 5 lakh
        self.initial_balance = initial_balance
        self.lock = FileLock(LOCK_FILE, timeout=5)
        self.load_portfolio()

    def _get_default_state(self):
        return {
            "balance": self.initial_balance,
            "equity": self.initial_balance,
            "positions": [],
            "history": []
        }

    def load_portfolio(self):
        with self.lock:
            if os.path.exists(PORTFOLIO_FILE):
                try:
                    with open(PORTFOLIO_FILE, "r") as f:
                        self.data = json.load(f)
                except Exception as e:
                    print(f"Error loading portfolio.json, resetting: {e}")
                    self.data = self._get_default_state()
            else:
                self.data = self._get_default_state()
                self._save_raw()

    def save_portfolio(self):
        with self.lock:
            self._save_raw()
            
    def _save_raw(self):
        try:
            with open(PORTFOLIO_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving portfolio: {e}")

    def reset_portfolio(self):
        with self.lock:
            self.data = self._get_default_state()
            self._save_raw()

    def get_portfolio_summary(self, current_prices: dict = None) -> dict:
        if current_prices is None:
            current_prices = {}

        total_position_value = 0.0
        open_positions = []
        
        # Win rate calc
        history = self.data.get("history", [])
        wins = sum(1 for trade in history if trade.get("pnl", 0) > 0)
        win_rate = round((wins / len(history)) * 100, 2) if history else 0.0

        with self.lock:
            for pos in self.data["positions"]:
                ticker = pos["ticker"]
                qty = pos["qty"]
                entry_price = pos["entry_price"]
                instrument = pos["instrument"]
                
                # Fetch latest price
                current_price = current_prices.get(ticker, entry_price)

                # Calculate P&L using premium differences
                pnl = (current_price - entry_price) * qty
                current_value = current_price * qty
                
                # If short selling options (Credit logic)
                if pos.get("is_short", False):
                    pnl = (entry_price - current_price) * qty
                    current_value = (entry_price * 2 - current_price) * qty

                pnl_pct = (pnl / (entry_price * qty)) * 100 if entry_price > 0 else 0.0
                total_position_value += current_value

                pos_data = pos.copy()
                pos_data.update({
                    "current_price": current_price,
                    "market_value": round(current_value, 2),
                    "unrealized_pnl": round(pnl, 2),
                    "unrealized_pnl_pct": round(pnl_pct, 2)
                })
                open_positions.append(pos_data)

            equity = self.data["balance"] + total_position_value
            self.data["equity"] = equity
            
            return {
                "balance": round(self.data["balance"], 2),
                "equity": round(equity, 2),
                "total_pnl": round(equity - self.initial_balance, 2),
                "total_pnl_pct": round(((equity / self.initial_balance) - 1) * 100, 2),
                "win_rate": win_rate,
                "total_trades": len(history),
                "positions": open_positions,
                "history": history[-10:] # last 10
            }

    def execute_trade(self, ticker: str, action: str, qty: int, price: float, instrument="EQ", strike="None", is_short=False) -> dict:
        BROKERAGE = 20.0
        STT_RATE = 0.001 # approx
        
        with self.lock:
            if action.upper() == "BUY":
                if len(self.data["positions"]) >= 5:
                    return {"success": False, "message": "Max 5 open positions allowed for risk management."}
                    
                cost = price * qty
                if self.data["balance"] < cost + BROKERAGE:
                    return {"success": False, "message": "Insufficient funds."}

                # Check if position exists
                existing = next((p for p in self.data["positions"] if p["ticker"] == ticker and p["instrument"] == instrument and p["strike"] == strike), None)
                
                if existing:
                    # Average down
                    total_qty = existing["qty"] + qty
                    avg_price = ((existing["entry_price"] * existing["qty"]) + cost) / total_qty
                    existing["entry_price"] = round(avg_price, 2)
                    existing["qty"] = total_qty
                else:
                    self.data["positions"].append({
                        "ticker": ticker,
                        "instrument": instrument,
                        "strike": strike,
                        "qty": qty,
                        "entry_price": price,
                        "is_short": is_short,
                        "timestamp": datetime.now().isoformat()
                    })

                self.data["balance"] -= (cost + BROKERAGE)
                self._save_raw()
                return {"success": True, "message": f"Bought {qty} of {ticker} at {price}"}

            elif action.upper() == "SELL":
                existing = next((p for p in self.data["positions"] if p["ticker"] == ticker and p["instrument"] == instrument and p["strike"] == strike), None)
                
                if not existing or existing["qty"] < qty:
                    return {"success": False, "message": "Insufficient quantity to sell."}

                entry = existing["entry_price"]
                
                if existing.get("is_short", False):
                    pnl = (entry - price) * qty
                else:
                    pnl = (price - entry) * qty
                    
                stt_cost = (price * qty) * STT_RATE
                proceeds = (price * qty) if not existing.get("is_short", False) else (entry * qty + pnl)
                net_pnl = pnl - BROKERAGE - stt_cost
                
                # Update positions
                if existing["qty"] == qty:
                    self.data["positions"].remove(existing)
                else:
                    existing["qty"] -= qty

                # Update history
                self.data["history"].append({
                    "ticker": ticker,
                    "instrument": instrument,
                    "strike": strike,
                    "qty": qty,
                    "entry_price": entry,
                    "exit_price": price,
                    "pnl": round(net_pnl, 2),
                    "pnl_pct": round((net_pnl / (entry * qty)) * 100, 2) if entry > 0 else 0.0,
                    "entry_time": existing["timestamp"],
                    "exit_time": datetime.now().isoformat()
                })

                self.data["balance"] += (proceeds - BROKERAGE - stt_cost)
                self._save_raw()
                return {"success": True, "message": f"Sold {qty} of {ticker} at {price}. PnL: ₹{net_pnl:.2f}"}

        return {"success": False, "message": "Unknown action."}
