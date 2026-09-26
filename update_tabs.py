import re

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    c = f.read()

# 1. Add currentTab state
state_code = """  const [tradeQty, setTradeQty] = useState(10);
  const [autoTrade, setAutoTrade] = useState({ is_running: false, daily_stats: {} });
  const [autoLogs, setAutoLogs] = useState([]);
  const [currentTab, setCurrentTab] = useState('manual');
"""
c = re.sub(r'  const \[tradeQty, setTradeQty\] = useState\(10\);\s*const \[autoTrade, setAutoTrade\] = useState\(\{ is_running: false, daily_stats: \{\} \}\);', state_code, c)

# 2. Add log fetcher
fetch_auto = """
    const fetchAutoTrade = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/autotrade/status`);
        if (res.ok) setAutoTrade(await res.json());
        
        const logRes = await fetch(`${API_BASE}/api/autotrade/logs`);
        if (logRes.ok) setAutoLogs((await logRes.json()).logs);
      } catch (e) {}
    };
    fetchAutoTrade();
"""
c = re.sub(r'    const fetchAutoTrade = async \(\) => \{.*?\n    fetchAutoTrade\(\);', fetch_auto, c, flags=re.DOTALL)

# 3. Add Navbar and Main Container wrappers
top_bar = """
      <div className="header">
        <div className="logo">
          <Cpu size={24} color="#10b981" /> ANTIGRAVITY ALGO
        </div>
        <div style={{ display: 'flex', gap: '20px' }}>
          <button 
            onClick={() => setCurrentTab('manual')} 
            className={currentTab === 'manual' ? 'btn-primary' : 'btn-secondary'}
          >
            Manual Analysis
          </button>
          <button 
            onClick={() => setCurrentTab('auto')} 
            className={currentTab === 'auto' ? 'btn-primary' : 'btn-secondary'}
            style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
          >
            <Activity size={16}/> Autonomous Bot {autoTrade.is_running && <span className="spinner" style={{width:'8px',height:'8px',background:'#10b981',borderRadius:'50%'}}></span>}
          </button>
        </div>
        <div className="api-key-container">
"""
c = re.sub(r'      <div className="header">\s*<div className="logo">\s*<Cpu size=\{24\} color="#10b981" /> ANTIGRAVITY ALGO\s*</div>\s*<div className="api-key-container">', top_bar, c)

# 4. Remove AutoTrader from the right bar in Manual tab
c = re.sub(r'          <div className="glass-panel" style=\{\{ padding: \'15px\', marginTop: \'15px\' \}\}>\s*<div style=\{\{ display: \'flex\', justifyContent: \'space-between\', alignItems: \'center\', marginBottom: \'10px\' \}\}>\s*<span style=\{\{ fontSize: \'0\.9rem\', fontWeight: 600 \}\}>Autonomous Trading Bot</span>.*?Trades:.*?SL Hits:.*?</div>\s*</div>', '', c, flags=re.DOTALL)

# 5. Wrap the main-content with tab condition
main_content_start = """
    {currentTab === 'manual' ? (
      <>
      <div className="main-content">
"""
c = c.replace('<div className="main-content">', main_content_start)

# 6. Add Auto Bot tab content at the end before bottom panel
auto_tab_content = """
      </div>
      </>
    ) : (
      <div className="main-content" style={{ display: 'flex', flexDirection: 'column', padding: '20px', gap: '20px', overflowY: 'auto' }}>
        <div className="glass-panel" style={{ padding: '20px' }}>
          <h2>Autonomous Trading Engine (Crude Oil & Nifty)</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
            The bot monitors markets continuously when activated. It respects your daily 30k simulator risk limits.
          </p>
          <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
            <button 
              onClick={toggleAutoTrade}
              style={{ 
                background: autoTrade.is_running ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                color: autoTrade.is_running ? '#ef4444' : '#10b981',
                border: `1px solid ${autoTrade.is_running ? '#ef4444' : '#10b981'}`,
                padding: '10px 20px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem'
              }}
            >
              {autoTrade.is_running ? 'STOP BOT (RUNNING)' : 'START BOT (OFFLINE)'}
            </button>
            <div style={{ display: 'flex', gap: '15px' }}>
              <div className="signal-val-box">
                <span className="signal-val-label">Max Daily Trades</span>
                <span className="signal-val-price">{autoTrade.daily_stats?.trades_taken || 0} / 4</span>
              </div>
              <div className="signal-val-box">
                <span className="signal-val-label">SL Hits (Stop Limit)</span>
                <span className="signal-val-price">{autoTrade.daily_stats?.sl_hits || 0} / 2</span>
              </div>
              <div className="signal-val-box">
                <span className="signal-val-label">Target Hits</span>
                <span className="signal-val-price">{autoTrade.daily_stats?.target_hits || 0} / 2</span>
              </div>
            </div>
          </div>
        </div>
        <div className="agent-terminal glass-panel" style={{ flex: 1, minHeight: '400px' }}>
          <div className="terminal-header">
            <span className="terminal-title"><Terminal size={16} /> SYSTEM LIVE LOGS</span>
          </div>
          <div className="terminal-logs" style={{ padding: '15px', fontFamily: 'monospace', color: '#10b981', height: '400px', overflowY: 'auto' }}>
            {autoLogs.map((log, idx) => (
              <div key={idx} style={{ marginBottom: '5px' }}>{log}</div>
            ))}
            {autoLogs.length === 0 && <div style={{color:'var(--text-muted)'}}>No logs available...</div>}
            <div ref={(el) => { el?.scrollIntoView(); }} />
          </div>
        </div>
      </div>
    )}
"""
c = re.sub(r'\s*</div>\s*\{/\* 4\. Bottom Panel: Portfolio Summary \*/\}', auto_tab_content + '\n      {/* 4. Bottom Panel: Portfolio Summary */}', c)

# 7. Add Activity Icon import
c = c.replace("import { Search, Terminal, RefreshCw, Play, Wallet } from 'lucide-react';", "import { Search, Terminal, RefreshCw, Play, Wallet, Activity } from 'lucide-react';")

with open(r'd:\AI_Projects\AlgoTradingBot\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(c)

print('App.jsx patched for tabs.')
