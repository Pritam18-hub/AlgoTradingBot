from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

from backend.data_collector import DataCollector
from backend.agent_core import TradingAgentCore
from backend.portfolio import PortfolioManager

app = FastAPI(title="Algo Trading Bot API", version="1.0")

# Enable CORS for React Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize modules
collector = DataCollector()
agent_core = TradingAgentCore()
portfolio = PortfolioManager()

@app.get("/")
def read_root():
    return {"status": "running", "message": "Algo Trading Bot Backend API is active."}

@app.get("/api/indices")
def get_indices():
    """
    Fetches the latest prices of major Indian indices.
    """
    indices = {
        "Nifty 50": "^NSEI",
        "Bank Nifty": "^NSEBANK",
        "Sensex": "^BSESN"
    }
    results = {}
    for name, ticker in indices.items():
        try:
            df = collector.fetch_market_data(ticker, period="5d", interval="1d")
            if not df.empty:
                last_close = df.iloc[-1]['Close']
                prev_close = df.iloc[-2]['Close'] if len(df) > 1 else last_close
                change = last_close - prev_close
                pct_change = (change / prev_close) * 100
                results[name] = {
                    "ticker": ticker,
                    "price": round(last_close, 2),
                    "change": round(change, 2),
                    "pct_change": round(pct_change, 2)
                }
            else:
                results[name] = {"error": "No data found"}
        except Exception as e:
            results[name] = {"error": str(e)}
    return results

@app.get("/api/stock/{ticker}")
def get_stock_data(ticker: str):
    """
    Fetches complete historical, fundamental, and indicator data for a stock.
    """
    data = collector.get_comprehensive_data(ticker)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data
from backend.stock_screener import screener

@app.get("/api/stock/{ticker}/option-chain")
def get_option_chain(ticker: str):
    """
    Fetches calculated options chain strike premiums and open interest (OI) stats.
    """
    data = collector.get_option_chain(ticker)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data

@app.get("/api/screener/multibagger")
def get_multibagger_screener():
    """
    Runs the multi-bagger screener and returns potential stocks.
    """
    return {"results": screener.run_screener()}


@app.post("/api/analyze")
def analyze_stock(
    ticker: str = Body(..., embed=True), 
    openai_key: Optional[str] = Body(None, embed=True)
):
    """
    Triggers the multi-agent reasoning chain.
    """
    # 1. Fetch comprehensive market data
    market_data = collector.get_comprehensive_data(ticker)
    if "error" in market_data:
        raise HTTPException(status_code=404, detail=market_data["error"])

    # 1b. Fetch calculated option chain data and append it
    option_chain_data = collector.get_option_chain(ticker)
    if "error" not in option_chain_data:
        market_data["option_chain"] = option_chain_data

    # 2. Run analysis
    try:
        analysis_result = agent_core.run_analysis(market_data, custom_api_key=openai_key)
        if "error" in analysis_result:
            raise HTTPException(status_code=500, detail=analysis_result["error"])
        
        # Inject current market parameters into results
        analysis_result["ticker"] = ticker
        analysis_result["spot_price"] = market_data["price_details"]["close"]
        return analysis_result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/portfolio/summary")
def get_portfolio():
    """
    Retrieves the simulated portfolio with active, live-calculated PnL.
    """
    # Find all unique tickers in open positions to fetch their live prices
    open_positions = portfolio.data.get("positions", [])
    unique_tickers = list(set([pos["ticker"] for pos in open_positions]))
    
    current_prices = {}
    for ticker in unique_tickers:
        try:
            df = collector.fetch_market_data(ticker, period="1d", interval="1m")
            if df.empty:
                df = collector.fetch_market_data(ticker, period="5d", interval="1d")
            
            if not df.empty:
                current_prices[ticker] = df.iloc[-1]['Close']
        except Exception as e:
            print(f"Error fetching live price for portfolio ticker {ticker}: {e}")

    summary = portfolio.get_portfolio_summary(current_prices)
    return summary

@app.post("/api/portfolio/trade")
def execute_portfolio_trade(
    ticker: str = Body(...),
    action: str = Body(...), # BUY or SELL
    qty: int = Body(...),
    price: float = Body(...),
    instrument: str = Body("EQ"), # EQ, CE, PE
    strike: str = Body("None")
):
    """
    Executes a trade in the paper trading simulator.
    """
    result = portfolio.execute_trade(
        ticker=ticker,
        action=action,
        qty=qty,
        price=price,
        instrument=instrument,
        strike=strike
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result

@app.post("/api/portfolio/reset")
def reset_portfolio():
    """
    Resets the simulated trading account.
    """
    portfolio.reset_portfolio()
    return {"success": True, "message": "Simulated portfolio reset successful."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
