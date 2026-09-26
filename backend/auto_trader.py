import asyncio
import logging
from datetime import datetime
from backend.data_collector import DataCollector
from backend.agent_core import TradingAgentCore
from backend.portfolio import PortfolioManager

logger = logging.getLogger(__name__)

class AutoTrader:
    def __init__(self, collector: DataCollector, agent_core: TradingAgentCore, portfolio: PortfolioManager):
        self.collector = collector
        self.agent_core = agent_core
        self.portfolio = portfolio
        self.is_running = False
        self.tickers_to_monitor = ["NIFTY", "BANKNIFTY", "CL=F"] # Added Crude Oil
        self.task = None
        self.logs = [f"{datetime.now().strftime('%H:%M:%S')} - System initialized."]

    def _add_log(self, msg):
        self.logs.append(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")
        if len(self.logs) > 50:
            self.logs.pop(0)

    async def start(self):
        if not self.is_running:
            self.is_running = True
            self.task = asyncio.create_task(self._trade_loop())
            return {"status": "started", "message": "Autonomous trading engine started."}
        return {"status": "already_running", "message": "Already running."}

    def stop(self):
        if self.is_running:
            self.is_running = False
            if self.task:
                self.task.cancel()
            return {"status": "stopped", "message": "Autonomous trading engine stopped."}
        return {"status": "already_stopped", "message": "Not running."}

    def status(self):
        stats = self.portfolio.data.get("daily_stats", {})
        return {
            "is_running": self.is_running,
            "tickers": self.tickers_to_monitor,
            "daily_stats": stats
        }

    async def _trade_loop(self):
        while self.is_running:
            try:
                await self._evaluate_markets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-trader error: {e}")
                
            # Sleep for 5 minutes before next scan
            await asyncio.sleep(300)

    async def _evaluate_markets(self):
        stats = self.portfolio.data.get("daily_stats", {})
        
        # Risk Management Limits
        if stats.get("trades_taken", 0) >= 4:
            self._add_log("Daily trade limit reached (4). Stopping.")
            self.stop()
            return
            
        if stats.get("sl_hits", 0) >= 2:
            self._add_log("Daily Stop Loss limit hit (2). Stopping.")
            self.stop()
            return

        if stats.get("target_hits", 0) >= 2:
            self._add_log("Daily Target hits achieved (2). Stopping to preserve RRR.")
            self.stop()
            return

        # Check existing positions for SL or Targets
        current_prices = {}
        for pos in self.portfolio.data.get("positions", []):
            ticker = pos["ticker"]
            if ticker not in current_prices:
                df = self.collector.fetch_market_data(ticker, period="1d", interval="1m")
                if not df.empty:
                    current_prices[ticker] = float(df.iloc[-1]['Close'])
            
            cp = current_prices.get(ticker)
            if cp:
                # Basic mock logic for auto-exit based on arbitrary 10% bounds if not properly set
                # In a real bot, we'd store the targets and SLs in the position dict!
                entry = pos["entry_price"]
                qty = pos["qty"]
                instrument = pos["instrument"]
                strike = pos["strike"]
                
                # If we don't have exact targets saved, we approximate for the simulator
                if cp <= entry * 0.90:  # Hit SL (10% down)
                    self._add_log(f"SL HIT for {ticker}! Auto-exiting position.")
                    self.portfolio.execute_trade(ticker, "SELL", qty, cp, instrument, strike, is_sl=True)
                elif cp >= entry * 1.20: # Hit Target (20% up)
                    self._add_log(f"TARGET HIT for {ticker}! Auto-exiting position.")
                    self.portfolio.execute_trade(ticker, "SELL", qty, cp, instrument, strike, is_target=True)
                    
        # Look for new setups if we have capacity
        if len(self.portfolio.data.get("positions", [])) >= 3:
            return # Don't open more than 3 at once
            
        for ticker in self.tickers_to_monitor:
            # 1. Fetch data
            market_data = self.collector.get_comprehensive_data(ticker)
            if "error" in market_data:
                continue
                
            if ticker in ["NIFTY", "BANKNIFTY"]:
                market_data["option_chain"] = self.collector.get_option_chain(ticker)
                
            # 2. Analyze
            analysis = self.agent_core.run_analysis(market_data)
            if "error" in analysis:
                continue
                
            lead_decision = analysis.get("lead_verification", {})
            if lead_decision.get("approved") and lead_decision.get("final_action") in ["BUY", "SELL"]:
                
                # Check bounds again in case of async delays
                stats = self.portfolio.data.get("daily_stats", {})
                if stats.get("trades_taken", 0) >= 4: break

                action = lead_decision["final_action"]
                instrument = lead_decision.get("instrument_type", "EQ")
                strike = lead_decision.get("final_strike", "None")
                
                entry_range = lead_decision.get("final_entry_range", "0")
                try:
                    price = float(entry_range.split('-')[0].strip())
                except:
                    price = market_data.get("price_details", {}).get("close", 0)
                    
                if price <= 0: continue
                
                qty = 25 if instrument == "Options" and "NIFTY" in ticker else (100 if "CL=F" in ticker else 10)
                
                # Save targets in position metadata (we would update portfolio.py to store these ideally)
                self._add_log(f"EXECUTING {action} on {ticker} ({instrument}) at {price}")
                self.portfolio.execute_trade(ticker, action, qty, price, instrument=instrument, strike=strike)
