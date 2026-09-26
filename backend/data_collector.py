import pandas as pd
import pandas_ta as ta
import numpy as np
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import urllib.parse
from datetime import datetime
from backend.nse_scraper import nse_fetcher
import math

class DataCollector:
    def __init__(self):
        self.cache = {}

    def fetch_market_data(self, ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        ticker = ticker.upper().strip()
        if ticker in ["NIFTY", "NIFTY50", "NIFTY 50", "^NSEI"]:
            ticker = "^NSEI"
        elif ticker in ["BANKNIFTY", "BANK NIFTY", "^NSEBANK"]:
            ticker = "^NSEBANK"
        elif ticker in ["SENSEX", "^BSESN"]:
            ticker = "^BSESN"
        elif not ticker.endswith(".NS") and not ticker.endswith(".BO") and not ticker.startswith("^"):
            ticker = f"{ticker}.NS"

        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty:
                df = yf.download(ticker, period=period, interval=interval, progress=False)
            return df
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 20:
            return df

        df = df.copy()
        
        # EMAs & SMAs
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.sma(length=20, append=True)
        
        # Rename standard columns for consistency with frontend
        df.rename(columns={'EMA_9': 'EMA_9', 'EMA_21': 'EMA_21', 'EMA_50': 'EMA_50', 'EMA_200': 'EMA_200', 'SMA_20': 'SMA_20'}, inplace=True)

        # Standard Oscillators (RSI, MACD)
        df.ta.rsi(length=14, append=True)
        df.rename(columns={'RSI_14': 'RSI'}, inplace=True)
        
        macd = df.ta.macd(fast=12, slow=26, signal=9, append=False)
        if macd is not None:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']
            
        # Volatility (ATR, Bollinger Bands)
        df.ta.atr(length=14, append=True)
        df.rename(columns={'ATRr_14': 'ATR'}, inplace=True)
        
        bbands = df.ta.bbands(length=20, std=2, append=False)
        if bbands is not None:
            # Pandas-ta names can vary by version (e.g., 'BBL_20_2.0' vs 'BBL_20_2.0_2.0')
            bbl_col = next((c for c in bbands.columns if c.startswith('BBL')), None)
            bbm_col = next((c for c in bbands.columns if c.startswith('BBM')), None)
            bbu_col = next((c for c in bbands.columns if c.startswith('BBU')), None)
            if bbl_col: df['BB_Lower'] = bbands[bbl_col]
            if bbm_col: df['BB_Mid'] = bbands[bbm_col]
            if bbu_col: df['BB_Upper'] = bbands[bbu_col]

        # ADVANCED INDICATORS
        # SuperTrend (10,3)
        st = df.ta.supertrend(length=10, multiplier=3, append=False)
        if st is not None:
            col_supert = next((c for c in st.columns if c.startswith('SUPERT_')), None)
            col_supertd = next((c for c in st.columns if c.startswith('SUPERTd_')), None)
            if col_supert: df['SuperTrend'] = st[col_supert]
            if col_supertd: df['SuperTrend_Direction'] = st[col_supertd]
            
        # VWAP
        try:
            vwap = df.ta.vwap(append=False)
            if vwap is not None:
                col_vwap = next((c for c in vwap.columns if c.startswith('VWAP')), None)
                if col_vwap: df['VWAP'] = vwap[col_vwap]
        except Exception:
            pass # VWAP needs intraday data usually, fallback if fails

        # Stochastic RSI
        stochrsi = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=False)
        if stochrsi is not None:
            col_k = next((c for c in stochrsi.columns if c.startswith('STOCHRSIk')), None)
            col_d = next((c for c in stochrsi.columns if c.startswith('STOCHRSId')), None)
            if col_k: df['StochRSI_K'] = stochrsi[col_k]
            if col_d: df['StochRSI_D'] = stochrsi[col_d]

        # ADX
        adx = df.ta.adx(length=14, append=False)
        if adx is not None:
            col_adx = next((c for c in adx.columns if c.startswith('ADX')), None)
            col_dp = next((c for c in adx.columns if c.startswith('DMP')), None)
            col_dn = next((c for c in adx.columns if c.startswith('DMN')), None)
            if col_adx: df['ADX'] = adx[col_adx]
            if col_dp: df['DI+'] = adx[col_dp]
            if col_dn: df['DI-'] = adx[col_dn]
            
        # OBV
        try:
            df.ta.obv(append=True)
            if 'OBV' in df.columns:
                df.rename(columns={'OBV': 'OBV'}, inplace=True)
            else:
                col_obv = next((c for c in df.columns if c.startswith('OBV')), None)
                if col_obv: df.rename(columns={col_obv: 'OBV'}, inplace=True)
        except Exception:
            pass
            
        # Williams %R
        willr = df.ta.willr(length=14, append=False)
        if willr is not None:
            col_willr = next((c for c in willr.columns if c.startswith('WILLR')), None)
            if col_willr: df['WILLR'] = willr[col_willr]
            
        # CCI
        cci = df.ta.cci(length=20, append=False)
        if cci is not None:
            col_cci = next((c for c in cci.columns if c.startswith('CCI')), None)
            if col_cci: df['CCI'] = cci[col_cci]

        return df

    def detect_candlestick_patterns(self, df: pd.DataFrame) -> list:
        if df.empty or len(df) < 5:
            return []

        patterns = []
        for i in range(len(df) - 3, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1] if i > 0 else None
            prev2_row = df.iloc[i - 2] if i > 1 else None
            
            o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
            body = abs(c - o)
            candle_range = h - l
            if candle_range == 0: continue

            upper_shadow = h - max(o, c)
            lower_shadow = min(o, c) - l

            # Doji
            if body / candle_range < 0.1:
                patterns.append({"date": str(df.index[i])[:10], "pattern": "Doji", "sentiment": "Neutral", "description": "Indicates market indecision."})

            # Hammer / Shooting Star
            if lower_shadow >= 2 * body and upper_shadow / candle_range < 0.15:
                patterns.append({"date": str(df.index[i])[:10], "pattern": "Hammer / Pinbar", "sentiment": "Bullish", "description": "Bullish reversal."})
            elif upper_shadow >= 2 * body and lower_shadow / candle_range < 0.15:
                patterns.append({"date": str(df.index[i])[:10], "pattern": "Shooting Star", "sentiment": "Bearish", "description": "Bearish reversal."})

            # Multi-candle patterns
            if prev_row is not None:
                po, pc, ph, pl = prev_row['Open'], prev_row['Close'], prev_row['High'], prev_row['Low']
                prev_body = abs(pc - po)
                
                # Engulfing
                if pc < po and c > o and o <= pc and c >= po and body > prev_body:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Bullish Engulfing", "sentiment": "Bullish", "description": "Strong bullish reversal."})
                elif pc > po and c < o and o >= pc and c <= po and body > prev_body:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Bearish Engulfing", "sentiment": "Bearish", "description": "Strong bearish reversal."})
                
                # Piercing Line & Dark Cloud Cover
                if pc < po and c > o and o < pl and c > (po + pc)/2 and c < po:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Piercing Line", "sentiment": "Bullish", "description": "Bullish reversal pattern."})
                if pc > po and c < o and o > ph and c < (po + pc)/2 and c > po:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Dark Cloud Cover", "sentiment": "Bearish", "description": "Bearish reversal pattern."})
                    
                # Tweezer Top/Bottom
                if abs(ph - h) < (candle_range * 0.05) and pc > po and c < o:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Tweezer Top", "sentiment": "Bearish", "description": "Bearish reversal."})
                if abs(pl - l) < (candle_range * 0.05) and pc < po and c > o:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Tweezer Bottom", "sentiment": "Bullish", "description": "Bullish reversal."})

            # 3-Candle Patterns (Morning/Evening Star, Soldiers/Crows)
            if prev2_row is not None:
                p2o, p2c = prev2_row['Open'], prev2_row['Close']
                
                # Morning Star
                if p2c < p2o and abs(pc - po)/(ph - pl + 0.001) < 0.1 and c > o and c > (p2o + p2c)/2:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Morning Star", "sentiment": "Bullish", "description": "Major bullish reversal."})
                # Evening Star
                if p2c > p2o and abs(pc - po)/(ph - pl + 0.001) < 0.1 and c < o and c < (p2o + p2c)/2:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Evening Star", "sentiment": "Bearish", "description": "Major bearish reversal."})
                # Three White Soldiers
                if p2c > p2o and pc > po and c > o and p2c < pc < c:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Three White Soldiers", "sentiment": "Bullish", "description": "Strong bullish continuation."})
                # Three Black Crows
                if p2c < p2o and pc < po and c < o and p2c > pc > c:
                    patterns.append({"date": str(df.index[i])[:10], "pattern": "Three Black Crows", "sentiment": "Bearish", "description": "Strong bearish continuation."})

        return patterns

    def fetch_news_sentiment(self, ticker: str) -> list:
        # Same robust RSS + YF integration
        ticker_clean = ticker.replace('.NS', '').replace('^NSEI', 'NIFTY').replace('^NSEBANK', 'BANKNIFTY')
        news_list = []
        try:
            yf_news = yf.Ticker(ticker).news
            if yf_news:
                for item in yf_news[:5]:
                    news_list.append({
                        "title": item.get("title"), "publisher": item.get("publisher"), "link": item.get("link"),
                        "publish_time": datetime.fromtimestamp(item.get("providerPublishTime")).strftime('%Y-%m-%d %H:%M') if item.get("providerPublishTime") else "Recent"
                    })
        except: pass

        try:
            query = urllib.parse.quote(f"{ticker_clean} stock news india")
            url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'xml')
                for item in soup.find_all('item')[:5]:
                    title = item.find('title').text
                    if not any(n['title'] == title for n in news_list):
                        news_list.append({
                            "title": title, "publisher": item.find('source').text if item.find('source') else "Google News",
                            "link": item.find('link').text if item.find('link') else "",
                            "publish_time": item.find('pubDate').text[:16] if item.find('pubDate') else "Recent"
                        })
        except: pass
        return news_list[:6]

    def fetch_fii_dii_data(self) -> dict:
        result = {
            "date": datetime.today().strftime('%Y-%m-%d'),
            "fii_net_rs_cr": -345.20, "dii_net_rs_cr": 1280.45,
            "sentiment": "Neutral-Bullish (DII Buying offsetting FII Selling)",
            "source": "Estimated / Fallback Feed"
        }
        try:
            r = requests.get("https://www.moneycontrol.com/stocks/marketstats/fii_dii_activity/index.php", headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                table = soup.find('table', {'class': 'mctable1'})
                if table:
                    rows = table.find_all('tr')
                    if len(rows) > 1:
                        cols = rows[1].find_all('td')
                        if len(cols) >= 5:
                            fii = float(cols[3].text.replace(',', '').strip())
                            dii = float(cols[6].text.replace(',', '').strip())
                            sentiment = "Neutral"
                            if fii > 0 and dii > 0: sentiment = "Strongly Bullish"
                            elif fii < 0 and dii < 0: sentiment = "Strongly Bearish"
                            elif fii > 0 and dii < 0: sentiment = "Bullish"
                            elif fii < 0 and dii > 0: sentiment = "Neutral-Bullish"
                            result.update({"date": cols[0].text.strip(), "fii_net_rs_cr": fii, "dii_net_rs_cr": dii, "sentiment": sentiment, "source": "Moneycontrol Live Scrape"})
        except: pass
        return result

    def get_comprehensive_data(self, ticker: str) -> dict:
        df = self.fetch_market_data(ticker, period="6mo", interval="1d")
        if df.empty: return {"error": f"Failed to retrieve data for {ticker}"}

        df_ind = self.calculate_indicators(df)
        last_row = df_ind.iloc[-1]
        prev_row = df_ind.iloc[-2] if len(df_ind) > 1 else last_row

        candlesticks = self.detect_candlestick_patterns(df_ind)
        news = self.fetch_news_sentiment(ticker)
        fii_dii = self.fetch_fii_dii_data()

        fundamentals = {}
        if not ticker.startswith("^"):
            try:
                info = yf.Ticker(ticker).info
                fundamentals = {
                    "pe_ratio": info.get("trailingPE"), "forward_pe": info.get("forwardPE"),
                    "market_cap_cr": round(info.get("marketCap", 0) / 10000000, 2) if info.get("marketCap") else None,
                    "volume": int(last_row.get("Volume", info.get("volume", 0))),
                    "debt_to_equity": info.get("debtToEquity")
                }
            except: pass

        def safe_float(val): return float(round(val, 2)) if not pd.isna(val) else None
        
        tech_indicators = {
            "close": safe_float(last_row['Close']), "open": safe_float(last_row['Open']),
            "high": safe_float(last_row['High']), "low": safe_float(last_row['Low']),
            "ema_9": safe_float(last_row.get('EMA_9')), "ema_21": safe_float(last_row.get('EMA_21')),
            "ema_50": safe_float(last_row.get('EMA_50')), "ema_200": safe_float(last_row.get('EMA_200')),
            "rsi": safe_float(last_row.get('RSI')), "macd": safe_float(last_row.get('MACD')),
            "atr": safe_float(last_row.get('ATR')), "supertrend": safe_float(last_row.get('SuperTrend')),
            "stochrsi_k": safe_float(last_row.get('StochRSI_K')), "adx": safe_float(last_row.get('ADX'))
        }

        history = []
        for idx, row in df_ind.tail(60).iterrows():
            history.append({
                "time": str(idx)[:10], "open": safe_float(row['Open']), "high": safe_float(row['High']),
                "low": safe_float(row['Low']), "close": safe_float(row['Close']), "volume": int(row['Volume']),
                "ema_9": safe_float(row.get('EMA_9')), "ema_21": safe_float(row.get('EMA_21'))
            })

        return {
            "ticker": ticker, "price_details": tech_indicators, "fundamentals": fundamentals,
            "candlestick_patterns": candlesticks, "news": news, "fii_dii": fii_dii, "historical_chart": history
        }

    def get_option_chain(self, ticker: str) -> dict:
        """
        Uses new nse_scraper.py to get REAL live option chain data, 
        and formats it to match the UI expectations (ce_premium, pe_premium, etc).
        """
        raw_ticker = ticker.upper().strip().replace('.NS', '')
        if raw_ticker in ["NIFTY", "NIFTY50", "NIFTY 50", "^NSEI"]: raw_ticker = "NIFTY"
        elif raw_ticker in ["BANKNIFTY", "BANK NIFTY", "^NSEBANK"]: raw_ticker = "BANKNIFTY"
        
        # Get spot price for fallback
        try:
            spot_df = self.fetch_market_data(ticker, period="1d", interval="1m")
            spot_price = float(spot_df.iloc[-1]['Close'])
        except:
            spot_price = 0.0

        # Fetch real NSE data!
        try:
            nse_data = nse_fetcher.get_option_chain(raw_ticker, spot_price)
        except Exception as e:
            print(f"Error getting option chain from NSE Scraper: {e}")
            return {"error": "Failed to fetch option chain."}
            
        # Reformat NSE Scraper output to match what UI expects
        formatted_options = []
        for strike_data in nse_data.get("strikes", []):
            formatted_options.append({
                "strike": strike_data["strike"],
                "moneyness": strike_data["moneyness"],
                "ce_premium": strike_data["ce_price"],
                "pe_premium": strike_data["pe_price"],
                "ce_oi": strike_data["ce_oi"],
                "pe_oi": strike_data["pe_oi"],
                "ce_iv": strike_data["ce_iv"],
                "pe_iv": strike_data["pe_iv"]
            })
            
        return {
            "ticker": ticker,
            "spot_price": nse_data.get("spot_price", spot_price),
            "pcr": nse_data.get("pcr", 1.0),
            "sentiment": nse_data.get("sentiment", "Neutral"),
            "max_pain": nse_data.get("max_pain", 0),
            "expiry": nse_data.get("expiry_date", "Unknown"),
            "options": formatted_options
        }
