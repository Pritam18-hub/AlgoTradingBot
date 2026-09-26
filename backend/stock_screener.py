import yfinance as yf
import pandas as pd
import pandas_ta as ta
from typing import List, Dict

# Predefined basket of high-growth potential Indian stocks (Mid/Small Cap)
BASKET = [
    "DIXON.NS", "POLYCAB.NS", "KPITTECH.NS", "TATAELXSI.NS", "RVNL.NS", 
    "IRFC.NS", "MAZDOCK.NS", "HAL.NS", "BSE.NS", "CDSL.NS", "ANGELONE.NS",
    "ZENTEC.NS", "SUZLON.NS", "TRENT.NS", "VARROC.NS", "JINDALSTEL.NS",
    "CGPOWER.NS", "KALYANKJIL.NS", "TRIDENT.NS", "HAPPSTMNDS.NS"
]

class MultiBaggerScreener:
    def __init__(self, tickers: List[str] = BASKET):
        self.tickers = tickers

    def run_screener(self) -> List[Dict]:
        """
        Executes a dual-funnel screener: Fundamental + Technical.
        Returns a ranked list of stocks that pass the criteria.
        """
        results = []
        
        # 1. Fetch Technical Data via batch download
        # Download 1 year of daily data to get 200 EMA
        df_batch = yf.download(self.tickers, period="1y", interval="1d", group_by="ticker", progress=False)
        
        for ticker in self.tickers:
            try:
                # Get technical data for the specific ticker
                if len(self.tickers) > 1:
                    df = df_batch[ticker].copy()
                else:
                    df = df_batch.copy()
                    
                df.dropna(inplace=True)
                if len(df) < 200:
                    continue # Need at least 200 days for 200 EMA
                    
                # Calculate Technicals
                df.ta.ema(length=50, append=True)
                df.ta.ema(length=200, append=True)
                df.ta.rsi(length=14, append=True)
                
                last_row = df.iloc[-1]
                close = last_row['Close']
                ema_50 = last_row['EMA_50']
                ema_200 = last_row['EMA_200']
                rsi = last_row['RSI_14']
                
                # Technical Filter: Stage 2 Uptrend (Price > 50 EMA > 200 EMA)
                if not (close > ema_50 and ema_50 > ema_200):
                    continue # Fails technical stage 2
                    
                # Technical Filter: Not massively overbought
                if rsi > 85:
                    continue
                    
                # 2. Fetch Fundamentals for passed stocks
                info = yf.Ticker(ticker).info
                
                # Extract metrics (handle missing gracefully)
                roe = info.get("returnOnEquity", 0) or 0
                de = info.get("debtToEquity", 100) or 100  # Default to high debt if missing
                peg = info.get("pegRatio", 5) or 5
                rev_growth = info.get("revenueGrowth", 0) or 0
                earn_growth = info.get("earningsGrowth", 0) or 0
                promoter_holding = info.get("heldPercentInsiders", 0) or 0
                
                # Format to percentages
                roe_pct = roe * 100
                promoter_pct = promoter_holding * 100
                rev_growth_pct = rev_growth * 100
                earn_growth_pct = earn_growth * 100
                
                # Convert D/E from percentage to ratio if necessary (yfinance sometimes gives 40 instead of 0.4)
                de_ratio = de / 100 if de > 5 else de
                
                # Fundamental Filters
                passed = True
                reasons = []
                
                if roe_pct < 15: passed = False; reasons.append("Low ROE")
                if de_ratio > 0.5: passed = False; reasons.append("High Debt")
                if peg > 1.5: passed = False; reasons.append("High PEG (Overvalued)")
                if rev_growth_pct < 10: passed = False; reasons.append("Low Revenue Growth")
                if promoter_pct < 20: passed = False; reasons.append("Low Promoter Holding")
                
                if passed:
                    # Calculate a simple "Multi-Bagger Score" out of 100
                    score = 50 
                    if roe_pct >= 20: score += 10
                    if de_ratio <= 0.2: score += 10
                    if earn_growth_pct > 20: score += 15
                    if rsi < 60: score += 15 # Good entry point
                    
                    results.append({
                        "ticker": ticker.replace(".NS", ""),
                        "score": score,
                        "close": round(close, 2),
                        "roe_pct": round(roe_pct, 2),
                        "debt_to_equity": round(de_ratio, 2),
                        "peg_ratio": round(peg, 2),
                        "revenue_growth_pct": round(rev_growth_pct, 2),
                        "earnings_growth_pct": round(earn_growth_pct, 2),
                        "promoter_holding_pct": round(promoter_pct, 2),
                        "technicals": "Stage 2 Uptrend (Price > 50 EMA > 200 EMA)",
                    })
            except Exception as e:
                print(f"Screener error on {ticker}: {e}")
                
        # Sort by highest score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

screener = MultiBaggerScreener()
