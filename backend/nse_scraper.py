import time
import math
import logging
from typing import Dict, Any, Tuple
from curl_cffi import requests

logger = logging.getLogger(__name__)

class NSEOptionChainFetcher:
    def __init__(self):
        # We will reuse the same session to maintain cookies
        self.session = requests.Session(impersonate="chrome124")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
            "Connection": "keep-alive"
        }
        self.is_warmed_up = False
        
        # Simple TTL Cache: symbol -> {"timestamp": float, "data": dict}
        self.cache = {}
        self.CACHE_TTL = 30  # 30 seconds caching

    def _warmup_session(self):
        """Hit the main page to get initial cookies (nsit, ak_bmsc, bm_sv)."""
        if self.is_warmed_up:
            return
        
        try:
            logger.info("Warming up NSE session cookies...")
            self.session.get("https://www.nseindia.com", headers=self.headers, timeout=10)
            self.is_warmed_up = True
            time.sleep(1)  # Brief pause after warmup
        except Exception as e:
            logger.error(f"Failed to warmup NSE session: {e}")

    def fetch_raw_option_chain(self, symbol: str, is_index: bool = True) -> dict:
        """Fetches raw JSON from NSE API."""
        self._warmup_session()
        
        endpoint = "option-chain-indices" if is_index else "option-chain-equities"
        url = f"https://www.nseindia.com/api/{endpoint}?symbol={symbol}"
        
        logger.info(f"Fetching live NSE option chain for {symbol}...")
        response = self.session.get(url, headers=self.headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code in [401, 403]:
            # Retry once with a fresh warmup
            logger.warning(f"NSE returned {response.status_code}. Retrying warmup...")
            self.is_warmed_up = False
            self._warmup_session()
            response = self.session.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
                
        raise Exception(f"Failed to fetch option chain. HTTP {response.status_code}: {response.text}")

    def get_option_chain(self, symbol: str, spot_price: float = None) -> dict:
        """
        Main public method to get formatted option chain. 
        Tries cache first, then live NSE data, then falls back to Black-Scholes.
        """
        current_time = time.time()
        
        # 1. Check Cache
        if symbol in self.cache:
            cached_data = self.cache[symbol]
            if current_time - cached_data["timestamp"] < self.CACHE_TTL:
                logger.info(f"Returning cached option chain for {symbol}")
                return cached_data["data"]
                
        # 2. Try fetching real data
        is_index = symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
        if symbol == "SENSEX":
            # BSE not supported by NSE scraper directly, use fallback or BSE scraper
            # We'll rely on fallback for Sensex right now
            logger.info("Sensex detected, using fallback synthetic chain.")
            data = self._generate_synthetic_chain(symbol, spot_price)
            self.cache[symbol] = {"timestamp": current_time, "data": data}
            return data

        try:
            raw_data = self.fetch_raw_option_chain(symbol, is_index)
            formatted_data = self._format_nse_data(symbol, raw_data)
            
            # Save to cache
            self.cache[symbol] = {"timestamp": current_time, "data": formatted_data}
            return formatted_data
            
        except Exception as e:
            logger.error(f"Live NSE fetch failed for {symbol}: {e}. Falling back to synthetic.")
            if spot_price is None:
                raise ValueError("Spot price is required for synthetic fallback when live fetch fails.")
            data = self._generate_synthetic_chain(symbol, spot_price)
            self.cache[symbol] = {"timestamp": current_time, "data": data}
            return data

    def _format_nse_data(self, symbol: str, raw_data: dict) -> dict:
        """Parses NSE JSON into our required frontend/agent format."""
        records = raw_data.get("records", {})
        data_list = records.get("data", [])
        
        if not data_list:
            raise ValueError("No data found in NSE response")

        # Get spot price and current expiry
        spot_price = records.get("underlyingValue", 0.0)
        expiry_dates = records.get("expiryDates", [])
        current_expiry = expiry_dates[0] if expiry_dates else "Unknown"

        # Filter data for current expiry
        current_expiry_data = [item for item in data_list if item.get("expiryDate") == current_expiry]
        
        # Sort by strike price
        current_expiry_data.sort(key=lambda x: x.get("strikePrice", 0))
        
        # Find ATM strike
        closest_diff = float('inf')
        atm_strike = 0
        for item in current_expiry_data:
            strike = item.get("strikePrice", 0)
            diff = abs(strike - spot_price)
            if diff < closest_diff:
                closest_diff = diff
                atm_strike = strike

        # Select 5 strikes above and 5 below ATM
        atm_idx = next((i for i, item in enumerate(current_expiry_data) if item.get("strikePrice") == atm_strike), -1)
        if atm_idx != -1:
            start_idx = max(0, atm_idx - 5)
            end_idx = min(len(current_expiry_data), atm_idx + 6)
            selected_data = current_expiry_data[start_idx:end_idx]
        else:
            selected_data = current_expiry_data[:11]

        formatted_strikes = []
        total_ce_oi = 0
        total_pe_oi = 0

        # Calculate max pain
        max_pain = self._calculate_max_pain(current_expiry_data)

        for item in selected_data:
            strike = item.get("strikePrice", 0)
            ce = item.get("CE", {})
            pe = item.get("PE", {})
            
            ce_oi = ce.get("openInterest", 0) * 50  # Usually given in lots/contracts, multiply by approximate lot size if needed, but relative is fine
            pe_oi = pe.get("openInterest", 0) * 50
            
            total_ce_oi += ce.get("openInterest", 0)
            total_pe_oi += pe.get("openInterest", 0)

            formatted_strikes.append({
                "strike": strike,
                "ce_price": ce.get("lastPrice", 0.0),
                "pe_price": pe.get("lastPrice", 0.0),
                "ce_oi": ce.get("openInterest", 0),
                "pe_oi": pe.get("openInterest", 0),
                "ce_iv": ce.get("impliedVolatility", 0.0),
                "pe_iv": pe.get("impliedVolatility", 0.0),
                "moneyness": "ATM" if strike == atm_strike else ("ITM" if strike < spot_price else "OTM") # Very basic
            })

        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 1.0
        
        sentiment = "Neutral"
        if pcr > 1.2:
            sentiment = "Bullish (Put writers dominating)"
        elif pcr < 0.8:
            sentiment = "Bearish (Call writers dominating)"

        return {
            "source": "NSE_LIVE",
            "expiry_date": current_expiry,
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "strikes": formatted_strikes,
            "pcr": round(pcr, 2),
            "max_pain": max_pain,
            "sentiment": sentiment,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi
        }

    def _calculate_max_pain(self, expiry_data: list) -> float:
        """Calculates Max Pain strike price."""
        # Max pain is the strike where option buyers lose the most money (and sellers gain the most).
        pain_values = {}
        
        # Consider strikes around the ATM for performance
        strikes = [item.get("strikePrice", 0) for item in expiry_data]
        if not strikes:
            return 0.0
            
        for eval_strike in strikes:
            total_pain = 0
            for item in expiry_data:
                strike = item.get("strikePrice", 0)
                ce_oi = item.get("CE", {}).get("openInterest", 0)
                pe_oi = item.get("PE", {}).get("openInterest", 0)
                
                # intrinsic value if expiry happens at eval_strike
                ce_pain = max(0, eval_strike - strike) * ce_oi
                pe_pain = max(0, strike - eval_strike) * pe_oi
                
                total_pain += (ce_pain + pe_pain)
            pain_values[eval_strike] = total_pain
            
        # Return strike with minimum pain
        if pain_values:
            return min(pain_values, key=pain_values.get)
        return 0.0

    def _std_normal_cdf(self, x: float) -> float:
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    def _black_scholes(self, S, K, t, r, sigma, option_type="CE"):
        """Fallback Black Scholes formula."""
        if t <= 0:
            return max(0, S - K) if option_type == "CE" else max(0, K - S)
        
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        
        if option_type == "CE":
            price = S * self._std_normal_cdf(d1) - K * math.exp(-r * t) * self._std_normal_cdf(d2)
        else:
            price = K * math.exp(-r * t) * self._std_normal_cdf(-d2) - S * self._std_normal_cdf(-d1)
        
        return max(price, 0.05)

    def _generate_synthetic_chain(self, ticker: str, spot_price: float) -> dict:
        """Generates synthetic chain if NSE is unreachable."""
        import datetime
        
        if spot_price <= 0:
            return {"error": "Invalid spot price"}

        # Dynamic strike interval
        if "NIFTY" in ticker:
            strike_interval = 50
            sigma = 0.14
        elif "BANKNIFTY" in ticker or "SENSEX" in ticker:
            strike_interval = 100
            sigma = 0.16
        else:
            if spot_price < 500: strike_interval = 5
            elif spot_price < 2000: strike_interval = 10
            elif spot_price < 5000: strike_interval = 20
            else: strike_interval = 50
            sigma = 0.24
            
        atm_strike = round(spot_price / strike_interval) * strike_interval
        
        # Generate Strikes (5 up, 5 down)
        strikes = [atm_strike + (i * strike_interval) for i in range(-5, 6)]
        
        # Approx time to expiry (3 days for simulation)
        t = 3 / 365.0 
        r = 0.07

        formatted_strikes = []
        for K in strikes:
            ce_price = self._black_scholes(spot_price, K, t, r, sigma, "CE")
            pe_price = self._black_scholes(spot_price, K, t, r, sigma, "PE")
            
            dist = abs(K - spot_price) / spot_price
            ce_oi = int(1200000 / (1 + dist * 0.4))
            pe_oi = int(250000 / (1 + dist * 1.5))
            
            formatted_strikes.append({
                "strike": K,
                "ce_price": round(ce_price, 2),
                "pe_price": round(pe_price, 2),
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "ce_iv": round(sigma * 100, 2),
                "pe_iv": round(sigma * 100, 2),
                "moneyness": "ATM" if K == atm_strike else ("ITM" if K < spot_price else "OTM")
            })

        return {
            "source": "SYNTHETIC_FALLBACK",
            "expiry_date": (datetime.datetime.now() + datetime.timedelta(days=3)).strftime("%d-%b-%Y"),
            "spot_price": spot_price,
            "atm_strike": atm_strike,
            "strikes": formatted_strikes,
            "pcr": 0.95,
            "max_pain": atm_strike,
            "sentiment": "Neutral (Synthetic Data)",
            "total_ce_oi": sum(s['ce_oi'] for s in formatted_strikes),
            "total_pe_oi": sum(s['pe_oi'] for s in formatted_strikes)
        }

# Singleton instance
nse_fetcher = NSEOptionChainFetcher()
