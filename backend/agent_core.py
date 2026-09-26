import os
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

class EquityProposal(BaseModel):
    action: str = Field(description="Action recommendation: BUY, SELL, or HOLD")
    entry_range: str = Field(description="Suggested entry price range for the equity stock (e.g., '2450 - 2465')")
    target_1: float = Field(description="First take-profit target price")
    target_2: float = Field(description="Second take-profit target price")
    stop_loss: float = Field(description="Stop loss price level")
    rationale_technical: List[str] = Field(description="Technical factors like SuperTrend, RSI, VWAP, Candlesticks")
    rationale_fundamental: List[str] = Field(description="Fundamental factors like PE, Debt/Equity, FII/DII")
    news_impact: str = Field(description="Assessment of recent news sentiment")
    outlook_prediction: str = Field(description="Market prediction for today and upcoming 3-5 days")
    risk_rating: str = Field(description="Low, Medium, High")
    confidence_score: float = Field(description="Confidence score from 0.0 to 1.0")

class OptionsStrategyProposal(BaseModel):
    strategy_type: str = Field(description="Strategy: 'CE_BUY', 'PE_BUY', 'CE_SELL', 'PE_SELL', 'HOLD'")
    primary_leg: str = Field(description="Example: 'NIFTY 24400 CE' or 'None'")
    primary_entry: float = Field(description="Option Premium Entry Price (e.g., 200)")
    primary_target_1: float = Field(description="Option Premium Target 1 (e.g., 240)")
    primary_target_2: float = Field(description="Option Premium Target 2 (e.g., 260)")
    primary_stop_loss: float = Field(description="Option Premium Stop Loss (e.g., 180)")
    lot_size: int = Field(description="Lot size (e.g., NIFTY=25, BANKNIFTY=15)")
    max_risk_per_lot: float = Field(description="Max risk per lot in INR (Entry - SL) * lot_size")
    max_reward_per_lot: float = Field(description="Max reward per lot in INR (T2 - Entry) * lot_size")
    risk_reward_ratio: float = Field(description="RRR (e.g., 2.0 for 1:2)")
    strategy_rationale: str = Field(description="Why this specific strike and strategy?")
    greeks_analysis: str = Field(description="IV assessment and theta decay warning")

class LeadVerification(BaseModel):
    approved: bool = Field(description="True if the best proposal is approved, False if rejected")
    final_action: str = Field(description="Final action: BUY, SELL, or HOLD")
    instrument_type: str = Field(description="Equities or Options")
    final_strike: str = Field(description="Selected strike if Options, else 'None'")
    final_entry_range: str = Field(description="Final entry price/premium")
    final_target_1: float = Field(description="Final Target 1 price level")
    final_target_2: float = Field(description="Final Target 2 price level")
    final_stop_loss: float = Field(description="Final Stop Loss price level")
    risk_reward_ratio: float = Field(description="Calculated Risk-Reward Ratio (e.g. 1.5)")
    risk_assessment: str = Field(description="Detailed risk critique covering capital allocation and event risk")
    outlook_prediction: str = Field(description="Final verified outlook prediction")
    review_comments: str = Field(description="Team Lead's detailed feedback")

