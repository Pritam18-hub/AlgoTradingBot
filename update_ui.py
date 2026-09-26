import re

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add AutoTrader state
state_code = """  const [tradeQty, setTradeQty] = useState(10);
  const [autoTrade, setAutoTrade] = useState({ is_running: false, daily_stats: {} });
"""
c = re.sub(r'  const \[tradeQty, setTradeQty\] = useState\(10\);', state_code, c)

# 2. Add fetchAutoTrade status
fetch_auto = """
    const fetchAutoTrade = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/autotrade/status`);
        if (res.ok) {
          const data = await res.json();
          setAutoTrade(data);
        }
      } catch (e) {}
    };
    fetchAutoTrade();
"""
c = re.sub(r'fetchPortfolio\(\);\n', 'fetchPortfolio();\n' + fetch_auto, c)

# 3. Add toggle function
toggle_func = """
  const toggleAutoTrade = async () => {
    const action = autoTrade.is_running ? 'stop' : 'start';
    try {
      const res = await fetch(`${API_BASE}/api/autotrade/${action}`, { method: 'POST' });
      if (res.ok) {
        fetchAutoTrade();
      }
    } catch (e) {}
  };
"""
c = re.sub(r'  const triggerAgentAnalysis = async \(\) => \{', toggle_func + '\n  const triggerAgentAnalysis = async () => {', c)

# 4. Render toggle button and stats in the UI
auto_ui = """
          <div className="glass-panel" style={{ padding: '15px', marginTop: '15px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Autonomous Trading Bot</span>
              <button 
                onClick={toggleAutoTrade}
                style={{ 
                  background: autoTrade.is_running ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                  color: autoTrade.is_running ? '#ef4444' : '#10b981',
                  border: `1px solid ${autoTrade.is_running ? '#ef4444' : '#10b981'}`,
                  padding: '5px 12px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold'
                }}
              >
                {autoTrade.is_running ? 'STOP BOT' : 'START BOT'}
              </button>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Monitoring: NIFTY, BANKNIFTY, CL=F (Crude Oil)
            </div>
            {autoTrade.daily_stats && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '10px', fontSize: '0.8rem' }}>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '5px', borderRadius: '4px' }}>
                  Trades: {autoTrade.daily_stats.trades_taken || 0} / 4
                </div>
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', padding: '5px', borderRadius: '4px' }}>
                  SL Hits: {autoTrade.daily_stats.sl_hits || 0} / 2
                </div>
              </div>
            )}
          </div>
"""
c = re.sub(r'          \{/\* Actionable Signal Card \(Show if Lead approved and action is BUY or SELL\) \*/\}', auto_ui + '\n          {/* Actionable Signal Card (Show if Lead approved and action is BUY or SELL) */}', c)

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(c)
print("Done")
