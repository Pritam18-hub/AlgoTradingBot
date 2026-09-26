import React, { useState, useEffect, useRef } from 'react';
import { 
  TrendingUp, TrendingDown, Search, Cpu, Terminal, 
  Wallet, ShieldCheck, RefreshCw, AlertTriangle, Play 
} from 'lucide-react';
import StockChart from './components/Chart';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [openaiKey, setOpenaiKey] = useState(() => localStorage.getItem('openai_key') || '');
  const [tempKey, setTempKey] = useState(() => localStorage.getItem('openai_key') || '');
  const [keySaved, setKeySaved] = useState(false);
  
  const [ticker, setTicker] = useState('RELIANCE');
  const [searchQuery, setSearchQuery] = useState('RELIANCE');
  const [stockData, setStockData] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [portfolio, setPortfolio] = useState({ balance: 100000.0, equity: 100000.0, total_pnl: 0.0, positions: [], history: [] });
  const [indices, setIndices] = useState({});
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const [tradeQty, setTradeQty] = useState(10);
  
  const [activeTab, setActiveTab] = useState('overview');
  const [optionChain, setOptionChain] = useState(null);

  // Poll intervals
  useEffect(() => {
    localStorage.setItem('openai_key', openaiKey);
  }, [openaiKey]);

  // Initial load
  useEffect(() => {
    fetchIndices();
    fetchStockData(ticker);
    fetchPortfolio();

    // Setup periodic polling (every 5 seconds)
    const interval = setInterval(() => {
      fetchIndices();
      fetchPortfolio();
      if (ticker) {
        pollStockPrice(ticker);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [ticker]);

  const fetchIndices = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indices`);
      if (res.ok) {
        const data = await res.json();
        setIndices(data);
      }
    } catch (err) {
      console.error('Failed to fetch indices:', err);
    }
  };

  const fetchPortfolio = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/summary`);
      if (res.ok) {
        const data = await res.json();
        setPortfolio(data);
      }
    } catch (err) {
      console.error('Failed to fetch portfolio:', err);
    }
  };

  const fetchOptionChain = async (symbol) => {
    try {
      const res = await fetch(`${API_BASE}/api/stock/${symbol}/option-chain`);
      if (res.ok) {
        const data = await res.json();
        setOptionChain(data);
      }
    } catch (err) {
      console.error('Failed to fetch option chain:', err);
    }
  };

  const fetchStockData = async (symbol) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/stock/${symbol}`);
      if (!res.ok) {
        const errDetails = await res.json();
        throw new Error(errDetails.detail || 'Ticker not found');
      }
      const data = await res.json();
      setStockData(data);
      setAnalysisResult(null); // Reset analysis on ticker search
      fetchOptionChain(symbol);
    } catch (err) {
      setError(err.message);
      setStockData(null);
      setOptionChain(null);
    } finally {
      setLoading(false);
    }
  };

  const pollStockPrice = async (symbol) => {
    try {
      const res = await fetch(`${API_BASE}/api/stock/${symbol}`);
      if (res.ok) {
        const data = await res.json();
        // Update stockData close price and historical chart's last bar
        setStockData(prev => {
          if (!prev || prev.ticker !== data.ticker) return prev;
          return {
            ...prev,
            price_details: data.price_details,
            historical_chart: data.historical_chart
          };
        });
      }
      fetchOptionChain(symbol);
    } catch (err) {
      console.error('Failed to poll price:', err);
    }
  };

  const triggerAgentAnalysis = async () => {
    if (!openaiKey) {
      setError('Please provide an OpenAI API key in the header to run agent analysis.');
      return;
    }
    setAnalyzing(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker,
          openai_key: openaiKey
        })
      });
      if (!res.ok) {
        const errDetails = await res.json();
        throw new Error(errDetails.detail || 'Agent analysis failed');
      }
      const data = await res.json();
      setAnalysisResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setTicker(searchQuery.trim().toUpperCase());
    }
  };

  const executePaperTrade = async (action, orderType = 'EQ', strike = 'None', price = null) => {
    if (!stockData) return;
    const tradePrice = price || stockData.price_details.close;
    
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: ticker,
          action: action,
          qty: parseInt(tradeQty),
          price: tradePrice,
          instrument: orderType,
          strike: strike
        })
      });
      if (!res.ok) {
        const errDetails = await res.json();
        throw new Error(errDetails.detail || 'Trade failed');
      }
      fetchPortfolio();
      alert(`Simulated order executed: ${action} ${tradeQty} ${ticker} @ ₹${tradePrice}`);
    } catch (err) {
      alert(`Order failed: ${err.message}`);
    }
  };

  const executeSquareOff = async (position) => {
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: position.ticker,
          action: 'SELL',
          qty: position.qty,
          price: position.current_price,
          instrument: position.instrument,
          strike: position.strike
        })
      });
      if (!res.ok) {
        const errDetails = await res.json();
        throw new Error(errDetails.detail || 'Square off failed');
      }
      fetchPortfolio();
      alert(`Simulated square off executed for ${position.ticker}`);
    } catch (err) {
      alert(`Square off failed: ${err.message}`);
    }
  };

  const resetSimulatedPortfolio = async () => {
    if (!window.confirm('Are you sure you want to reset your simulated trading account? All cash balances and histories will be restored.')) return;
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/reset`, { method: 'POST' });
      if (res.ok) {
        fetchPortfolio();
      }
    } catch (err) {
      console.error('Reset failed:', err);
    }
  };

  // Helper formatting classes
  const getPnLClass = (val) => (val >= 0 ? 'pnl-green' : 'pnl-red');
  const getPnLIcon = (val) => (val >= 0 ? <TrendingUp size={16} className="pnl-green" /> : <TrendingDown size={16} className="pnl-red" />);

  return (
    <div className="app-container">
      {/* 1. Header Area */}
      <header className="header">
        <div className="logo-container">
          <Cpu className="pnl-green" size={24} />
          <span className="logo-text">ANTIGRAVITY ALGO</span>
        </div>

        <div className="api-key-container">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>OpenAI API Key:</span>
          <input
            type="password"
            placeholder="sk-proj-..."
            className="api-key-input"
            style={{ width: '220px' }}
            value={tempKey}
            onChange={(e) => setTempKey(e.target.value)}
          />
          <button 
            type="button"
            className="btn-primary"
            style={{ padding: '6px 12px', fontSize: '0.75rem', borderRadius: '6px' }}
            onClick={() => {
              setOpenaiKey(tempKey);
              setKeySaved(true);
              setTimeout(() => setKeySaved(false), 2000);
            }}
          >
            {keySaved ? 'Saved ✓' : 'Save Key'}
          </button>
        </div>
      </header>

      {/* 2. Ticker Tape Indices */}
      <div className="ticker-tape">
        {Object.entries(indices).map(([name, item]) => {
          if (item.error) return null;
          return (
            <div key={name} className="ticker-item">
              <span style={{ color: 'var(--text-secondary)' }}>{name}:</span>
              <span className="ticker-val">₹{item.price?.toLocaleString('en-IN')}</span>
              <span className={getPnLClass(item.change)} style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                {item.change >= 0 ? '+' : ''}{item.pct_change}%
                {getPnLIcon(item.change)}
              </span>
            </div>
          );
        })}
      </div>

      {/* 3. Main Workspace Area */}
      <div className="main-workspace">
        {/* Left Panel: Search & Stats */}
        <div className="left-bar">
          <div className="glass-panel" style={{ padding: '15px' }}>
            <form onSubmit={handleSearch} className="search-box">
              <input
                type="text"
                placeholder="Search Stock (e.g. Reliance, TCS)"
                className="search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button type="submit" className="btn-primary" style={{ padding: '10px' }}>
                <Search size={18} />
              </button>
            </form>
          </div>

          {error && (
            <div className="glass-panel glow-red" style={{ padding: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-bear)', fontSize: '0.85rem' }}>
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}

          {stockData && (
            <div className="glass-panel" style={{ display: 'flex', gap: '5px', padding: '5px', background: 'rgba(0, 0, 0, 0.2)', borderRadius: '8px' }}>
              <button 
                type="button"
                className="btn-secondary"
                style={{ flex: 1, padding: '8px', fontSize: '0.8rem', background: activeTab === 'overview' ? 'var(--bg-tertiary)' : 'transparent', border: 'none', borderRadius: '6px' }}
                onClick={() => setActiveTab('overview')}
              >
                Overview
              </button>
              <button 
                type="button"
                className="btn-secondary"
                style={{ flex: 1, padding: '8px', fontSize: '0.8rem', background: activeTab === 'options' ? 'var(--bg-tertiary)' : 'transparent', border: 'none', borderRadius: '6px' }}
                onClick={() => setActiveTab('options')}
              >
                Option Chain (F&O)
              </button>
            </div>
          )}

          {stockData && activeTab === 'overview' && (
            <div className="glass-panel stock-summary">
              <div className="stock-name-price">
                <div>
                  <div className="stock-ticker">{stockData.ticker}</div>
                  <div className="stock-company">{stockData.ticker.startsWith('^') ? 'Index Indicators' : 'NSE Equities'}</div>
                </div>
                <div className="stock-price">
                  ₹{stockData.price_details.close?.toLocaleString('en-IN')}
                </div>
              </div>

              <div className="price-change-row">
                <span style={{ color: 'var(--text-secondary)' }}>Today's Change</span>
                <span className={getPnLClass(stockData.price_details.price_change)}>
                  {stockData.price_details.price_change >= 0 ? '+' : ''}
                  {stockData.price_details.price_change} ({stockData.price_details.pct_change}%)
                </span>
              </div>

              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">RSI (14)</span>
                  <span className="stat-value" style={{ color: stockData.price_details.rsi > 70 ? 'var(--color-bear)' : stockData.price_details.rsi < 30 ? 'var(--color-bull)' : 'var(--text-primary)' }}>
                    {stockData.price_details.rsi}
                  </span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">MACD</span>
                  <span className="stat-value">{stockData.price_details.macd}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">P/E Ratio</span>
                  <span className="stat-value">{stockData.fundamentals.pe_ratio || 'N/A'}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Market Cap</span>
                  <span className="stat-value">{stockData.fundamentals.market_cap_cr ? `₹${stockData.fundamentals.market_cap_cr.toLocaleString('en-IN')} Cr` : 'N/A'}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">EMA (50)</span>
                  <span className="stat-value">₹{stockData.price_details.ema_50}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">EMA (200)</span>
                  <span className="stat-value">₹{stockData.price_details.ema_200}</span>
                </div>
              </div>
            </div>
          )}

          {stockData && activeTab === 'overview' && stockData.candlestick_patterns.length > 0 && (
            <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '10px', padding: '15px' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Candlestick Patterns</span>
              <div className="candlestick-list">
                {stockData.candlestick_patterns.map((item, idx) => (
                  <div key={idx} className="candle-pattern-item">
                    <div className="candle-pattern-header">
                      <span>{item.pattern}</span>
                      <span className={item.sentiment === 'Bullish' ? 'bullet-bullish' : item.sentiment === 'Bearish' ? 'bullet-bearish' : 'bullet-neutral'}>
                        {item.sentiment}
                      </span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{item.description} ({item.date})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {stockData && activeTab === 'options' && optionChain && (
            <div className="glass-panel" style={{ padding: '15px', display: 'flex', flexDirection: 'column', gap: '12px', overflow: 'hidden' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                <span>PCR: <strong className={optionChain.pcr > 1.0 ? 'pnl-green' : 'pnl-red'}>{optionChain.pcr}</strong> ({optionChain.sentiment})</span>
                <span>Expiry: {optionChain.expiry}</span>
              </div>
              <div style={{ overflowX: 'auto', overflowY: 'auto', maxHeight: '400px', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                <table className="portfolio-table" style={{ width: '100%', fontSize: '0.7rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)' }}>
                      <th style={{ padding: '6px 4px', textAlign: 'left' }}>Call OI</th>
                      <th style={{ padding: '6px 4px', textAlign: 'left' }}>CE Price</th>
                      <th style={{ padding: '6px 4px', textAlign: 'center' }}>Strike</th>
                      <th style={{ padding: '6px 4px', textAlign: 'right' }}>PE Price</th>
                      <th style={{ padding: '6px 4px', textAlign: 'right' }}>Put OI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.options?.map((opt, i) => {
                      const isATM = opt.moneyness === 'ATM';
                      return (
                        <tr key={i} style={{ background: isATM ? 'rgba(0, 176, 255, 0.08)' : 'transparent', borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                          <td style={{ color: 'var(--text-muted)', padding: '6px 4px', fontSize: '0.65rem' }}>{(opt.ce_oi / 100000).toFixed(1)}L</td>
                          <td style={{ color: 'var(--color-bull)', fontWeight: 600, padding: '6px 4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <button 
                              type="button"
                              onClick={() => executePaperTrade('BUY', 'CE', `${opt.strike} CE`, opt.ce_premium)}
                              className="btn-primary" 
                              style={{ padding: '2px 4px', fontSize: '0.6rem', border: 'none', background: 'rgba(0, 230, 118, 0.2)', color: 'var(--color-bull)', cursor: 'pointer' }}
                            >
                              B
                            </button>
                            ₹{opt.ce_premium.toFixed(2)}
                          </td>
                          <td style={{ textAlign: 'center', fontWeight: 'bold', padding: '6px 4px', borderLeft: '1px solid var(--border-color)', borderRight: '1px solid var(--border-color)', color: isATM ? 'var(--color-info)' : 'var(--text-primary)' }}>
                            {opt.strike}
                          </td>
                          <td style={{ color: 'var(--color-bear)', fontWeight: 600, padding: '6px 4px', textAlign: 'right' }}>
                            <span style={{ marginRight: '4px' }}>₹{opt.pe_premium.toFixed(2)}</span>
                            <button 
                              type="button"
                              onClick={() => executePaperTrade('BUY', 'PE', `${opt.strike} PE`, opt.pe_premium)}
                              className="btn-primary" 
                              style={{ padding: '2px 4px', fontSize: '0.6rem', border: 'none', background: 'rgba(255, 23, 68, 0.2)', color: 'var(--color-bear)', cursor: 'pointer' }}
                            >
                              B
                            </button>
                          </td>
                          <td style={{ color: 'var(--text-muted)', padding: '6px 4px', textAlign: 'right', fontSize: '0.65rem' }}>{(opt.pe_oi / 100000).toFixed(1)}L</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Center Panel: Charts */}
        <div className="chart-area">
          <div className="chart-container-inner">
            <div className="chart-header">
              <span className="chart-title">
                {ticker} Candlestick Chart (Daily / Moving Averages Overlay)
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Powered by TradingView</span>
            </div>
            {loading ? (
              <div className="loader-container">
                <div className="spinner"></div>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Fetching live chart data...</span>
              </div>
            ) : stockData ? (
              <StockChart data={stockData.historical_chart} ticker={stockData.ticker} />
            ) : (
              <div className="loader-container">
                <Search size={30} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Search a stock to load chart</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Multi-Agent Console & Recommendation Output */}
        <div className="right-bar">
          <div className="glass-panel" style={{ padding: '15px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyItems: 'center', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Multi-Agent Strategy Desk</span>
              <button 
                onClick={triggerAgentAnalysis} 
                disabled={analyzing || !stockData} 
                className="btn-primary" 
                style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '8px 12px' }}
              >
                {analyzing ? <RefreshCw size={14} className="spinner" /> : <Play size={14} />}
                {analyzing ? 'Auditing...' : 'Analyze Market'}
              </button>
            </div>
          </div>

          {analyzing && (
            <div className="glass-panel" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', justifyItems: 'center', justifyContent: 'center', alignItems: 'center', gap: '12px' }}>
              <div className="spinner" style={{ width: '50px', height: '50px' }}></div>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
                Junior Analyst collecting technical factors...<br/>
                Team Lead auditing strategy and event risk...
              </span>
            </div>
          )}

          {!analyzing && analysisResult && (
            <div className="agent-terminal glass-panel">
              <div className="terminal-header">
                <span className="terminal-title">
                  <Terminal size={16} />
                  AI AUDIT DEBATE
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Structured Logs</span>
              </div>
              
              <div className="terminal-logs">
                {/* Junior Agent Proposal Log */}
                <div className="log-entry log-junior">
                  <div className="log-role junior-role">[JUNIOR ANALYST] EQUITY PROPOSAL</div>
                  <div className="log-text">
                    Action: {analysisResult.junior_proposal.action}
                    {"\n"}Entry Range: {analysisResult.junior_proposal.entry_range}
                    {"\n"}Target 1: ₹{analysisResult.junior_proposal.target_1} | Target 2: ₹{analysisResult.junior_proposal.target_2}
                    {"\n"}Stop Loss: ₹{analysisResult.junior_proposal.stop_loss}
                  </div>
                </div>

                {/* Options Strategy Specialist Log */}
                {analysisResult.options_specialist && (
                <div className="log-entry log-junior" style={{ borderColor: '#e040fb' }}>
                  <div className="log-role junior-role" style={{ color: '#e040fb', background: 'rgba(224, 64, 251, 0.15)' }}>[OPTIONS STRATEGY] F&O PROPOSAL</div>
                  <div className="log-text">
                    Strategy: {analysisResult.options_specialist.strategy_type}
                    {"\n"}Primary Leg: {analysisResult.options_specialist.primary_leg}
                    {"\n"}Entry Premium: ₹{analysisResult.options_specialist.primary_entry}
                    {"\n"}Target 1: ₹{analysisResult.options_specialist.primary_target_1} | Target 2: ₹{analysisResult.options_specialist.primary_target_2}
                    {"\n"}Stop Loss: ₹{analysisResult.options_specialist.primary_stop_loss}
                    {"\n"}Risk/Reward per Lot: ₹{analysisResult.options_specialist.max_risk_per_lot} / ₹{analysisResult.options_specialist.max_reward_per_lot} (1:{analysisResult.options_specialist.risk_reward_ratio})
                  </div>
                </div>
                )}

                {/* Team Lead Verification Log */}
                <div className="log-entry log-lead">
                  <div className="log-role lead-role">[SENIOR VERIFIER / TEAM LEAD] FINAL DECISION</div>
                  <div className="log-text">
                    Status: {analysisResult.lead_verification.approved ? 'APPROVED' : 'REJECTED'}
                    {"\n"}Final Action: {analysisResult.lead_verification.final_action} ({analysisResult.lead_verification.instrument_type})
                    {analysisResult.lead_verification.final_strike !== 'None' && `\nTarget Strike: ${analysisResult.lead_verification.final_strike}`}
                    {"\n"}Final Entry Range: {analysisResult.lead_verification.final_action === 'HOLD' ? 'N/A' : analysisResult.lead_verification.final_entry_range}
                    {"\n"}Targets: ₹{analysisResult.lead_verification.final_target_1} / ₹{analysisResult.lead_verification.final_target_2} | SL: ₹{analysisResult.lead_verification.final_stop_loss}
                    {"\n\n"}Risk Assessment:
                    {"\n"}{analysisResult.lead_verification.risk_assessment}
                    {"\n\n"}Outlook:
                    {"\n"}{analysisResult.lead_verification.outlook_prediction}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Actionable Signal Card (Show if Lead approved and action is BUY or SELL) */}
          {!analyzing && analysisResult && analysisResult.lead_verification.approved && (
            analysisResult.lead_verification.final_action !== 'HOLD' ? (
              <div className="glass-panel signal-card glow-green">
                <div className="signal-action buy">
                  {analysisResult.lead_verification.final_action} RECOMMENDED
                </div>
                <div className="signal-row">
                  <div className="signal-val-box">
                    <span className="signal-val-label">Entry Range</span>
                    <span className="signal-val-price">{analysisResult.lead_verification.final_entry_range}</span>
                  </div>
                  <div className="signal-val-box">
                    <span className="signal-val-label">Stop Loss</span>
                    <span className="signal-val-price stop">₹{analysisResult.lead_verification.final_stop_loss}</span>
                  </div>
                </div>
                <div className="signal-row">
                  <div className="signal-val-box">
                    <span className="signal-val-label">Target 1</span>
                    <span className="signal-val-price target">₹{analysisResult.lead_verification.final_target_1}</span>
                  </div>
                  <div className="signal-val-box">
                    <span className="signal-val-label">Target 2</span>
                    <span className="signal-val-price target">₹{analysisResult.lead_verification.final_target_2}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', marginTop: '5px' }}>
                  <input 
                    type="number" 
                    value={tradeQty} 
                    onChange={(e) => setTradeQty(Math.max(1, parseInt(e.target.value) || 1))}
                    className="search-input" 
                    style={{ width: '80px', padding: '6px' }}
                  />
                  <button 
                    onClick={() => executePaperTrade(
                      analysisResult.lead_verification.final_action, 
                      analysisResult.lead_verification.instrument_type === 'Options' ? (analysisResult.lead_verification.final_strike.includes('CE') ? 'CE' : 'PE') : 'EQ',
                      analysisResult.lead_verification.final_strike,
                      parseFloat(analysisResult.lead_verification.final_entry_range.split('-')[0]) || stockData.price_details.close
                    )} 
                    className="btn-primary" 
                    style={{ flex: 1, padding: '6px' }}
                  >
                    Place Simulated Trade
                  </button>
                </div>
              </div>
            ) : (
              <div className="glass-panel signal-card glow-warn" style={{ borderColor: 'var(--color-warn)', boxShadow: '0 0 10px rgba(255, 179, 0, 0.15)', padding: '15px', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center', textAlign: 'center' }}>
                <div className="signal-action hold" style={{ background: 'rgba(255, 179, 0, 0.15)', color: 'var(--color-warn)', border: '1px solid var(--color-warn)', width: '100%', borderRadius: '6px', padding: '6px 12px', textTransform: 'uppercase', fontWeight: 800, fontSize: '1.1rem' }}>
                  HOLD RECOMMENDATION ACTIVE
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  The market is currently consolidating sideways. Option buyers should stay out of call or put purchases to avoid Theta (time) decay. No active trade execution recommended.
                </span>
              </div>
            )
          )}
        </div>
      </div>

      {/* 4. Bottom Panel: Portfolio Summary */}
      <div className="portfolio-panel">
        <div className="portfolio-stats">
          <div className="portfolio-metrics">
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Wallet size={14} /> SIMULATOR BALANCE
            </span>
            <div className="portfolio-metric-row" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                ₹{portfolio.equity?.toLocaleString('en-IN')}
              </span>
              <span className={getPnLClass(portfolio.total_pnl)} style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '3px' }}>
                {portfolio.total_pnl >= 0 ? '+' : ''}{portfolio.total_pnl?.toLocaleString('en-IN')}
              </span>
            </div>
            <div className="portfolio-metric-row">
              <span style={{ color: 'var(--text-secondary)' }}>Cash Balance:</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>₹{portfolio.balance?.toLocaleString('en-IN')}</span>
            </div>
          </div>
          
          <button onClick={resetSimulatedPortfolio} className="btn-secondary" style={{ padding: '6px', fontSize: '0.75rem' }}>
            Reset Simulator
          </button>
        </div>

        <div className="portfolio-table-wrapper">
          {portfolio.positions && portfolio.positions.length > 0 ? (
            <table className="portfolio-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Avg Price</th>
                  <th>LTP</th>
                  <th>Market Value</th>
                  <th>Unrealized P&L</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((pos, idx) => (
                  <tr key={idx}>
                    <td style={{ fontWeight: 600 }}>{pos.ticker}</td>
                    <td>
                      <span className={`instrument-badge ${pos.instrument === 'EQ' ? 'badge-eq' : pos.instrument === 'CE' ? 'badge-ce' : 'badge-pe'}`}>
                        {pos.instrument} {pos.strike !== 'None' ? `@ ${pos.strike}` : ''}
                      </span>
                    </td>
                    <td>{pos.qty}</td>
                    <td>₹{pos.entry_price?.toLocaleString('en-IN')}</td>
                    <td>₹{pos.current_price?.toLocaleString('en-IN')}</td>
                    <td>₹{pos.market_value?.toLocaleString('en-IN')}</td>
                    <td className={getPnLClass(pos.pnl)}>
                      {pos.pnl >= 0 ? '+' : ''}{pos.pnl?.toLocaleString('en-IN')} ({pos.pnl_pct}%)
                    </td>
                    <td>
                      <button 
                        onClick={() => executeSquareOff(pos)} 
                        className="btn-secondary" 
                        style={{ padding: '4px 8px', fontSize: '0.7rem', border: '1px solid var(--color-bear)', color: 'var(--color-bear)', background: 'transparent' }}
                      >
                        Square Off
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-positions">
              No open positions. Use the agent analysis to verify and execute automated trading recommendations.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