class TradingAgentCore:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def _get_client(self, api_key: Optional[str] = None) -> OpenAI:
        key = api_key or self.api_key
        if not key:
            raise ValueError("OpenAI API Key is missing. Please provide it in settings or set OPENAI_API_KEY env variable.")
        return OpenAI(api_key=key)

    def run_analysis(self, market_data: dict, custom_api_key: Optional[str] = None) -> dict:
        client = self._get_client(custom_api_key)
        
        # Use gpt-4o as suggested in the implementation plan for better reasoning, fallback to mini if needed
        MODEL = "gpt-4o-mini"

        ticker = market_data.get("ticker", "Unknown Ticker")
        price_details = market_data.get("price_details", {})
        candlesticks = market_data.get("candlestick_patterns", [])
        option_chain = market_data.get("option_chain", {})
        
        # Determine lot size
        lot_size = 25 if "NIFTY" in ticker and "BANK" not in ticker else 15 if "BANK" in ticker else 500

        # ---------------------------------------------
        # STEP 1: JUNIOR ANALYST (EQUITIES)
        # ---------------------------------------------
        junior_sys = (
            "You are a professional junior technical and fundamental analyst for Indian Equities.\n"
            "Analyze the data and propose an equity spot trade.\n"
            "CRITICAL: If indicators show no trend (RSI 43-57, flat MACD), action = HOLD, targets = 0.\n"
        )
        try:
            junior_comp = client.beta.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": junior_sys},
                    {"role": "user", "content": f"Ticker: {ticker}\nPrices/Inds: {price_details}\nPatterns: {candlesticks}"}
                ],
                response_format=EquityProposal,
                temperature=0.3
            )
            junior_proposal = junior_comp.choices[0].message.parsed
        except Exception as e:
            return {"error": f"Failed Junior Agent: {e}"}

        # ---------------------------------------------
        # STEP 2: OPTIONS STRATEGY SPECIALIST
        # ---------------------------------------------
        options_sys = (
            "You are an Options Strategy Specialist for the Indian Stock Market.\n"
            "Review the real NSE Option Chain data and propose the best F&O trade.\n"
            "RULES:\n"
            "1. Enforce a tight 20-point stop loss and 40-60 point target for intraday options.\n"
            "2. If IV is high (PCR extreme), consider option selling.\n"
            "3. If sideways, strategy_type = HOLD, primary_entry = 0, targets = 0.\n"
            "4. Output targets strictly in premium values (e.g., buy at 200, SL at 180), NOT spot prices.\n"
        )
        try:
            opt_comp = client.beta.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": options_sys},
                    {"role": "user", "content": f"Ticker: {ticker}\nSpot: {price_details.get('close')}\nOption Chain: {option_chain}\nLot Size: {lot_size}"}
                ],
                response_format=OptionsStrategyProposal,
                temperature=0.3
            )
            options_proposal = opt_comp.choices[0].message.parsed
        except Exception as e:
            return {"error": f"Failed Options Specialist: {e}"}

        # ---------------------------------------------
        # STEP 3: SENIOR RISK MANAGER (TEAM LEAD)
        # ---------------------------------------------
        lead_sys = (
            "You are the Senior Trading Desk Risk Manager.\n"
            "You have proposals from the Junior Equity Analyst and Options Specialist.\n"
            "Select the best strategy based on risk-to-reward and market context, or reject both (HOLD).\n"
            "Ensure capital risk is strictly managed. If Options trade is selected, verify the 20-point SL rule.\n"
            "Return the finalized VERIFIED strategy parameters. If HOLD, zero out all targets."
        )
        try:
            lead_comp = client.beta.chat.completions.parse(
                model=MODEL,
                messages=[
                    {"role": "system", "content": lead_sys},
                    {"role": "user", "content": f"Equity Proposal: {junior_proposal.model_dump_json()}\nOptions Proposal: {options_proposal.model_dump_json()}\nData: {price_details}\nChain: {option_chain.get('max_pain')}"}
                ],
                response_format=LeadVerification,
                temperature=0.2
            )
            lead_verification = lead_comp.choices[0].message.parsed
        except Exception as e:
            return {"error": f"Failed Senior Lead: {e}"}

        # Format output to match existing UI expectations as closely as possible, 
        # while passing the new rich data.
        return {
            "junior_proposal": {
                "action": junior_proposal.action,
                "instrument_type": "Equities",
                "strike_price": "None",
                "entry_range": junior_proposal.entry_range,
                "target_1": junior_proposal.target_1,
                "target_2": junior_proposal.target_2,
                "stop_loss": junior_proposal.stop_loss,
                "rationale_technical": junior_proposal.rationale_technical,
                "rationale_fundamental": junior_proposal.rationale_fundamental,
                "news_impact": junior_proposal.news_impact,
                "outlook_prediction": junior_proposal.outlook_prediction,
                "risk_rating": junior_proposal.risk_rating,
                "confidence_score": junior_proposal.confidence_score
            },
            "options_specialist": options_proposal.model_dump(),
            "lead_verification": lead_verification.model_dump()
        }
